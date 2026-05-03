"""
user_knowledge_base_module.py — Service de gestion de la base de connaissance privée (utilisateur).

Ce module expose les opérations CRUD sur la table `documents` pour un utilisateur donné.
Chaque document est strictement isolé par `user_id` ; aucun utilisateur ne peut
accéder aux documents d'un autre.

    add_document     → Persiste un fichier uploadé après extraction OCR/texte
    get_document     → Récupère un document (avec vérification de propriété)
    delete_document  → Supprime un document par son identifiant
    list_documents   → Retourne les métadonnées de tous les documents d'un utilisateur
    search_documents → Recherche sémantique vectorielle (filtrée par user_id)

Cycle de vie d'un ajout :
    UploadFile (bytes) → fichier temporaire → extraction OCR → Document en base → nettoyage

Dépendances internes :
    orm_module.Document             — modèle SQLAlchemy
    content_extractor               — extracteur OCR/parsing multi-format
    vector_store_module             — indexation / recherche Qdrant (collection privée)
    exeption_module.CustomException — gestion unifiée des erreurs métier
"""

import os
import tempfile
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from lib.core.orm_module import Document
from lib.core.content_extractor import extract_content, get_supported_extensions
from lib.core.exeption_module import CustomException
from lib.core import vector_store_module as vector_store


# ──────────────────────────────────────────────────────────────
# OPÉRATIONS PUBLIQUES
# ──────────────────────────────────────────────────────────────

def add_document(
    db: Session,
    user_id: int,
    filename: str,
    content_bytes: bytes,
    extension: str,
) -> Document:
    """
    Ajoute un document dans la base de connaissance privée d'un utilisateur.

    Étapes :
        1. Validation de l'extension contre les formats supportés.
        2. Écriture du contenu binaire dans un fichier temporaire.
        3. Extraction du texte via OCR ou parsing selon le format.
        4. Création et persistance du `Document` en base (lié à `user_id`).
        5. Indexation vectorielle dans la collection `private_documents` (Qdrant).
        6. Suppression systématique du fichier temporaire.

    Args:
        db            : Session SQLAlchemy active (injectée par FastAPI).
        user_id       : Identifiant de l'utilisateur propriétaire.
        filename      : Nom d'origine du fichier (ex: "devis_lot1.pdf").
        content_bytes : Contenu binaire brut du fichier uploadé.
        extension     : Extension du fichier (ex: ".pdf" ou "pdf").

    Returns:
        L'instance Document créée et rafraîchie depuis la base.

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
            print(
                f"  [UserKB] Avertissement : aucun texte extrait pour '{filename}' "
                f"(user_id={user_id}). Stockage sans indexation textuelle."
            )

    except CustomException:
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
                print(f"  [UserKB] Impossible de supprimer le fichier temporaire : {remove_err}")

    # ── Déduction du statut final d'indexation ──
    indexation_status = "indexed" if text_content else "failed"

    # ── Persistence en base de données ──
    now = datetime.now(timezone.utc).isoformat()

    doc = Document(
        user_id=user_id,
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
        f"  [UserKB] Document ajouté — id={doc.id}, user_id={user_id}, "
        f"fichier='{filename}', indexation_status='{indexation_status}'"
    )

    # ── Indexation vectorielle (si le texte a été extrait) ──
    if text_content:
        try:
            chunks = vector_store.index_private_document(doc.id, user_id, text_content, filename)
            print(
                f"  [UserKB] {chunks} chunk(s) indexé(s) dans Qdrant pour le document id={doc.id}."
            )
        except Exception as vec_exc:
            # L'échec d'indexation vectorielle ne doit pas bloquer la persistance
            print(
                f"  [UserKB] Avertissement : indexation vectorielle échouée "
                f"pour id={doc.id} : {vec_exc}"
            )

    return doc


def get_document(db: Session, user_id: int, doc_id: int) -> Document:
    """
    Récupère un document de la base de connaissance privée par son identifiant.

    La vérification de propriété (`user_id`) garantit qu'un utilisateur
    ne peut pas accéder aux documents d'un autre.

    Args:
        db      : Session SQLAlchemy active.
        user_id : Identifiant de l'utilisateur propriétaire.
        doc_id  : Identifiant du document.

    Returns:
        L'instance Document (inclut le binaire et le texte extrait).

    Raises:
        CustomException(404) — document introuvable ou n'appartenant pas à l'utilisateur.
    """
    doc = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.user_id == user_id)
        .first()
    )
    if doc is None:
        raise CustomException(
            f"Document introuvable : id={doc_id}",
            status_code=404,
        )
    return doc


def delete_document(db: Session, user_id: int, doc_id: int) -> None:
    """
    Supprime un document de la base de connaissance privée par son identifiant.

    La vérification de propriété (`user_id`) garantit qu'un utilisateur
    ne peut supprimer que ses propres documents.

    Args:
        db      : Session SQLAlchemy active.
        user_id : Identifiant de l'utilisateur propriétaire.
        doc_id  : Identifiant du document à supprimer.

    Raises:
        CustomException(404) — document introuvable ou n'appartenant pas à l'utilisateur.
    """
    doc = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.user_id == user_id)
        .first()
    )

    if doc is None:
        raise CustomException(
            f"Document introuvable : id={doc_id}",
            status_code=404,
        )

    db.delete(doc)
    db.commit()
    print(f"  [UserKB] Document supprimé — id={doc_id}, user_id={user_id}")

    # ── Suppression des vecteurs associés dans Qdrant ──
    try:
        vector_store.delete_private_document(doc_id)
    except Exception as vec_exc:
        print(
            f"  [UserKB] Avertissement : suppression vectorielle échouée "
            f"pour id={doc_id} : {vec_exc}"
        )


def list_documents(db: Session, user_id: int) -> list[dict]:
    """
    Retourne les métadonnées de tous les documents d'un utilisateur.

    Le champ `content` (binaire) est volontairement exclu pour ne pas
    surcharger les réponses réseau.

    Args:
        db      : Session SQLAlchemy active.
        user_id : Identifiant de l'utilisateur propriétaire.

    Returns:
        Liste de dictionnaires avec les champs :
            id                 (int) — identifiant unique
            filename           (str) — nom du fichier original
            extension          (str) — extension (ex: ".pdf")
            upload_date        (str) — date ISO 8601 de l'upload (UTC)
            indexation_status  (str) — "pending" | "indexing" | "indexed" | "failed"
    """
    docs = (
        db.query(Document)
        .filter(Document.user_id == user_id)
        .order_by(Document.id.desc())
        .all()
    )

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


def search_documents(db: Session, user_id: int, query: str, top_k: int = 5) -> dict:
    """
    Recherche sémantique dans la base de connaissance privée d'un utilisateur.

    Combine la recherche vectorielle Qdrant (filtrée par `user_id`) avec une
    récupération des métadonnées depuis PostgreSQL.

    Étapes :
        1. Recherche vectorielle dans Qdrant avec filtre `user_id` (top_k chunks).
        2. Pour chaque `doc_id` retourné, récupération du Document PostgreSQL
           (une seule requête par doc_id distinct, mis en cache).
        3. Vérification de propriété : les chunks orphelins sont ignorés.
        4. Assemblage d'une réponse structurée chunk + document source.

    Args:
        db      : Session SQLAlchemy active.
        user_id : Identifiant de l'utilisateur (isolation des résultats).
        query   : Question ou texte en langage naturel.
        top_k   : Nombre maximal de chunks retournés (défaut : 5).

    Returns:
        Dictionnaire compatible avec UserVectorSearchResponse :
            query         (str)  — requête originale
            total_results (int)  — nombre de résultats effectifs
            results       (list) — liste de résultats enrichis

    Raises:
        CustomException(400) — requête vide.
        CustomException(503) — Qdrant injoignable.
        CustomException(500) — erreur inattendue.
    """
    # ── Recherche vectorielle filtrée par user_id ──
    hits = vector_store.search_private(query, user_id=user_id, top_k=top_k)

    # ── Cache des documents PostgreSQL ──
    doc_cache: dict[int, Document] = {}

    results = []
    for hit in hits:
        doc_id: int = hit["doc_id"]

        if doc_id not in doc_cache:
            doc = (
                db.query(Document)
                .filter(Document.id == doc_id, Document.user_id == user_id)
                .first()
            )
            if doc is None:
                print(
                    f"  [UserKB Search] Chunk orphelin ignoré — "
                    f"doc_id={doc_id} absent de PostgreSQL pour user_id={user_id}."
                )
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
                "id":                doc.id,
                "filename":          doc.filename,
                "extension":         doc.extension,
                "upload_date":       doc.upload_date,
                "indexation_status": doc.indexation_status,
                "text_content":      doc.text_content,
            },
        })

    return {
        "query":         query,
        "total_results": len(results),
        "results":       results,
    }
