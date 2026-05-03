"""
vector_store_module.py — Indexation vectorielle des documents publics (Qdrant).

Collection dédiée : `public_documents` (séparée des éventuelles collections privées).

Fonctionnement d'un chunk :
    1. Découpage intelligent : paragraphes → phrases (spaCy) → fallback caractères
    2. Enrichissement NLP (sans IA) :
       - keywords  : extraction statistique via YAKE (top-N termes les plus saillants)
       - description : première phrase complète du chunk (spaCy)
    3. Embedding vectoriel : sentence-transformers (multilingue)
    4. Stockage Qdrant avec payload structuré incluant doc_id → lien vers PostgreSQL

API publique :
    index_document(doc_id, text, filename)  → découpe, enrichit, indexe
    delete_document(doc_id)                 → purge les vecteurs d'un document
    search(query, top_k)                    → recherche sémantique + retour doc_id

Configuration (variables d'environnement) :
    QDRANT_HOST              — hôte Qdrant           (défaut : "localhost")
    QDRANT_PORT              — port REST              (défaut : 6333)
    QDRANT_API_KEY           — clé API                (optionnel)
    EMBEDDING_MODEL_NAME     — modèle sentence-transformers
                               (défaut : paraphrase-multilingual-MiniLM-L12-v2)
    VECTOR_CHUNK_MAX_CHARS   — taille max d'un chunk en caractères (défaut : 1200)
    VECTOR_CHUNK_MIN_CHARS   — taille min pour conserver un chunk  (défaut : 80)
    VECTOR_KEYWORDS_TOP_N    — nombre de mots-clés YAKE par chunk  (défaut : 8)
    SPACY_MODEL              — modèle spaCy à charger              (défaut : fr_core_news_sm)

Payload Qdrant par point :
    doc_id        (int)       — FK vers public_documents.id (PostgreSQL)
    filename      (str)       — nom du fichier source
    chunk         (str)       — texte du passage
    description   (str)       — première phrase du chunk (résumé court)
    keywords      (list[str]) — mots-clés NLP extraits par YAKE
    chunk_index   (int)       — position dans le document (0-based)
    total_chunks  (int)       — nombre total de chunks du document
"""

import os
import re
import uuid
from typing import Any

import yake
import spacy
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from sentence_transformers import SentenceTransformer

from lib.core.exeption_module import CustomException


# ──────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────

_QDRANT_HOST: str    = os.getenv("QDRANT_HOST", "localhost")
_QDRANT_PORT: int    = int(os.getenv("QDRANT_PORT", "6333"))
_QDRANT_API_KEY: str | None = os.getenv("QDRANT_API_KEY") or None

# Collection dédiée aux documents publics (isolée des éventuelles collections privées)
_COLLECTION: str = "public_documents"

_EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/all-MiniLM-L6-v2",
)
_CHUNK_MAX: int  = int(os.getenv("VECTOR_CHUNK_MAX_CHARS", "1200"))
_CHUNK_MIN: int  = int(os.getenv("VECTOR_CHUNK_MIN_CHARS", "80"))
_KW_TOP_N: int   = int(os.getenv("VECTOR_KEYWORDS_TOP_N", "8"))
_SPACY_MODEL: str = os.getenv("SPACY_MODEL", "fr_core_news_sm")


# ──────────────────────────────────────────────────────────────
# SINGLETONS
# ──────────────────────────────────────────────────────────────

_client:  QdrantClient | None       = None
_encoder: SentenceTransformer | None = None
_nlp:     spacy.Language | None     = None
_kw_extractor: yake.KeywordExtractor | None = None


def get_client() -> QdrantClient:
    """Retourne le client Qdrant (singleton lazy)."""
    global _client
    if _client is None:
        try:
            kwargs: dict = {
                "host": _QDRANT_HOST,
                "port": _QDRANT_PORT,
                "https": False,
                "timeout": 15,
            }
            if _QDRANT_API_KEY:
                kwargs["api_key"] = _QDRANT_API_KEY
            _client = QdrantClient(**kwargs)
        except Exception as exc:
            raise CustomException(
                f"Impossible de se connecter à Qdrant ({_QDRANT_HOST}:{_QDRANT_PORT}) : {exc}",
                status_code=503,
            )
    return _client


def _get_encoder() -> SentenceTransformer:
    global _encoder
    if _encoder is None:
        cache_dir = os.getenv(
            "SENTENCE_TRANSFORMERS_HOME",
            os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "sentence_transformers"),
        )
        _encoder = SentenceTransformer(_EMBEDDING_MODEL, cache_folder=cache_dir)
    return _encoder


def _get_nlp() -> spacy.Language:
    """Charge le modèle spaCy (singleton). Fallback sur le modèle anglais si le FR est absent."""
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load(_SPACY_MODEL)
        except OSError:
            try:
                _nlp = spacy.load("en_core_web_sm")
                print(f"  [NLP] Modèle '{_SPACY_MODEL}' absent, fallback sur 'en_core_web_sm'.")
            except OSError:
                # Dernier recours : pipeline vide (tokenisation uniquement)
                _nlp = spacy.blank("fr")
                print("  [NLP] Aucun modèle spaCy disponible, pipeline vide utilisé.")
    return _nlp


def _get_kw_extractor() -> yake.KeywordExtractor:
    global _kw_extractor
    if _kw_extractor is None:
        _kw_extractor = yake.KeywordExtractor(
            lan="fr",
            n=3,           # n-grammes jusqu'à 3 mots
            dedupLim=0.7,  # déduplique les kw trop similaires
            top=_KW_TOP_N,
            features=None,
        )
    return _kw_extractor


def _ensure_collection() -> None:
    """Crée la collection `public_documents` dans Qdrant si elle n'existe pas."""
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if _COLLECTION not in existing:
        vector_size: int = _get_encoder().get_sentence_embedding_dimension()
        client.create_collection(
            collection_name=_COLLECTION,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        print(f"  [Qdrant] Collection '{_COLLECTION}' créée (dim={vector_size}).")


# ──────────────────────────────────────────────────────────────
# CHUNKING INTELLIGENT
# ──────────────────────────────────────────────────────────────

def _split_into_paragraphs(text: str) -> list[str]:
    """Découpe le texte en paragraphes (séparés par ≥2 sauts de ligne)."""
    paras = re.split(r"\n{2,}", text)
    return [p.strip() for p in paras if p.strip()]


def _split_paragraph_into_sentences(para: str) -> list[str]:
    """Segmente un paragraphe en phrases grâce au détecteur de frontières spaCy."""
    nlp = _get_nlp()
    doc = nlp(para)
    if doc.has_annotation("SENT_START"):
        return [s.text.strip() for s in doc.sents if s.text.strip()]
    # Fallback : split sur ". " si spaCy ne fournit pas de segmentation
    parts = re.split(r"(?<=[.!?])\s+", para)
    return [p.strip() for p in parts if p.strip()]


def _merge_sentences_into_chunks(sentences: list[str], max_chars: int) -> list[str]:
    """
    Regroupe les phrases consécutives en chunks de taille ≤ max_chars.

    Stratégie gloutonne : on accumule les phrases jusqu'à saturation,
    puis on ouvre un nouveau chunk en reprenant la dernière phrase du
    chunk précédent (chevauchement d'une phrase = contexte naturel).
    """
    chunks: list[str] = []
    current_sentences: list[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent)
        # Si la phrase seule dépasse max_chars, la découper par caractères
        if sent_len > max_chars:
            # Vider d'abord le buffer courant
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_len = 0
            # Découpe caractère par caractère avec overlap d'un mot
            for start in range(0, sent_len, max_chars - 50):
                sub = sent[start : start + max_chars].strip()
                if sub:
                    chunks.append(sub)
            continue

        if current_len + sent_len + 1 > max_chars and current_sentences:
            chunks.append(" ".join(current_sentences))
            # Chevauchement : on conserve la dernière phrase comme contexte
            overlap_sent = current_sentences[-1]
            current_sentences = [overlap_sent, sent]
            current_len = len(overlap_sent) + sent_len + 1
        else:
            current_sentences.append(sent)
            current_len += sent_len + 1

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks


def chunk_text(text: str) -> list[str]:
    """
    Découpe le texte en chunks selon la hiérarchie :
        paragraphes → phrases (spaCy) → taille max

    Returns:
        Liste de chunks non vides, de longueur ≥ CHUNK_MIN.
    """
    if not text:
        return []

    all_chunks: list[str] = []
    for para in _split_into_paragraphs(text):
        sentences = _split_paragraph_into_sentences(para)
        para_chunks = _merge_sentences_into_chunks(sentences, _CHUNK_MAX)
        all_chunks.extend(para_chunks)

    # Filtrer les micro-chunks sans substance
    return [c for c in all_chunks if len(c) >= _CHUNK_MIN]


# ──────────────────────────────────────────────────────────────
# ENRICHISSEMENT NLP PAR CHUNK
# ──────────────────────────────────────────────────────────────

def _extract_keywords(text: str) -> list[str]:
    """
    Extrait les N mots-clés les plus saillants via YAKE (statistique, sans IA).

    YAKE classe les n-grammes par score d'importance inverse (plus le score
    est bas, plus le terme est important). On retourne les termes normalisés.
    """
    extractor = _get_kw_extractor()
    try:
        keywords = extractor.extract_keywords(text)
        # keywords = [(kw_string, score), ...], trié par score croissant
        return [kw for kw, _score in keywords]
    except Exception:
        return []


def _extract_description(chunk: str) -> str:
    """
    Retourne la première phrase du chunk comme description courte.

    Utilisé pour donner un contexte rapide sans lire le chunk entier.
    Limité à 300 caractères pour rester compact dans le payload Qdrant.
    """
    nlp = _get_nlp()
    doc = nlp(chunk)
    if doc.has_annotation("SENT_START"):
        for sent in doc.sents:
            sentence = sent.text.strip()
            if sentence:
                return sentence[:300]
    # Fallback : prendre les 300 premiers caractères
    return chunk[:300].rstrip()


# ──────────────────────────────────────────────────────────────
# UTILITAIRES
# ──────────────────────────────────────────────────────────────

def _point_id(doc_id: int, chunk_index: int) -> str:
    """UUID déterministe pour un chunk : même entrée = même UUID (idempotence upsert)."""
    namespace = uuid.UUID("7b4e3c2a-1d0f-4e5b-9c8a-0f2e1a3b4c5d")
    return str(uuid.uuid5(namespace, f"pub:{doc_id}:{chunk_index}"))


# ──────────────────────────────────────────────────────────────
# OPÉRATIONS PUBLIQUES
# ──────────────────────────────────────────────────────────────

def index_document(doc_id: int, text: str, filename: str) -> int:
    """
    Indexe (ou ré-indexe) un document public dans la collection Qdrant dédiée.

    Étapes :
        1. Suppression des anciens vecteurs pour ce doc_id.
        2. Découpage intelligent en chunks.
        3. Enrichissement NLP : description + keywords.
        4. Génération des embeddings (batch).
        5. Upsert des points dans Qdrant.

    Args:
        doc_id   : Identifiant du document dans PostgreSQL (`public_documents.id`).
        text     : Texte extrait du document (issu du pipeline OCR/parsing).
        filename : Nom original du fichier (payload de contexte).

    Returns:
        Nombre de chunks effectivement indexés.

    Raises:
        CustomException(400) — texte vide ou aucun chunk généré.
        CustomException(503) — Qdrant injoignable.
        CustomException(500) — erreur inattendue.
    """
    if not text or not text.strip():
        raise CustomException(
            f"Impossible d'indexer le document id={doc_id} : texte vide.",
            status_code=400,
        )

    try:
        _ensure_collection()
        client  = get_client()
        encoder = _get_encoder()

        # ── 1. Purge des anciens vecteurs ──
        client.delete(
            collection_name=_COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )

        # ── 2. Chunking intelligent ──
        chunks = chunk_text(text)
        if not chunks:
            raise CustomException(
                f"Aucun chunk généré pour le document id={doc_id}.",
                status_code=400,
            )
        total = len(chunks)

        # ── 3. Enrichissement NLP ──
        enriched: list[dict] = []
        for chunk in chunks:
            enriched.append({
                "text":        chunk,
                "description": _extract_description(chunk),
                "keywords":    _extract_keywords(chunk),
            })

        # ── 4. Embeddings (batch sur les textes bruts) ──
        vectors = encoder.encode(
            [e["text"] for e in enriched],
            show_progress_bar=False,
        ).tolist()

        # ── 5. Construction et envoi des points ──
        points = [
            PointStruct(
                id=_point_id(doc_id, idx),
                vector=vector,
                payload={
                    "doc_id":       doc_id,
                    "filename":     filename,
                    "chunk":        e["text"],
                    "description":  e["description"],
                    "keywords":     e["keywords"],
                    "chunk_index":  idx,
                    "total_chunks": total,
                },
            )
            for idx, (e, vector) in enumerate(zip(enriched, vectors))
        ]

        client.upsert(collection_name=_COLLECTION, points=points)

        print(
            f"  [Qdrant] Document indexé — id={doc_id}, fichier='{filename}', "
            f"chunks={total}, collection='{_COLLECTION}'"
        )
        return total

    except CustomException:
        raise
    except Exception as exc:
        raise CustomException(
            f"Erreur lors de l'indexation du document id={doc_id} : {exc}",
            status_code=500,
        )


def delete_document(doc_id: int) -> None:
    """
    Supprime tous les vecteurs d'un document public dans Qdrant.

    Args:
        doc_id : Identifiant du document (`public_documents.id`).

    Raises:
        CustomException(503/500) en cas d'erreur Qdrant.
    """
    try:
        _ensure_collection()
        client = get_client()
        client.delete(
            collection_name=_COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )
        print(f"  [Qdrant] Vecteurs supprimés — doc_id={doc_id}, collection='{_COLLECTION}'")

    except CustomException:
        raise
    except Exception as exc:
        raise CustomException(
            f"Erreur lors de la suppression des vecteurs pour doc_id={doc_id} : {exc}",
            status_code=500,
        )


def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Recherche sémantique dans la collection des documents publics.

    Chaque résultat contient le `doc_id` permettant de récupérer le
    document complet depuis PostgreSQL pour une consultation approfondie.

    Args:
        query  : Question ou texte en langage naturel.
        top_k  : Nombre maximal de résultats (défaut : 5).

    Returns:
        Liste triée par score décroissant, chaque élément contenant :
            score        (float)      — similarité cosinus [0, 1]
            doc_id       (int)        — FK vers public_documents.id (PostgreSQL)
            filename     (str)        — nom du fichier source
            chunk        (str)        — passage de texte correspondant
            description  (str)        — première phrase du chunk
            keywords     (list[str])  — mots-clés NLP du chunk
            chunk_index  (int)        — position dans le document
            total_chunks (int)        — nombre de chunks du document

    Raises:
        CustomException(400) — requête vide.
        CustomException(503/500) — erreur Qdrant.
    """
    if not query or not query.strip():
        raise CustomException("La requête de recherche ne peut pas être vide.", status_code=400)

    try:
        _ensure_collection()
        client  = get_client()
        encoder = _get_encoder()

        query_vector = encoder.encode(query, show_progress_bar=False).tolist()

        result = client.query_points(
            collection_name=_COLLECTION,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "score":        round(hit.score, 4),
                "doc_id":       hit.payload.get("doc_id"),
                "filename":     hit.payload.get("filename"),
                "chunk":        hit.payload.get("chunk"),
                "description":  hit.payload.get("description"),
                "keywords":     hit.payload.get("keywords", []),
                "chunk_index":  hit.payload.get("chunk_index"),
                "total_chunks": hit.payload.get("total_chunks"),
            }
            for hit in result.points
        ]

    except CustomException:
        raise
    except Exception as exc:
        raise CustomException(
            f"Erreur lors de la recherche vectorielle : {exc}",
            status_code=500,
        )


# ──────────────────────────────────────────────────────────────
# COLLECTION PRIVÉE (documents par utilisateur)
# ──────────────────────────────────────────────────────────────

_PRIVATE_COLLECTION: str = "private_documents"


def _ensure_private_collection() -> None:
    """Crée la collection `private_documents` dans Qdrant si elle n'existe pas."""
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if _PRIVATE_COLLECTION not in existing:
        vector_size: int = _get_encoder().get_sentence_embedding_dimension()
        client.create_collection(
            collection_name=_PRIVATE_COLLECTION,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        print(f"  [Qdrant] Collection '{_PRIVATE_COLLECTION}' créée (dim={vector_size}).")


def _private_point_id(doc_id: int, chunk_index: int) -> str:
    """UUID déterministe pour un chunk privé (idempotence upsert)."""
    namespace = uuid.UUID("3a1c7e9f-2b4d-4f6a-8e0c-1d3b5a7c9e2f")
    return str(uuid.uuid5(namespace, f"priv:{doc_id}:{chunk_index}"))


def index_private_document(doc_id: int, user_id: int, text: str, filename: str) -> int:
    """
    Indexe (ou ré-indexe) un document privé utilisateur dans Qdrant.

    La collection `private_documents` est commune à tous les utilisateurs ;
    l'isolation est garantie par le champ `user_id` dans le payload,
    utilisé comme filtre lors des recherches.

    Args:
        doc_id  : Identifiant du document dans PostgreSQL (`documents.id`).
        user_id : Identifiant de l'utilisateur propriétaire.
        text    : Texte extrait du document.
        filename: Nom original du fichier.

    Returns:
        Nombre de chunks effectivement indexés.

    Raises:
        CustomException(400) — texte vide ou aucun chunk généré.
        CustomException(503) — Qdrant injoignable.
        CustomException(500) — erreur inattendue.
    """
    if not text or not text.strip():
        raise CustomException(
            f"Impossible d'indexer le document privé id={doc_id} : texte vide.",
            status_code=400,
        )

    try:
        _ensure_private_collection()
        client  = get_client()
        encoder = _get_encoder()

        # ── 1. Purge des anciens vecteurs pour ce document ──
        client.delete(
            collection_name=_PRIVATE_COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )

        # ── 2. Chunking intelligent ──
        chunks = chunk_text(text)
        if not chunks:
            raise CustomException(
                f"Aucun chunk généré pour le document privé id={doc_id}.",
                status_code=400,
            )
        total = len(chunks)

        # ── 3. Enrichissement NLP ──
        enriched: list[dict] = []
        for chunk in chunks:
            enriched.append({
                "text":        chunk,
                "description": _extract_description(chunk),
                "keywords":    _extract_keywords(chunk),
            })

        # ── 4. Embeddings (batch) ──
        vectors = encoder.encode(
            [e["text"] for e in enriched],
            show_progress_bar=False,
        ).tolist()

        # ── 5. Construction et envoi des points ──
        points = [
            PointStruct(
                id=_private_point_id(doc_id, idx),
                vector=vector,
                payload={
                    "doc_id":       doc_id,
                    "user_id":      user_id,
                    "filename":     filename,
                    "chunk":        e["text"],
                    "description":  e["description"],
                    "keywords":     e["keywords"],
                    "chunk_index":  idx,
                    "total_chunks": total,
                },
            )
            for idx, (e, vector) in enumerate(zip(enriched, vectors))
        ]

        client.upsert(collection_name=_PRIVATE_COLLECTION, points=points)

        print(
            f"  [Qdrant] Document privé indexé — id={doc_id}, user_id={user_id}, "
            f"fichier='{filename}', chunks={total}, collection='{_PRIVATE_COLLECTION}'"
        )
        return total

    except CustomException:
        raise
    except Exception as exc:
        raise CustomException(
            f"Erreur lors de l'indexation du document privé id={doc_id} : {exc}",
            status_code=500,
        )


def delete_private_document(doc_id: int) -> None:
    """
    Supprime tous les vecteurs d'un document privé dans Qdrant.

    Args:
        doc_id : Identifiant du document (`documents.id`).

    Raises:
        CustomException(503/500) en cas d'erreur Qdrant.
    """
    try:
        _ensure_private_collection()
        client = get_client()
        client.delete(
            collection_name=_PRIVATE_COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )
        print(
            f"  [Qdrant] Vecteurs privés supprimés — doc_id={doc_id}, "
            f"collection='{_PRIVATE_COLLECTION}'"
        )

    except CustomException:
        raise
    except Exception as exc:
        raise CustomException(
            f"Erreur lors de la suppression des vecteurs privés pour doc_id={doc_id} : {exc}",
            status_code=500,
        )


def search_private(query: str, user_id: int, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Recherche sémantique dans les documents privés d'un utilisateur.

    Le filtre `user_id` garantit qu'un utilisateur ne peut accéder
    qu'à ses propres documents.

    Args:
        query   : Question ou texte en langage naturel.
        user_id : Identifiant de l'utilisateur (isolation des résultats).
        top_k   : Nombre maximal de résultats (défaut : 5).

    Returns:
        Liste triée par score décroissant (mêmes champs que `search()`).

    Raises:
        CustomException(400) — requête vide.
        CustomException(503/500) — erreur Qdrant.
    """
    if not query or not query.strip():
        raise CustomException("La requête de recherche ne peut pas être vide.", status_code=400)

    try:
        _ensure_private_collection()
        client  = get_client()
        encoder = _get_encoder()

        query_vector = encoder.encode(query, show_progress_bar=False).tolist()

        result = client.query_points(
            collection_name=_PRIVATE_COLLECTION,
            query=query_vector,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "score":        round(hit.score, 4),
                "doc_id":       hit.payload.get("doc_id"),
                "filename":     hit.payload.get("filename"),
                "chunk":        hit.payload.get("chunk"),
                "description":  hit.payload.get("description"),
                "keywords":     hit.payload.get("keywords", []),
                "chunk_index":  hit.payload.get("chunk_index"),
                "total_chunks": hit.payload.get("total_chunks"),
            }
            for hit in result.points
        ]

    except CustomException:
        raise
    except Exception as exc:
        raise CustomException(
            f"Erreur lors de la recherche vectorielle privée : {exc}",
            status_code=500,
        )
