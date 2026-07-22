"""Couche ChromaDB pour le RAG de mapping.

Deux collections distinctes :
  - `attack_techniques` : le catalogue ATT&CK (candidats).
  - `expert_examples`   : les mappings experts des anciennes versions (exemples).

La séparation permet d'activer/désactiver le corpus d'exemples selon la
variante de RAG testée, sans toucher à l'index ATT&CK.
"""

from __future__ import annotations

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings

import config

_client: chromadb.PersistentClient | None = None


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=config.CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection(name: str) -> Collection:
    return get_client().get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine"}
    )


def reset_collection(name: str) -> Collection:
    client = get_client()
    try:
        client.delete_collection(name)
    except Exception:
        pass
    return client.create_collection(name=name, metadata={"hnsw:space": "cosine"})


def add_documents(
    collection: Collection,
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
) -> None:
    if not ids:
        return
    if not (len(ids) == len(documents) == len(embeddings) == len(metadatas)):
        raise ValueError("ids, documents, embeddings et metadatas doivent être alignés.")
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def query(
    collection: Collection,
    query_embedding: list[float],
    top_k: int,
    where: dict | None = None,
) -> list[dict]:
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    ids = results.get("ids", [[]])[0]

    return [
        {"id": i, "document": d, "metadata": m, "distance": dist}
        for i, d, m, dist in zip(ids, documents, metadatas, distances)
    ]


def count(name: str) -> int:
    return get_collection(name).count()


if __name__ == "__main__":
    print("Chroma path :", config.CHROMA_PATH)
    print("attack_techniques :", count(config.ATTACK_COLLECTION))
    print("expert_examples   :", count(config.EXAMPLES_COLLECTION))
