"""
Recherche documentaire via Azure AI Search (hybride texte + vecteur).
"""

from __future__ import annotations

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

import config
from embeddings import get_embedding

TOP_K = int(getattr(config, "TOP_K", 5))

EXCLUDED_SOURCES = {"emails_clients_test.csv"}


def _get_search_client() -> SearchClient:
    if not config.SEARCH_API_KEY:
        raise ValueError(
            "AZURE_SEARCH_API_KEY manquant. Définissez-la dans dev.env."
        )
    return SearchClient(
        endpoint=config.SEARCH_ENDPOINT,
        index_name=config.SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(config.SEARCH_API_KEY),
    )


def _parse_source(text: str, doc_id: str) -> str:
    if ": " in text:
        prefix = text.split(": ", 1)[0].strip()
        if "." in prefix:
            return prefix
    if "_chunk_" in doc_id:
        return doc_id.rsplit("_chunk_", 1)[0]
    return doc_id


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Recherche les chunks les plus pertinents dans Azure AI Search.

    Retourne le même format que retrieve.py (Chroma) pour réutiliser build_context.
    """
    if not query or not query.strip():
        raise ValueError("La requête ne peut pas être vide.")

    client = _get_search_client()
    query_embedding = get_embedding(query)

    vector_query = VectorizedQuery(
        vector=query_embedding,
        k_nearest_neighbors=top_k,
        fields="vector",
    )

    results = client.search(
        search_text=query,
        vector_queries=[vector_query],
        top=top_k,
    )

    retrieved_chunks: list[dict] = []

    for doc in results:
        doc_id = doc.get("id", "")
        text = doc.get("text", "")
        source = _parse_source(text, doc_id)

        if source in EXCLUDED_SOURCES:
            continue

        document_body = text.split(": ", 1)[1] if ": " in text else text

        retrieved_chunks.append(
            {
                "id": doc_id,
                "document": document_body,
                "metadata": {
                    "source": source,
                    "chunk_id": doc_id,
                },
                "distance": doc.get("@search.score"),
            }
        )

    return retrieved_chunks
