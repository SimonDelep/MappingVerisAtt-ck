#!/usr/bin/env python3
"""Complète les fichiers d'exemple veris_to_mitre par capability_group.

À partir du mapping officiel des experts (format CTID, clé "mapping_objects")
et du catalogue ATT&CK local, on génère un fichier JSON par capability_group
au format `veris_to_mitre` (identique à l'exemple action.hacking.json).

Les paires VERIS -> ATT&CK proviennent intégralement des experts : ces fichiers
constituent donc un résultat "parfait" (référence) au format attendu par
Resultat/compare_veris_mappings.py.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTAT = ROOT / "Resultat"
EXPERTS = RESULTAT / "Mapping_des_experts" / "veris-1.4.1_attack-19.1-enterprise_json.json"
ATTACK_CATALOG = (
    ROOT / "data_for_work" / "attack-19.1_veris-1.4.1" / "attack_19.1.json"
)
OUT_DIR = (
    RESULTAT / "Resultat_Exemple" / "veris-1.4.1_attack-19.1-enterprise_Exemple"
)

VERIS_VERSION = "1.4.1"
ATTACK_VERSION = "19.1"

# On ne (re)génère pas action.hacking.json : il sert d'exemple de référence.
SKIP_GROUPS = {"action.hacking"}

# Réutilise la normalisation exacte du script de comparaison.
sys.path.insert(0, str(RESULTAT))
from compare_veris_mappings import normalize_veris_id  # noqa: E402


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_attack_index() -> dict[str, dict]:
    catalog = load_json(ATTACK_CATALOG)
    return {t["attack_id"]: t for t in catalog["techniques"]}


def veris_label_from_capability_id(capability_id: str) -> str:
    parts = capability_id.split(".")
    remainder = parts[2:]  # retire axis.category
    if remainder and remainder[0].lower() in {"variety", "vector"}:
        remainder = remainder[1:]
    return ".".join(remainder)


def make_mapping_entry(attack_id: str, attack_name: str, index: dict, label: str) -> dict:
    is_sub = "." in attack_id
    if is_sub:
        parent_id = attack_id.split(".")[0]
        technique_id = parent_id
        technique_name = index.get(parent_id, {}).get("name", "")
        sub_technique_id = attack_id
        sub_technique_name = attack_name or index.get(attack_id, {}).get("name", "")
        display_name = sub_technique_name
    else:
        technique_id = attack_id
        technique_name = attack_name or index.get(attack_id, {}).get("name", "")
        sub_technique_id = None
        sub_technique_name = None
        display_name = technique_name

    tactics = index.get(attack_id, {}).get("tactics", [])

    return {
        "technique_id": technique_id,
        "technique_name": technique_name,
        "sub_technique_id": sub_technique_id,
        "sub_technique_name": sub_technique_name,
        "tactic(s)": tactics,
        "mapping_type": "related_to",
        "confidence": "high",
        "confidence_score": 1.0,
        "justification": f"Correspondance des experts entre {label} et {display_name}.",
    }


def main() -> None:
    experts = load_json(EXPERTS)
    index = build_attack_index()

    # Regroupe les objets experts par capability_group puis par capability_id.
    groups: dict[str, "OrderedDict[str, dict]"] = {}
    for obj in experts["mapping_objects"]:
        group = obj.get("capability_group")
        if not group or group in SKIP_GROUPS:
            continue
        capability_id = obj.get("capability_id", "")
        caps = groups.setdefault(group, OrderedDict())
        entry = caps.setdefault(
            capability_id,
            {
                "veris_id": normalize_veris_id(capability_id),
                "veris_category": group.split(".", 1)[1].capitalize(),
                "veris_label": veris_label_from_capability_id(capability_id),
                "no_mapping_found": True,
                "mitre_mappings": [],
                "ambiguous": False,
                "notes": "",
            },
        )

        attack_id = (obj.get("attack_object_id") or "").strip()
        if not attack_id:
            continue
        entry["mitre_mappings"].append(
            make_mapping_entry(
                attack_id, obj.get("attack_object_name", ""), index,
                entry["veris_label"],
            )
        )
        entry["no_mapping_found"] = False

    for group, caps in groups.items():
        entries = list(caps.values())
        for entry in entries:
            entry["mitre_mappings"].sort(
                key=lambda m: (m["technique_id"], m["sub_technique_id"] or "")
            )
            if entry["no_mapping_found"]:
                entry["notes"] = "Aucune correspondance trouvée."
        entries.sort(key=lambda e: e["veris_id"])

        payload = {
            "metadata": {
                "veris_version": VERIS_VERSION,
                "mitre_attack_version": ATTACK_VERSION,
                "scope": group,
            },
            "veris_to_mitre": entries,
        }
        out_path = OUT_DIR / f"{group}.json"
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))

        mapped = sum(1 for e in entries if not e["no_mapping_found"])
        print(
            f"{group:28} -> {len(entries):3} capacités "
            f"({mapped} mappées, {len(entries) - mapped} sans mapping)"
        )


if __name__ == "__main__":
    main()
