"""Pipeline RAG multi-LLM : capacités VERIS -> mapping ATT&CK -> 7 JSON.

Retrieval local (ChromaDB + MiniLM) + décision par un LLM cloud (parmi les
modèles de la phase 1). Sorties sous Resultat/Resultat_RAG_MultiLLM/.

Modes :
  - attack_only
  - with_examples

Usage :
  python generate_mapping.py --mode with_examples --model meta-llama/Llama-3.3-70B-Instruct-Turbo
  python generate_mapping.py --mode both --model Qwen/Qwen2.5-7B-Instruct-Turbo --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import config
import datasets
import generator
from prompt import CONFIDENCE_SCORES
from retrieve import merge_candidates_with_examples, retrieve_examples, retrieve_techniques

sys.path.insert(0, str(config.RESULTAT_DIR))
from compare_veris_mappings import normalize_veris_id  # noqa: E402


def mode_dirname(mode: str, model_id: str, tag: str | None = None) -> str:
    slug = config.model_slug(model_id)
    base = f"{config.TARGET_REF}_RAG_MultiLLM_{slug}_{mode}"
    if tag:
        return f"{base}_{tag}"
    return base


def enrich_mapping(
    attack_id: str,
    decision: dict,
    attack_index: dict,
) -> dict | None:
    """Construit une entrée mitre_mappings enrichie (anti-hallucination catalogue)."""
    attack_id = (attack_id or "").strip().upper()
    if attack_id not in attack_index:
        return None

    tech = attack_index[attack_id]
    if tech.is_subtechnique:
        parent = attack_index.get(tech.parent_id)
        technique_id = tech.parent_id
        technique_name = parent.name if parent else ""
        sub_technique_id = attack_id
        sub_technique_name = tech.name
    else:
        technique_id = attack_id
        technique_name = tech.name
        sub_technique_id = None
        sub_technique_name = None

    confidence = str(decision.get("confidence", "medium")).lower()
    if confidence not in CONFIDENCE_SCORES:
        confidence = "medium"

    return {
        "technique_id": technique_id,
        "technique_name": technique_name,
        "sub_technique_id": sub_technique_id,
        "sub_technique_name": sub_technique_name,
        "tactic(s)": tech.tactics,
        "mapping_type": decision.get("mapping_type", "related_to") or "related_to",
        "confidence": confidence,
        "confidence_score": CONFIDENCE_SCORES[confidence],
        "justification": decision.get("justification", "") or "",
    }


def map_capability(
    cap: datasets.VerisCapability,
    attack_index: dict,
    use_examples: bool,
    model_id: str,
) -> dict:
    candidates = retrieve_techniques(cap.query_text())
    examples = retrieve_examples(cap.query_text()) if use_examples else []
    if use_examples and examples:
        candidates = merge_candidates_with_examples(
            candidates, examples, attack_index
        )

    try:
        result = generator.generate_decision(
            group=cap.capability_group,
            label=cap.value,
            description=cap.description,
            candidates=candidates,
            examples=examples,
            attack_index=attack_index,
            use_examples=use_examples,
            model=model_id,
        )
    except Exception as error:
        print(f"    [ERREUR génération] {cap.capability_id} : {error}")
        result = {
            "no_mapping_found": True,
            "mappings": [],
            "notes": f"Erreur: {error}",
        }

    mitre_mappings: list[dict] = []
    seen: set[str] = set()
    for decision in result.get("mappings", []) or []:
        attack_id = (decision.get("attack_id") or "").strip().upper()
        if not attack_id or attack_id in seen:
            continue
        entry = enrich_mapping(attack_id, decision, attack_index)
        if entry is not None:
            mitre_mappings.append(entry)
            seen.add(attack_id)

    mitre_mappings.sort(key=lambda m: (m["technique_id"], m["sub_technique_id"] or ""))
    no_mapping = not mitre_mappings

    return {
        "veris_id": normalize_veris_id(cap.capability_id),
        "veris_category": cap.capability_group.split(".", 1)[1].capitalize(),
        "veris_label": cap.value,
        "no_mapping_found": no_mapping,
        "mitre_mappings": mitre_mappings,
        "ambiguous": bool(result.get("ambiguous", False)),
        "notes": result.get("notes", "")
        or ("Aucune correspondance trouvée." if no_mapping else ""),
    }


def write_results(entries_by_group: dict[str, list[dict]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for group in config.CAPABILITY_GROUPS:
        entries = sorted(entries_by_group.get(group, []), key=lambda e: e["veris_id"])
        payload = {
            "metadata": {
                "veris_version": config.VERIS_VERSION,
                "mitre_attack_version": config.ATTACK_VERSION,
                "scope": group,
            },
            "veris_to_mitre": entries,
        }
        out_path = out_dir / f"{group}.json"
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        mapped = sum(1 for e in entries if not e["no_mapping_found"])
        print(f"  {group:28} -> {len(entries):3} capacités ({mapped} mappées)")


def run_mode(
    mode: str,
    model_id: str,
    limit: int | None,
    tag: str | None = None,
) -> Path:
    use_examples = mode == "with_examples"
    out_dir = config.RESULTAT_RAG_DIR / mode_dirname(mode, model_id, tag=tag)

    print("=" * 72)
    print(f"GÉNÉRATION RAG MultiLLM — mode '{mode}'")
    print(f"Modèle    : {model_id}")
    print(f"top_k     : {config.TOP_K_TECHNIQUES}")
    print(f"top_m     : {config.TOP_M_EXAMPLES}")
    print(f"max_cand  : {config.MAX_PROMPT_CANDIDATES}")
    if tag:
        print(f"tag       : {tag}")
    print(f"Sortie    : {out_dir}")
    print("=" * 72)

    capabilities = datasets.load_veris_capabilities()
    if limit:
        capabilities = capabilities[:limit]
    attack_index = datasets.build_attack_index()

    entries_by_group: dict[str, list[dict]] = defaultdict(list)
    for i, cap in enumerate(capabilities, start=1):
        print(f"[{i:3}/{len(capabilities)}] {cap.capability_id}", flush=True)
        entry = map_capability(cap, attack_index, use_examples, model_id)
        entries_by_group[cap.capability_group].append(entry)

    print("\nÉcriture des fichiers :")
    write_results(entries_by_group, out_dir)
    return out_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Génère le mapping RAG multi-LLM VERIS -> ATT&CK."
    )
    parser.add_argument(
        "--mode",
        choices=["attack_only", "with_examples", "both"],
        default="with_examples",
        help="Variante de retrieval (défaut: with_examples).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Id du modèle LLM (défaut: premier de RAG_MULTI_LLM_MODELS).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre de capacités (test rapide).",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Suffixe de dossier de sortie (ex: v2) pour ne pas écraser une run précédente.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config.validate_config()

    model_id = (args.model or config.TOGETHER_CHAT_MODEL).strip()
    if not model_id:
        raise SystemExit("Aucun modèle : passez --model ou RAG_MULTI_LLM_MODELS.")

    modes = ["attack_only", "with_examples"] if args.mode == "both" else [args.mode]
    for mode in modes:
        run_mode(mode, model_id, args.limit, tag=args.tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
