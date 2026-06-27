import chromadb
from chromadb.api.models.Collection import Collection

from config import CHROMA_PATH, CHROMA_COLLECTION


def get_chroma_client() -> chromadb.PersistentClient:
    """
    Crée un client ChromaDB persistant.

    Les données vectorielles sont stockées localement dans CHROMA_PATH.
    Exemple : ./db/chroma_store
    """
    return chromadb.PersistentClient(path=CHROMA_PATH)


def get_collection() -> Collection:
    """
    Récupère ou crée la collection ChromaDB utilisée par le RAG.

    La distance cosine est adaptée aux embeddings OpenAI/Azure OpenAI.
    """
    client = get_chroma_client()

    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    return collection


def reset_collection() -> Collection:
    """
    Supprime puis recrée la collection.

    À utiliser pendant l'ingestion pour repartir d'une base propre.
    Attention : cela efface les anciens chunks indexés.
    """
    client = get_chroma_client()

    try:
        client.delete_collection(name=CHROMA_COLLECTION)
        print(f"Collection supprimée : {CHROMA_COLLECTION}")
    except Exception:
        print(f"Aucune collection existante à supprimer : {CHROMA_COLLECTION}")

    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

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
