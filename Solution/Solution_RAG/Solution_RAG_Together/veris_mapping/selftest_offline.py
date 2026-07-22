"""Smoke-test HORS-LIGNE du pipeline RAG Together (sans appeler l'API).

Remplace embeddings et LLM par des bouchons déterministes, puis exécute
ingestion -> retrieval -> génération -> écriture sur un petit échantillon.

Usage : python selftest_offline.py
"""

from __future__ import annotations

import hashlib
import struct
import tempfile
from pathlib import Path

import config

DIM = 24


def _fake_vector(text: str) -> list[float]:
    """Vecteur déterministe (pseudo-aléatoire) dérivé du texte."""
    vec: list[float] = []
    seed = text.lower().encode("utf-8")
    counter = 0
    while len(vec) < DIM:
        digest = hashlib.sha256(seed + struct.pack("I", counter)).digest()
        for i in range(0, len(digest), 4):
            if len(vec) >= DIM:
                break
            value = struct.unpack("I", digest[i : i + 4])[0]
            vec.append((value % 10000) / 10000.0)
        counter += 1
    return vec


def _fake_embed_texts(texts, batch_size=None):
    return [_fake_vector(t) for t in texts]


def _fake_embed_query(text):
    return _fake_vector(text)


def _fake_together_decision(group, label, description, candidates, examples):
    del group, label, description, examples
    mappings = []
    for c in candidates[:2]:
        aid = (c.get("attack_id") or "").strip().upper()
        if aid:
            mappings.append(
                {
                    "attack_id": aid,
                    "mapping_type": "related_to",
                    "confidence": "medium",
                    "justification": "bouchon selftest",
                }
            )
    return {
        "no_mapping_found": not mappings,
        "ambiguous": False,
        "notes": "",
        "mappings": mappings,
    }


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="rag_together_selftest_"))
    config.CHROMA_PATH = str(tmp / "chroma")
    config.RESULTAT_RAG_DIR = tmp / "out"
    config.GENERATOR = "together"
    config.TOGETHER_API_KEY = "selftest-fake-key"
    print(f"Dossier temporaire : {tmp}")

    import embeddings
    import generator
    import ingest
    import retrieve
    import generate_mapping  # noqa: F401

    embeddings.embed_texts = _fake_embed_texts
    embeddings.embed_query = _fake_embed_query
    ingest.embed_texts = _fake_embed_texts
    retrieve.embed_query = _fake_embed_query
    generator._together_decision = _fake_together_decision

    print("\n--- Ingestion (bouchon) ---")
    ingest.ingest_attack()
    ingest.ingest_examples()

    print("\n--- Génération (bouchon, 6 capacités) ---")
    generate_mapping.run_mode("with_examples", limit=6)

    out_dir = config.RESULTAT_RAG_DIR / generate_mapping.MODES["with_examples"]
    files = sorted(out_dir.glob("*.json"))
    print(f"\nFichiers écrits : {len(files)}")
    assert len(files) == len(config.CAPABILITY_GROUPS), "Il manque des fichiers de scope."

    import json

    total = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["metadata"]["scope"] == path.stem
        total += len(data["veris_to_mitre"])
    print(f"Entrées veris_to_mitre totales : {total}")
    print("\nSMOKE-TEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
