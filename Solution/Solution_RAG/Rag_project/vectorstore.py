import shutil
import threading
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings

from config import CHROMA_COLLECTION, CHROMA_PATH

_chroma_lock = threading.RLock()
_chroma_client: Optional["chromadb.PersistentClient"] = None
_chroma_collection: Optional[Collection] = None


def _chroma_settings() -> Settings:
    return Settings(anonymized_telemetry=False)


def _invalidate_chroma_cache() -> None:
    """Réinitialise le singleton en mémoire (ingestion / reset uniquement)."""
    global _chroma_client, _chroma_collection
    with _chroma_lock:
        _chroma_client = None
        _chroma_collection = None


def get_chroma_client() -> chromadb.PersistentClient:
    """
    Client ChromaDB persistant partagé (une instance par processus).
    """
    global _chroma_client
    with _chroma_lock:
        if _chroma_client is None:
            _chroma_client = chromadb.PersistentClient(
                path=CHROMA_PATH,
                settings=_chroma_settings(),
            )
        return _chroma_client


def get_collection() -> Collection:
    """
    Récupère ou crée la collection ChromaDB utilisée par le RAG.
    """
    global _chroma_collection
    with _chroma_lock:
        if _chroma_collection is None:
            client = get_chroma_client()
            _chroma_collection = client.get_or_create_collection(
                name=CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        return _chroma_collection


def reset_collection() -> Collection:
    """
    Supprime puis recrée la collection et la base SQLite ChromaDB.
    """
    global _chroma_client, _chroma_collection
    _invalidate_chroma_cache()

    chroma_dir = Path(CHROMA_PATH)
    if chroma_dir.exists():
        try:
            shutil.rmtree(chroma_dir)
        except PermissionError as exc:
            raise RuntimeError(
                f"Impossible de supprimer {chroma_dir}. "
                "Fermez Streamlit et les autres processus utilisant ChromaDB, puis relancez l'ingestion."
            ) from exc
    chroma_dir.mkdir(parents=True, exist_ok=True)

    try:
        chromadb.api.client.SharedSystemClient.clear_system_cache()
    except Exception:
        pass

    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=_chroma_settings(),
    )
    collection = client.create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    with _chroma_lock:
        _chroma_client = client
        _chroma_collection = collection

    print(f"Collection créée : {CHROMA_COLLECTION}")
    return collection


def add_chunks(
    collection: Collection,
    chunks: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
    ids: list[str],
) -> None:
    """
    Ajoute des chunks dans ChromaDB avec leurs embeddings et métadonnées.
    """
    if not chunks:
        raise ValueError("Aucun chunk à ajouter.")

    if not (len(chunks) == len(embeddings) == len(metadatas) == len(ids)):
        raise ValueError(
            "Les listes chunks, embeddings, metadatas et ids doivent avoir la même longueur."
        )

    collection.add(
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )


def query_collection(
    collection: Collection,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Recherche les chunks les plus proches d'une requête.
    """
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    ids = results.get("ids", [[]])[0]

    retrieved_chunks = []

    for doc_id, document, metadata, distance in zip(
        ids, documents, metadatas, distances
    ):
        retrieved_chunks.append(
            {
                "id": doc_id,
                "document": document,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return retrieved_chunks


def count_chunks(collection: Collection) -> int:
    """
    Retourne le nombre de chunks stockés dans la collection.
    """
    return collection.count()


if __name__ == "__main__":
    collection = get_collection()

    print("Connexion à ChromaDB réussie.")
    print(f"Chemin ChromaDB : {CHROMA_PATH}")
    print(f"Collection : {CHROMA_COLLECTION}")
    print(f"Nombre de chunks indexés : {count_chunks(collection)}")
