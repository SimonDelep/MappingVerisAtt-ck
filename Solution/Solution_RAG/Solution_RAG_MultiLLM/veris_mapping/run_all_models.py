"""Lance le pipeline MultiLLM sur tous les modèles de RAG_MULTI_LLM_MODELS.

Usage (depuis veris_mapping/) :
  python run_all_models.py --mode with_examples
  python run_all_models.py --mode both --limit 5
  python run_all_models.py --models meta-llama/Llama-3.3-70B-Instruct-Turbo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config
from generate_mapping import run_mode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exécute generate_mapping pour chaque modèle multi-LLM."
    )
    parser.add_argument(
        "--mode",
        choices=["attack_only", "with_examples", "both"],
        default="with_examples",
        help="Mode(s) de retrieval.",
    )
    parser.add_argument(
        "--models",
        default=None,
        help="Liste CSV de modèles (défaut: RAG_MULTI_LLM_MODELS).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite capacités par run (smoke test).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config.validate_config()

    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        models = list(config.MULTI_LLM_MODELS)

    if not models:
        print("Aucun modèle à exécuter.", file=sys.stderr)
        return 1

    modes = ["attack_only", "with_examples"] if args.mode == "both" else [args.mode]

    print("Modèles :", models)
    print("Modes   :", modes)
    print("Limit   :", args.limit or "(toutes les capacités)")

    outputs: list[Path] = []
    for model_id in models:
        for mode in modes:
            out = run_mode(mode, model_id, args.limit)
            outputs.append(out)

    print("\n" + "=" * 72)
    print("Terminé. Sorties :")
    for path in outputs:
        print(f"  - {path}")
    print()
    print("Évaluation (depuis la racine SIEM) :")
    print(
        "  python Resultat/compare_veris_mappings_v2.py "
        "--solutions Resultat_RAG_MultiLLM"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
