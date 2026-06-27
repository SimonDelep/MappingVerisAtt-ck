import config

from embeddings import get_embedding
from vectorstore import get_collection, query_collection


TOP_K = int(getattr(config, "TOP_K", 5))


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Recherche les chunks les plus pertinents dans ChromaDB
    à partir d'une question utilisateur.

    Étapes :
    1. Générer l'embedding de la question.
    2. Interroger ChromaDB.
    3. Retourner les chunks récupérés avec leurs métadonnées.
    """
    if not query or not query.strip():
        raise ValueError("La requête ne peut pas être vide.")

    collection = get_collection()

    query_embedding = get_embedding(query)

    results = query_collection(
        collection=collection,
        query_embedding=query_embedding,
        top_k=top_k,
    )

    return results


def print_retrieved_results(results: list[dict]) -> None:
    """
    Affiche proprement les résultats récupérés.
    Utile pour tester le retrieval avant de passer au RAG complet.
    """
    if not results:
        print("Aucun résultat récupéré.")
        return

    print("\nRésultats récupérés :")
    print("=" * 80)

    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata", {})
        source = metadata.get("source", "source inconnue")
        chunk_id = metadata.get("chunk_id", "chunk inconnu")
        distance = result.get("distance", "N/A")
        document = result.get("document", "")

        print(f"\nRésultat {index}")
        print("-" * 80)
        print(f"Source   : {source}")
        print(f"Chunk ID : {chunk_id}")
        print(f"Distance : {distance}")
        print("\nExtrait :")
        print(document[:1000])

        if len(document) > 1000:
            print("...")


if __name__ == "__main__":
    print("=" * 80)
    print("Test de recherche sémantique — NordTrail Gear")
    print("=" * 80)

    query = input("\nQuestion client : ").strip()

    results = retrieve(query=query, top_k=TOP_K)

    print_retrieved_results(results)
