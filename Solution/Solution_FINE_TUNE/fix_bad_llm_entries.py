import json
import re
import sys
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def veris_category_from_id(veris_id):
    parts = str(veris_id).split(".")

    if len(parts) >= 2:
        return ".".join(parts[:2])

    return ""


def veris_label_from_id(veris_id):
    parts = str(veris_id).split(".")

    if parts:
        return parts[-1]

    return str(veris_id)


def split_attack_id(attack_id):
    attack_id = str(attack_id).strip().upper()

    if "." in attack_id:
        return attack_id.split(".", 1)[0], attack_id

    return attack_id, None


def build_mitre_mapping_from_string(value):
    text = str(value).upper()
    match = re.search(r"T\d{4}(?:\.\d{3})?", text)

    if not match:
        return None

    attack_id = match.group(0)
    technique_id, sub_technique_id = split_attack_id(attack_id)

    return {
        "technique_id": technique_id,
        "technique_name": "",
        "sub_technique_id": sub_technique_id,
        "sub_technique_name": None,
        "tactic(s)": [],
        "mapping_type": "related_to",
        "confidence": "medium",
        "justification": "Mapping réparé automatiquement depuis une sortie LLM mal structurée.",
    }


def fix_entry(entry):
    if isinstance(entry, str):
        return {
            "veris_id": entry,
            "veris_category": veris_category_from_id(entry),
            "veris_label": veris_label_from_id(entry),
            "no_mapping_found": True,
            "mitre_mappings": [],
            "ambiguous": False,
            "notes": "Entrée réparée automatiquement : le LLM avait retourné une chaîne au lieu d'un objet JSON.",
        }, 1

    if not isinstance(entry, dict):
        return None, 1

    mitre_mappings = entry.get("mitre_mappings", [])

    fixed_mappings = []
    fixed_count = 0

    if isinstance(mitre_mappings, str):
        mapping = build_mitre_mapping_from_string(mitre_mappings)

        if mapping:
            fixed_mappings.append(mapping)

        fixed_count += 1

    elif isinstance(mitre_mappings, list):
        for mapping in mitre_mappings:
            if isinstance(mapping, dict):
                fixed_mappings.append(mapping)
                continue

            if isinstance(mapping, str):
                fixed = build_mitre_mapping_from_string(mapping)

                if fixed:
                    fixed_mappings.append(fixed)

                fixed_count += 1
                continue

            fixed_count += 1

    else:
        fixed_count += 1

    entry["mitre_mappings"] = fixed_mappings
    entry["no_mapping_found"] = len(fixed_mappings) == 0
    entry["ambiguous"] = len(fixed_mappings) > 1

    return entry, fixed_count


def fix_file(path):
    data = load_json(path)

    if not isinstance(data, dict):
        return 0

    entries = data.get("veris_to_mitre")

    if not isinstance(entries, list):
        return 0

    fixed_entries = []
    fixed_count = 0

    for entry in entries:
        fixed_entry, count = fix_entry(entry)

        if fixed_entry is not None:
            fixed_entries.append(fixed_entry)

        fixed_count += count

    data["veris_to_mitre"] = fixed_entries

    write_json(path, data)

    return fixed_count


def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_bad_llm_entries.py <dossier_resultat>")
        raise SystemExit(1)

    base_dir = Path(sys.argv[1])

    if not base_dir.exists():
        print(f"Dossier introuvable : {base_dir}")
        raise SystemExit(1)

    total_fixed = 0

    for path in base_dir.glob("*.json"):
        fixed_count = fix_file(path)

        if fixed_count > 0:
            print(f"{path.name} : {fixed_count} correction(s)")

        total_fixed += fixed_count

    print(f"Réparation terminée. Total corrections : {total_fixed}")


if __name__ == "__main__":
    main()