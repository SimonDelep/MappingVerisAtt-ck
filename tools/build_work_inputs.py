#!/usr/bin/env python3
"""Génère, pour chaque version, les 2 entrées du mapping pour la solution IA.

Pour chaque paire (ATT&CK, VERIS) on écrit dans data_for_work/attack-<a>_veris-<v>/ :
  - veris_<v>.json   : capacités VERIS en scope (les "questions" à mapper)
  - attack_<a>.json  : techniques/sous-techniques ATT&CK (les "candidats")

Sources :
  - VERIS  : data/raw/veris/<v>/verisc-enum.json + verisc-labels.json
  - ATT&CK : data/raw/attack/<a>/enterprise-attack.json

Ce sont exactement les deux référentiels que les experts confrontent pour
produire le mapping (cf. méthodologie CTID / Mappings Explorer).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIS_RAW = ROOT / "data" / "raw" / "veris"
ATTACK_RAW = ROOT / "data" / "raw" / "attack"
WORK_DIR = ROOT / "data_for_work"

# (attack_version, veris_version)
PAIRS = [
    ("9.0", "1.3.5"),
    ("12.1", "1.3.7"),
    ("16.1", "1.4.0"),
    ("19.1", "1.4.1"),
]

# Groupes VERIS "comportementaux" mappés vers ATT&CK et leurs sous-catégories.
# (cf. les 7 capability_groups officiels du Mappings Explorer)
SCOPE_SUBCATEGORIES = {
    "action.hacking": ["variety", "vector"],
    "action.malware": ["variety", "vector"],
    "action.social": ["variety", "vector"],
    "attribute.integrity": ["variety"],
    "attribute.availability": ["variety"],
    "value_chain.development": ["variety"],
}

# attribute.confidentiality est un cas particulier : les experts mappent le
# champ "data_disclosure" lui-même (et non des valeurs sous "variety").
CONFIDENTIALITY_GROUP = "attribute.confidentiality"
CONFIDENTIALITY_FIELD = "data_disclosure"

SCOPE_GROUPS = list(SCOPE_SUBCATEGORIES) + [CONFIDENTIALITY_GROUP]


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def get_nested(tree: dict, *keys: str):
    """Descend dans un dict imbriqué, renvoie None si un niveau manque."""
    node = tree
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def extract_veris(veris_version: str) -> dict:
    enum = load_json(VERIS_RAW / veris_version / "verisc-enum.json")
    labels = load_json(VERIS_RAW / veris_version / "verisc-labels.json")

    capabilities: list[dict] = []

    for group, subcats in SCOPE_SUBCATEGORIES.items():
        axis, category = group.split(".", 1)
        for subcat in subcats:
            values = get_nested(enum, axis, category, subcat)
            if not isinstance(values, list):
                continue
            label_map = get_nested(labels, axis, category, subcat) or {}
            for value in values:
                capabilities.append(
                    {
                        "capability_id": f"{axis}.{category}.{subcat}.{value}",
                        "capability_group": group,
                        "value": value,
                        "description": label_map.get(value, value)
                        if isinstance(label_map, dict)
                        else value,
                    }
                )

    # Cas particulier confidentiality -> champ data_disclosure
    axis, category = CONFIDENTIALITY_GROUP.split(".", 1)
    if get_nested(enum, axis, category, CONFIDENTIALITY_FIELD) is not None:
        capabilities.append(
            {
                "capability_id": f"{CONFIDENTIALITY_GROUP}.{CONFIDENTIALITY_FIELD}",
                "capability_group": CONFIDENTIALITY_GROUP,
                "value": CONFIDENTIALITY_FIELD,
                "description": "",
            }
        )

    capabilities.sort(key=lambda c: c["capability_id"])
    return {
        "framework": "veris",
        "version": veris_version,
        "scope_groups": SCOPE_GROUPS,
        "capability_count": len(capabilities),
        "capabilities": capabilities,
    }


def extract_attack(attack_version: str) -> dict:
    bundle = load_json(ATTACK_RAW / attack_version / "enterprise-attack.json")

    techniques: list[dict] = []
    for obj in bundle.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue

        attack_id = None
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack" and ref.get("external_id"):
                attack_id = ref["external_id"]
                break
        if not attack_id:
            continue

        tactics = [
            phase["phase_name"]
            for phase in obj.get("kill_chain_phases", [])
            if phase.get("kill_chain_name") == "mitre-attack"
        ]
        is_sub = bool(obj.get("x_mitre_is_subtechnique"))

        techniques.append(
            {
                "attack_id": attack_id,
                "name": obj.get("name", ""),
                "description": obj.get("description", ""),
                "tactics": tactics,
                "is_subtechnique": is_sub,
                "parent_id": attack_id.split(".")[0] if is_sub else None,
            }
        )

    techniques.sort(key=lambda t: t["attack_id"])
    return {
        "framework": "mitre_attack",
        "domain": "enterprise",
        "version": attack_version,
        "technique_count": len(techniques),
        "techniques": techniques,
    }


def main() -> None:
    for attack_version, veris_version in PAIRS:
        out_dir = WORK_DIR / f"attack-{attack_version}_veris-{veris_version}"

        veris_data = extract_veris(veris_version)
        attack_data = extract_attack(attack_version)

        veris_path = out_dir / f"veris_{veris_version}.json"
        attack_path = out_dir / f"attack_{attack_version}.json"
        dump_json(veris_data, veris_path)
        dump_json(attack_data, attack_path)

        print(
            f"[VERIS {veris_version} / ATT&CK {attack_version}] "
            f"{veris_data['capability_count']:4} capacités VERIS | "
            f"{attack_data['technique_count']:4} techniques ATT&CK"
        )
        print(f"   -> {veris_path.relative_to(ROOT)}")
        print(f"   -> {attack_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
