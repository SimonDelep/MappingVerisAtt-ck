"""Embeddings : backend local (sentence-transformers) ou Azure OpenAI.

Le backend est choisi via config.PROVIDER :
  - "local" : sentence-transformers, 100% hors-ligne (après téléchargement initial).
  - "azure" : Azure OpenAI (appels par lots).

`ingest.py` et `retrieve.py` n'utilisent que `embed_texts` / `embed_query`
et n'ont donc pas à connaître le backend.
"""

from __future__ import annotations

import config

# ----- Backend local : sentence-transformers -----
_st_model = None


def _get_st_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer

        print(f"  [local] chargement du modèle d'embeddings : {config.LOCAL_EMBEDDING_MODEL}")
        _st_model = SentenceTransformer(config.LOCAL_EMBEDDING_MODEL)
    return _st_model


def _local_embed(texts: list[str]) -> list[list[float]]:
    model = _get_st_model()
    vectors = model.encode(
        texts,
        batch_size=config.EMBEDDING_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 64,
        convert_to_numpy=True,
    )
    return vectors.tolist()


# ----- Backend Azure OpenAI -----
_azure_client = None


def get_azure_client():
    global _azure_client
    if _azure_client is None:
        from openai import AzureOpenAI

        if not config.OPENAI_API_KEY:
            raise ValueError(
                "Clé API manquante : vérifiez AZURE_OPENAI_API_KEY dans dev.env."
            )
        _azure_client = AzureOpenAI(
            api_key=config.OPENAI_API_KEY,
            azure_endpoint=config.OPENAI_ENDPOINT,
            api_version=config.OPENAI_API_VERSION,
        )
    return _azure_client


def _azure_embed(texts: list[str], batch_size: int) -> list[list[float]]:
    client = get_azure_client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = [t if t and t.strip() else " " for t in texts[start : start + batch_size]]
        response = client.embeddings.create(
            model=config.OPENAI_EMBEDDING_MODEL,
            input=batch,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors.extend(item.embedding for item in ordered)
        print(f"  embeddings {min(start + batch_size, len(texts))}/{len(texts)}")
    return vectors


# ----- API publique -----
def embed_texts(texts: list[str], batch_size: int | None = None) -> list[list[float]]:
    if not texts:
        return []
    batch_size = batch_size or config.EMBEDDING_BATCH_SIZE
    if config.PROVIDER == "azure":
        return _azure_embed(texts, batch_size)
    return _local_embed(texts)


def embed_query(text: str) -> list[float]:
    return embed_texts([text], batch_size=1)[0]


if __name__ == "__main__":
    vecs = embed_texts(["Test embedding VERIS vers ATT&CK."])
    print("Provider :", config.PROVIDER)
    print("Dimension :", len(vecs[0]))
