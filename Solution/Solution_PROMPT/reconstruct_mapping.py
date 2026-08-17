#!/usr/bin/env python3
"""Reconstruit un mapping complet à partir des JSON LLM (IDs seulement).

Entrée typique (brut LLM) :
  {"veris_id": "...", "no_mapping_found": false, "attack_ids": ["T1110", "T1110.001"]}

Sortie enrichie (alignée Exemple / RAG) :
  veris_label, technique_name, tactics, mitre_to_veris inversé, etc.

Usage :
  python reconstruct_mapping.py \\
    -i ../../Resultat/Resultat_PROMPT/veris-1.4.1_attack-19.1-enterprise_PROMPT_Kimi-K3 \\
    -dw ../../data_for_work/attack-19.1_veris-1.4.1

  # ou chemins explicites
  python reconstruct_mapping.py -i <dir_brut> -a attack_19.1.json -v veris_1.4.1.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CAPABILITY = [
    "action.hacking",
    "action.malware",
    "attribute.integrity",
    "attribute.confidentiality",
    "attribute.availability",
    "action.social",
    "value_chain.development",
]

CONFIDENCE_SCORES = {"high": 1.0, "medium": 0.6, "low": 0.3}
DEFAULT_DB = Path(__file__).resolve().parents[2] / "data_for_work" / "attack-19.1_veris-1.4.1"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_veris_index(veris_data: dict) -> dict[str, dict]:
    return {c["capability_id"]: c for c in veris_data.get("capabilities", [])}


def build_attack_index(attack_data: dict) -> dict[str, dict]:
    idx = {}
    for t in attack_data.get("techniques", []):
        aid = (t.get("attack_id") or "").strip().upper()
        if aid:
            idx[aid] = t
    return idx


def category_from_group(group: str) -> str:
    # action.hacking -> Hacking ; attribute.availability -> Availability
    if "." in group:
        return group.split(".", 1)[1].replace("_", " ").title().replace(" ", "")
    return group


def extract_attack_ids(entry: dict) -> list[str]:
    """Accepte le schéma minimal (attack_ids) ou l'ancien (mitre_mappings)."""
    ids: list[str] = []
    if isinstance(entry.get("attack_ids"), list):
        for a in entry["attack_ids"]:
            if isinstance(a, str) and a.strip():
                ids.append(a.strip().upper())
            elif isinstance(a, dict):
                aid = (a.get("attack_id") or a.get("technique_id") or "").strip().upper()
                if aid:
                    ids.append(aid)
    for m in entry.get("mitre_mappings") or []:
        if not isinstance(m, dict):
            continue
        aid = (m.get("attack_id") or m.get("sub_technique_id") or m.get("technique_id") or "")
        aid = str(aid).strip().upper()
        if aid:
            ids.append(aid)
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for a in ids:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def enrich_attack_id(attack_id: str, attack_index: dict) -> dict | None:
    attack_id = (attack_id or "").strip().upper()
    tech = attack_index.get(attack_id)
    if tech is None:
        return None

    is_sub = bool(tech.get("is_subtechnique"))
    parent_id = (tech.get("parent_id") or "").strip().upper() or None

    if is_sub and parent_id:
        parent = attack_index.get(parent_id)
        return {
            "technique_id": parent_id,
            "technique_name": parent.get("name", "") if parent else "",
            "sub_technique_id": attack_id,
            "sub_technique_name": tech.get("name", ""),
            "tactic(s)": tech.get("tactics", []) or [],
            "mapping_type": "related_to",
            "confidence": "medium",
            "confidence_score": CONFIDENCE_SCORES["medium"],
            "justification": "",
        }

    return {
        "technique_id": attack_id,
        "technique_name": tech.get("name", ""),
        "sub_technique_id": None,
        "sub_technique_name": None,
        "tactic(s)": tech.get("tactics", []) or [],
        "mapping_type": "related_to",
        "confidence": "medium",
        "confidence_score": CONFIDENCE_SCORES["medium"],
        "justification": "",
    }


def enrich_veris_entry(
    entry: dict,
    veris_index: dict,
    attack_index: dict,
    capability_group: str,
) -> tuple[dict, list[str]]:
    """Retourne (entrée enrichie, attack_ids valides retenus)."""
    veris_id = entry.get("veris_id") or entry.get("capability_id") or ""
    vmeta = veris_index.get(veris_id, {})

    label = (
        entry.get("veris_label")
        or vmeta.get("value")
        or (veris_id.split(".")[-1] if veris_id else "")
    )
    group = vmeta.get("capability_group") or capability_group
    category = entry.get("veris_category") or category_from_group(group)

    attack_ids = extract_attack_ids(entry)
    mitre_mappings: list[dict] = []
    kept: list[str] = []
    rejected: list[str] = []

    for aid in attack_ids:
        enriched = enrich_attack_id(aid, attack_index)
        if enriched is None:
            rejected.append(aid)
            continue
        mitre_mappings.append(enriched)
        kept.append(aid)

    mitre_mappings.sort(key=lambda m: (m["technique_id"], m["sub_technique_id"] or ""))
    no_mapping = entry.get("no_mapping_found")
    if no_mapping is None:
        no_mapping = not mitre_mappings
    else:
        no_mapping = bool(no_mapping) or not mitre_mappings

    notes = entry.get("notes", "")
    if rejected:
        rej = ", ".join(rejected)
        extra = f"IDs ATT&CK inconnus rejetés: {rej}."
        notes = f"{notes} {extra}".strip() if notes else extra
    if no_mapping and not notes:
        notes = "Aucune correspondance trouvée."

    enriched_entry = {
        "veris_id": veris_id,
        "veris_category": category,
        "veris_label": label,
        "no_mapping_found": no_mapping,
        "mitre_mappings": [] if no_mapping else mitre_mappings,
        "ambiguous": bool(entry.get("ambiguous", False)),
        "notes": notes,
    }
    return enriched_entry, ([] if no_mapping else kept)


def build_mitre_to_veris(
    pairs: list[tuple[str, str]],
    veris_index: dict,
    attack_index: dict,
) -> list[dict]:
    """pairs = [(veris_id, attack_id), ...]"""
    by_attack: dict[str, list[str]] = {}
    for veris_id, attack_id in pairs:
        by_attack.setdefault(attack_id, [])
        if veris_id not in by_attack[attack_id]:
            by_attack[attack_id].append(veris_id)

    out: list[dict] = []
    for attack_id in sorted(by_attack.keys()):
        tech = attack_index.get(attack_id)
        if tech is None:
            continue
        is_sub = bool(tech.get("is_subtechnique"))
        parent_id = (tech.get("parent_id") or "").strip().upper() or None
        if is_sub and parent_id:
            parent = attack_index.get(parent_id)
            base = {
                "technique_id": parent_id,
                "technique_name": parent.get("name", "") if parent else "",
                "sub_technique_id": attack_id,
                "sub_technique_name": tech.get("name", ""),
                "tactic(s)": tech.get("tactics", []) or [],
            }
        else:
            base = {
                "technique_id": attack_id,
                "technique_name": tech.get("name", ""),
                "sub_technique_id": None,
                "sub_technique_name": None,
                "tactic(s)": tech.get("tactics", []) or [],
            }

        veris_mappings = []
        for vid in sorted(by_attack[attack_id]):
            vmeta = veris_index.get(vid, {})
            group = vmeta.get("capability_group", "")
            veris_mappings.append(
                {
                    "veris_id": vid,
                    "veris_category": category_from_group(group) if group else "",
                    "veris_label": vmeta.get("value", vid.split(".")[-1] if vid else ""),
                    "mapping_type": "related_to",
                    "confidence": "medium",
                    "confidence_score": CONFIDENCE_SCORES["medium"],
                    "justification": "",
                }
            )

        out.append(
            {
                **base,
                "no_mapping_found": False,
                "veris_mappings": veris_mappings,
                "ambiguous": False,
                "notes": "",
            }
        )
    return out


def reconstruct_file(
    raw: dict,
    veris_index: dict,
    attack_index: dict,
    capability_group: str,
    veris_version: str,
    attack_version: str,
) -> dict:
    entries_in = raw.get("veris_to_mitre") or []
    enriched_entries: list[dict] = []
    pairs: list[tuple[str, str]] = []

    for entry in entries_in:
        if not isinstance(entry, dict):
            continue
        enriched, kept_ids = enrich_veris_entry(
            entry, veris_index, attack_index, capability_group
        )
        enriched_entries.append(enriched)
        for aid in kept_ids:
            pairs.append((enriched["veris_id"], aid))

    meta = raw.get("metadata") or {}
    group = (
        meta.get("capability_group")
        or meta.get("scope")
        or capability_group
    )
    return {
        "metadata": {
            "veris_version": meta.get("veris_version") or veris_version,
            "mitre_attack_version": meta.get("mitre_attack_version") or attack_version,
            "scope": group,
            "capability_group": group,
            "enriched_from": "local_catalogs",
        },
        "veris_to_mitre": enriched_entries,
        "mitre_to_veris": build_mitre_to_veris(pairs, veris_index, attack_index),
    }


def reconstruct_directory(
    input_dir: Path,
    output_dir: Path,
    veris_data: dict,
    attack_data: dict,
) -> None:
    veris_index = build_veris_index(veris_data)
    attack_index = build_attack_index(attack_data)
    veris_version = str(veris_data.get("version", ""))
    attack_version = str(attack_data.get("version", ""))

    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob("*.json"))
    if not files:
        print(f"Aucun JSON dans {input_dir}")
        return

    for path in files:
        group = path.stem  # action.hacking
        try:
            raw = load_json(path)
        except json.JSONDecodeError as e:
            print(f"[SKIP] {path.name}: JSON invalide ({e})")
            continue
        if not isinstance(raw, dict) or "veris_to_mitre" not in raw:
            print(f"[SKIP] {path.name}: pas de veris_to_mitre")
            continue

        enriched = reconstruct_file(
            raw, veris_index, attack_index, group, veris_version, attack_version
        )
        out_path = output_dir / path.name
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)

        n = len(enriched["veris_to_mitre"])
        mapped = sum(1 for e in enriched["veris_to_mitre"] if not e["no_mapping_found"])
        n_m2v = len(enriched["mitre_to_veris"])
        print(
            f"[OK] {path.name}: {mapped}/{n} VERIS mappées, "
            f"{n_m2v} techniques dans mitre_to_veris -> {out_path}"
        )


def resolve_db_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.a and args.v:
        return Path(args.a), Path(args.v)
    dw = Path(args.dw) if args.dw else DEFAULT_DB
    name = dw.name  # attack-19.1_veris-1.4.1
    parts = name.split("_")
    if len(parts) < 2:
        raise SystemExit(f"Impossible de déduire les fichiers depuis -dw={dw}")
    attack_fn = parts[0].replace("-", "_") + ".json"
    veris_fn = parts[1].replace("-", "_") + ".json"
    return dw / attack_fn, dw / veris_fn


def build_arg_parse() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Enrichit les mappings PROMPT (IDs) avec les catalogues VERIS/ATT&CK"
    )
    p.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Dossier des JSON bruts LLM (ex: ..._PROMPT_Kimi-K3)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Dossier de sortie (défaut: <input>_enriched)",
    )
    p.add_argument("-dw", type=Path, default=DEFAULT_DB, help="Dossier data_for_work")
    p.add_argument("-a", type=Path, default=None, help="Fichier attack_*.json")
    p.add_argument("-v", type=Path, default=None, help="Fichier veris_*.json")
    return p


def main() -> None:
    args = build_arg_parse().parse_args()
    input_dir = args.input.resolve()
    output_dir = (args.output or Path(str(input_dir) + "_enriched")).resolve()
    path_attack, path_veris = resolve_db_paths(args)

    print(f"Input :  {input_dir}")
    print(f"Output:  {output_dir}")
    print(f"ATT&CK:  {path_attack}")
    print(f"VERIS :  {path_veris}")

    veris_data = load_json(path_veris)
    attack_data = load_json(path_attack)
    reconstruct_directory(input_dir, output_dir, veris_data, attack_data)
    print("Done.")


if __name__ == "__main__":
    main()
