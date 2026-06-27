"""Pipeline RAG complet : capacités VERIS -> mapping ATT&CK -> 7 fichiers JSON.

Deux variantes (paramètre --mode) :
  - attack_only    : récupération sur le seul catalogue ATT&CK.
  - with_examples  : récupération ATT&CK + exemples de mappings experts (autres
                     versions) injectés dans le prompt.

Chaque variante écrit dans un sous-dossier distinct de Resultat/Resultat_RAG,
nommé pour être reconnu par compare_veris_mappings_v2.py.
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
from retrieve import retrieve_examples, retrieve_techniques

# Réutilise la normalisation exacte du script de comparaison officiel.
sys.path.insert(0, str(config.RESULTAT_DIR))
from compare_veris_mappings import normalize_veris_id  # noqa: E402

MODES = {
    "attack_only": f"{config.TARGET_REF}_RAG_attack_only",
    "with_examples": f"{config.TARGET_REF}_RAG_with_examples",
}


def enrich_mapping(
    attack_id: str,
    decision: dict,
    attack_index: dict,
    label: str,
) -> dict | None:
    """Construit une entrée mitre_mappings enrichie depuis le catalogue ATT&CK.

    Renvoie None si l'identifiant n'existe pas (garde-fou anti-hallucination).
    """
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
) -> dict:
    candidates = retrieve_techniques(cap.query_text())
    examples = retrieve_examples(cap.query_text()) if use_examples else []

    try:
        result = generator.generate_decision(
            group=cap.capability_group,
            label=cap.value,
            description=cap.description,
            candidates=candidates,
            examples=examples,
            attack_index=attack_index,
            use_examples=use_examples,
        )
    except Exception as error:  # robustesse : une capacité ne casse pas le lot
        print(f"    [ERREUR génération] {cap.capability_id} : {error}")
        result = {"no_mapping_found": True, "mappings": [], "notes": f"Erreur: {error}"}

    mitre_mappings: list[dict] = []
    seen: set[str] = set()
    for decision in result.get("mappings", []) or []:
        attack_id = (decision.get("attack_id") or "").strip().upper()
        if not attack_id or attack_id in seen:
            continue
        entry = enrich_mapping(attack_id, decision, attack_index, cap.value)
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


def run_mode(mode: str, limit: int | None) -> None:
    use_examples = mode == "with_examples"
    out_dir = config.RESULTAT_RAG_DIR / MODES[mode]

    print("=" * 72)
    print(f"GÉNÉRATION RAG — mode '{mode}'")
    print(f"Provider/Generator : {config.PROVIDER} / {config.GENERATOR}")
    print(f"Sortie : {out_dir}")
    print("=" * 72)

    capabilities = datasets.load_veris_capabilities()
    if limit:
        capabilities = capabilities[:limit]
    attack_index = datasets.build_attack_index()

    entries_by_group: dict[str, list[dict]] = defaultdict(list)
    for i, cap in enumerate(capabilities, start=1):
        print(f"[{i:3}/{len(capabilities)}] {cap.capability_id}")
        entry = map_capability(cap, attack_index, use_examples)
        entries_by_group[cap.capability_group].append(entry)

    print("\nÉcriture des fichiers :")
    write_results(entries_by_group, out_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Génère le mapping RAG VERIS -> ATT&CK.")
    parser.add_argument(
        "--mode",
        choices=["attack_only", "with_examples", "both"],
        default="both",
        help="Variante de RAG à générer.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre de capacités (test rapide).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config.validate_config()

    modes = ["attack_only", "with_examples"] if args.mode == "both" else [args.mode]
    for mode in modes:
        run_mode(mode, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
