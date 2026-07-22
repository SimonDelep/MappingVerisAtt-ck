"""Récupération de contexte pour une capacité VERIS.

- `retrieve_techniques` : top-k techniques ATT&CK candidates (collection ATT&CK).
- `retrieve_examples`   : top-m mappings experts similaires (anciennes versions).

`retrieve_examples` n'est appelé que par la variante de RAG "avec exemples".
"""

from __future__ import annotations

import json

import config
from embeddings import embed_query
from vectorstore import get_collection, query


def retrieve_techniques(query_text: str, top_k: int | None = None) -> list[dict]:
    top_k = top_k or config.TOP_K_TECHNIQUES
    collection = get_collection(config.ATTACK_COLLECTION)
    embedding = embed_query(query_text)
    hits = query(collection, embedding, top_k=top_k)

    candidates = []
    for hit in hits:
        meta = hit.get("metadata", {})
        candidates.append(
            {
                "attack_id": meta.get("attack_id", hit.get("id", "")),
                "name": meta.get("name", ""),
                "tactics": [t for t in (meta.get("tactics") or "").split(",") if t],
                "is_subtechnique": bool(meta.get("is_subtechnique")),
                "parent_id": meta.get("parent_id") or None,
                "distance": hit.get("distance"),
                "document": hit.get("document", ""),
            }
        )
    return candidates


def retrieve_examples(query_text: str, top_m: int | None = None) -> list[dict]:
    top_m = top_m or config.TOP_M_EXAMPLES
    collection = get_collection(config.EXAMPLES_COLLECTION)
    if collection.count() == 0:
        return []
    embedding = embed_query(query_text)
    hits = query(collection, embedding, top_k=top_m)

    examples = []
    for hit in hits:
        meta = hit.get("metadata", {})
        try:
            mapped = json.loads(meta.get("mapped_json", "[]"))
        except json.JSONDecodeError:
            mapped = []
        examples.append(
            {
                "source_version": meta.get("source_version", ""),
                "capability_group": meta.get("capability_group", ""),
                "label": meta.get("label", ""),
                "mapped": mapped,
                "mapped_summary": meta.get("mapped_summary", ""),
                "distance": hit.get("distance"),
            }
        )
    return examples


if __name__ == "__main__":
    import datasets

    cap = datasets.load_veris_capabilities()[0]
    print("Capacité :", cap.capability_id)
    print("\nCandidats ATT&CK :")
    for c in retrieve_techniques(cap.query_text(), top_k=5):
        print(f"  {c['attack_id']:12} {c['name']}  (d={c['distance']:.3f})")
    print("\nExemples experts :")
    for e in retrieve_examples(cap.query_text(), top_m=3):
        print(f"  [{e['source_version']}] {e['label']} -> {e['mapped_summary'][:80]}")
