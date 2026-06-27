from typing import List
from openai import AzureOpenAI

from config import (
    OPENAI_API_KEY,
    OPENAI_ENDPOINT,
    OPENAI_API_VERSION,
    OPENAI_EMBEDDING_MODEL,
)


def get_azure_client() -> AzureOpenAI:
    """
    Crée le client Azure OpenAI à partir des variables chargées dans config.py.
    Les clés API restent dans dev.env et ne sont jamais écrites dans le code.
    """
    if not OPENAI_API_KEY:
        raise ValueError("Clé API manquante : vérifie AZURE_OPENAI_API_KEY dans dev.env")

    if not OPENAI_ENDPOINT:
        raise ValueError("Endpoint manquant : vérifie AZURE_OPENAI_ENDPOINT dans dev.env")

    return AzureOpenAI(
        api_key=OPENAI_API_KEY,
        azure_endpoint=OPENAI_ENDPOINT,
        api_version=OPENAI_API_VERSION,
    )


def get_embedding(text: str) -> List[float]:
    """
    Génère l'embedding d'un texte avec le deployment Azure configuré.

    Attention :
    OPENAI_EMBEDDING_MODEL doit être le nom du deployment Azure,
    pas seulement le nom du modèle.
    """
    if not text or not text.strip():
        raise ValueError("Impossible de créer un embedding pour un texte vide.")

    client = get_azure_client()

    response = client.embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=text,
    )

    return response.data[0].embedding


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Génère les embeddings pour une liste de textes.

    Version simple : un appel API par texte.
    C'est plus lent qu'un batch complet, mais plus facile à debugger
    pour une première version du projet.
    """
    embeddings = []

    for index, text in enumerate(texts, start=1):
        print(f"Embedding {index}/{len(texts)}")
        embedding = get_embedding(text)
        embeddings.append(embedding)

    return embeddings


if __name__ == "__main__":
    test_text = "NordTrail Gear accepte les retours sous conditions."
    embedding = get_embedding(test_text)

    print("Embedding généré avec succès.")
    print(f"Dimension : {len(embedding)}")
