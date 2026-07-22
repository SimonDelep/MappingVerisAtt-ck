"""Embeddings locaux via sentence-transformers.

`ingest.py` et `retrieve.py` n'utilisent que `embed_texts` / `embed_query`.
"""

from __future__ import annotations

import config

_st_model = None


def _get_st_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer

        print(f"  [local] chargement du modèle d'embeddings : {config.LOCAL_EMBEDDING_MODEL}")
        _st_model = SentenceTransformer(config.LOCAL_EMBEDDING_MODEL)
    return _st_model


def embed_texts(texts: list[str], batch_size: int | None = None) -> list[list[float]]:
    if not texts:
        return []
    batch_size = batch_size or config.EMBEDDING_BATCH_SIZE
    model = _get_st_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 64,
        convert_to_numpy=True,
    )
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text], batch_size=1)[0]


if __name__ == "__main__":
    vecs = embed_texts(["Test embedding VERIS vers ATT&CK."])
    print("Dimension :", len(vecs[0]))
