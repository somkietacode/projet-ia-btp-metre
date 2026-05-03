"""
knowledge_base_module.py — Service de gestion de la base de connaissance publique (admin).

Ce module expose les opérations CRUD sur la table `public_documents` :

    add_document    → Persiste un fichier uploadé après extraction OCR/texte
    delete_document → Supprime un document par son identifiant
    list_documents  → Retourne les métadonnées (sans le binaire) de tous les documents

Cycle de vie d'un ajout :
    UploadFile (bytes) → fichier temporaire → extraction OCR → PublicDocument en base → nettoyage

Dépendances internes :
    orm_module.PublicDocument   — modèle SQLAlchemy
    content_extractor           — extracteur OCR/parsing multi-format
    exeption_module.CustomException — gestion unifiée des erreurs métier
"""

import os
import tempfile
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from lib.core.orm_module import PublicDocument
from lib.core.content_extractor import extract_content, get_supported_extensions
from lib.core.exeption_module import CustomException
from lib.core import vector_store_module as vector_store


# ──────────────────────────────────────────────────────────────
# OPÉRATIONS PUBLIQUES
# ──────────────────────────────────────────────────────────────

def add_document(
    db: Session,
    filename: str,
    content_bytes: bytes,
    extension: str,
) -> PublicDocument:
    """
    Ajoute un document dans la base de connaissance publique.

    Étapes :
        1. Validation de l'extension contre les formats supportés.
        2. Écriture du contenu binaire dans un fichier temporaire.
        3. Extraction du texte via OCR ou parsing selon le format.
        4. Création et persistance du `PublicDocument` en base.
        5. Suppression systématique du fichier temporaire.

    Args:
        db            : Session SQLAlchemy active (injectée par FastAPI).
        filename      : Nom d'origine du fichier (ex: "cctp_lot1.pdf").
        content_bytes : Contenu binaire brut du fichier uploadé.
        extension     : Extension du fichier (ex: ".pdf" ou "pdf").

    Returns:
        L'instance PublicDocument créée et rafraîchie depuis la base.

    Raises:
        CustomException(400) — extension non supportée.
        CustomException(500) — erreur inattendue lors de l'extraction.
    """
    # ── Normalisation et validation de l'extension ──
    ext = extension.lower().strip()
    if not ext.startswith("."):
        ext = f".{ext}"

    supported = get_supported_extensions()
    if ext not in supported:
        raise CustomException(
            f"Extension '{ext}' non supportée. "
            f"Formats acceptés : {', '.join(sorted(supported))}",
            status_code=400,
        )

    # ── Écriture temporaire pour l'extracteur (qui opère sur des fichiers locaux) ──
    tmp_path: str | None = None
    text_content: str | None = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
            tmp_file.write(content_bytes)
            tmp_path = tmp_file.name

        # ── Extraction OCR / parsing ──
        text_content = extract_content(tmp_path, extension=ext)

        if text_content is None:
            # L'extraction a échoué ou le fichier ne contient pas de texte exploitable.
            # Le document est quand même stocké (contenu binaire disponible).
            print(
                f"  [KB] Avertissement : aucun texte extrait pour '{filename}'. "
                "Le document sera stocké sans indexation textuelle."
            )

    except CustomException:
        # Laisser remonter les erreurs métier telles quelles
        raise

    except Exception as exc:
        raise CustomException(
            f"Erreur inattendue lors du traitement de '{filename}' : {exc}",
            status_code=500,
        )

    finally:
        # ── Nettoyage systématique du fichier temporaire ──
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError as remove_err:
                print(f"  [KB] Impossible de supprimer le fichier temporaire : {remove_err}")

    # ── Déduction du statut final d'indexation ──
    indexation_status = "indexed" if text_content else "failed"

    # ── Persistence en base de données ──
    now = datetime.now(timezone.utc).isoformat()

    doc = PublicDocument(
        filename=filename,
        content=content_bytes,
        text_content=text_content,
        upload_date=now,
        extension=ext,
        indexation_status=indexation_status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    print(
        f"  [KB] Document ajouté — id={doc.id}, fichier='{filename}', "
        f"indexation_status='{indexation_status}'"
    )

    # ── Indexation vectorielle (si le texte a été extrait) ──
    if text_content:
        try:
            chunks = vector_store.index_document(doc.id, text_content, filename)
            print(f"  [KB] {chunks} chunk(s) indexé(s) dans Qdrant pour le document id={doc.id}.")
        except Exception as vec_exc:
            # L'échec d'indexation vectorielle ne doit pas bloquer la persistance
            print(f"  [KB] Avertissement : indexation vectorielle échouée pour id={doc.id} : {vec_exc}")

    return doc


def get_document(db: Session, doc_id: int) -> PublicDocument:
    """
    Récupère un document de la base de connaissance par son identifiant.

    Args:
        db     : Session SQLAlchemy active.
        doc_id : Identifiant du document.

    Returns:
        L'instance PublicDocument (inclut le binaire et le texte extrait).

    Raises:
        CustomException(404) — document introuvable.
    """
    doc = db.query(PublicDocument).filter(PublicDocument.id == doc_id).first()
    if doc is None:
        raise CustomException(
            f"Document introuvable : id={doc_id}",
            status_code=404,
        )
    return doc


def delete_document(db: Session, doc_id: int) -> None:
    """
    Supprime un document de la base de connaissance par son identifiant.

    Args:
        db     : Session SQLAlchemy active.
        doc_id : Identifiant du document à supprimer.

    Raises:
        CustomException(404) — document introuvable.
    """
    doc = db.query(PublicDocument).filter(PublicDocument.id == doc_id).first()

    if doc is None:
        raise CustomException(
            f"Document introuvable : id={doc_id}",
            status_code=404,
        )

    db.delete(doc)
    db.commit()
    print(f"  [KB] Document supprimé — id={doc_id}")

    # ── Suppression des vecteurs associés dans Qdrant ──
    try:
        vector_store.delete_document(doc_id)
    except Exception as vec_exc:
        print(f"  [KB] Avertissement : suppression vectorielle échouée pour id={doc_id} : {vec_exc}")


def list_documents(db: Session) -> list[dict]:
    """
    Retourne les métadonnées de tous les documents de la base de connaissance.

    Le champ `content` (binaire) est volontairement exclu pour ne pas
    surcharger les réponses réseau.

    Args:
        db : Session SQLAlchemy active.

    Returns:
        Liste de dictionnaires avec les champs :
            id                 (int) — identifiant unique
            filename           (str) — nom du fichier original
            extension          (str) — extension (ex: ".pdf")
            upload_date        (str) — date ISO 8601 de l'upload (UTC)
            indexation_status  (str) — "pending" | "indexing" | "indexed" | "failed"
    """
    docs = db.query(PublicDocument).order_by(PublicDocument.id.desc()).all()

    return [
        {
            "id":                doc.id,
            "filename":          doc.filename,
            "extension":         doc.extension,
            "upload_date":       doc.upload_date,
            "indexation_status": doc.indexation_status,
        }
        for doc in docs
    ]


def search_documents(db: Session, query: str, top_k: int = 5) -> dict:
    """
    Recherche sémantique dans la base de connaissance publique.

    Combine la recherche vectorielle Qdrant avec une récupération des
    métadonnées et du texte complet depuis PostgreSQL.

    Étapes :
        1. Recherche vectorielle dans Qdrant (top_k chunks les plus proches).
        2. Pour chaque doc_id retourné, récupération du document PostgreSQL
           (une seule requête par doc_id distinct, mis en cache).
        3. Assemblage d'une réponse structurée chunk + document source.

    Args:
        db     : Session SQLAlchemy active.
        query  : Question ou texte en langage naturel.
        top_k  : Nombre maximal de chunks retournés (défaut : 5).

    Returns:
        Dictionnaire compatible avec VectorSearchResponse :
            query         (str)  — requête originale
            total_results (int)  — nombre de résultats effectifs
            results       (list) — liste de résultats enrichis

        Chaque résultat contient :
            score        (float)  — similarité cosinus [0, 1]
            chunk        (str)    — passage de texte correspondant
            description  (str)    — première phrase du chunk
            keywords     (list)   — mots-clés NLP (YAKE)
            chunk_index  (int)    — position dans le document
            total_chunks (int)    — nombre total de chunks du document
            document     (dict)   — métadonnées + text_content du doc source

    Raises:
        CustomException(400) — requête vide.
        CustomException(503) — Qdrant injoignable.
        CustomException(500) — erreur inattendue.
    """
    # ── Recherche vectorielle ──
    hits = vector_store.search(query, top_k=top_k)

    # ── Cache des documents PostgreSQL (évite N requêtes pour le même doc) ──
    doc_cache: dict[int, PublicDocument] = {}

    results = []
    for hit in hits:
        doc_id: int = hit["doc_id"]

        # Récupération depuis le cache ou la base
        if doc_id not in doc_cache:
            doc = db.query(PublicDocument).filter(PublicDocument.id == doc_id).first()
            if doc is None:
                # Le document a été supprimé de PostgreSQL mais ses vecteurs
                # sont encore dans Qdrant — on ignore ce résultat
                print(f"  [KB Search] Chunk orphelin ignoré — doc_id={doc_id} absent de PostgreSQL.")
                continue
            doc_cache[doc_id] = doc

        doc = doc_cache[doc_id]

        results.append({
            "score":        hit["score"],
            "chunk":        hit["chunk"],
            "description":  hit.get("description", ""),
            "keywords":     hit.get("keywords", []),
            "chunk_index":  hit["chunk_index"],
            "total_chunks": hit["total_chunks"],
            "document": {
                "id":               doc.id,
                "filename":         doc.filename,
                "extension":        doc.extension,
                "upload_date":      doc.upload_date,
                "indexation_status": doc.indexation_status,
                "text_content":     doc.text_content,
            },
        })

    return {
        "query":         query,
        "total_results": len(results),
        "results":       results,
    }
