"""Ingestion des corpus vectoriels du RAG de mapping.

Indexe (une seule fois) :
  1. le catalogue ATT&CK cible      -> collection `attack_techniques`
  2. les exemples experts anciens   -> collection `expert_examples`

Les deux variantes de RAG (avec / sans exemples) partagent ce même index :
seul le *retrieval* décide d'interroger ou non la collection d'exemples.

Anti-fuite : les exemples proviennent uniquement des versions != cible.
"""

from __future__ import annotations

import json

import config
import datasets
from embeddings import embed_texts
from vectorstore import add_documents, count, reset_collection


def ingest_attack() -> int:
    techniques = datasets.load_attack_techniques()
    print(f"\n[ATT&CK] {len(techniques)} techniques -> {config.ATTACK_COLLECTION}")

    documents = [t.document_text() for t in techniques]
    embeddings = embed_texts(documents)

    ids = [t.attack_id for t in techniques]
    metadatas = [
        {
            "attack_id": t.attack_id,
            "name": t.name,
            "tactics": ",".join(t.tactics),
            "is_subtechnique": t.is_subtechnique,
            "parent_id": t.parent_id or "",
        }
        for t in techniques
    ]

    collection = reset_collection(config.ATTACK_COLLECTION)
    add_documents(collection, ids, documents, embeddings, metadatas)
    return len(techniques)


def ingest_examples() -> int:
    examples = datasets.load_expert_examples()
    print(f"\n[EXEMPLES] {len(examples)} capacités -> {config.EXAMPLES_COLLECTION}")

    documents = [ex.document_text() for ex in examples]
    embeddings = embed_texts(documents)

    ids = [f"{ex.source_version}::{ex.capability_id}" for ex in examples]
    metadatas = [
        {
            "source_version": ex.source_version,
            "capability_group": ex.capability_group,
            "label": ex.label,
            "mapped_json": json.dumps(ex.mapped, ensure_ascii=False),
            "mapped_summary": ex.mapped_summary(),
        }
        for ex in examples
    ]

    collection = reset_collection(config.EXAMPLES_COLLECTION)
    add_documents(collection, ids, documents, embeddings, metadatas)
    return len(examples)


def main() -> None:
    config.validate_config()
    print("=" * 72)
    print("INGESTION RAG — mapping VERIS -> ATT&CK")
    print("=" * 72)
    print(f"Version cible : {config.TARGET_REF}")
    print(f"Chroma path   : {config.CHROMA_PATH}")

    n_attack = ingest_attack()
    n_examples = ingest_examples()

    print("\n" + "=" * 72)
    print("INGESTION TERMINÉE")
    print(f"  attack_techniques : {count(config.ATTACK_COLLECTION)} (attendu {n_attack})")
    print(f"  expert_examples   : {count(config.EXAMPLES_COLLECTION)} (attendu {n_examples})")


if __name__ == "__main__":
    main()
