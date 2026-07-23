import json
from pathlib import Path


BASE_DIR = Path(
    r"C:\Users\Freddo\OneDrive\Bureau\VERIS\MappingVerisAtt-ck_reference\Resultat\Resultat_FINE_TUNE\veris-1.4.1_attack-19.1-enterprise_FINE_TUNED_LLM_LLAMA_B3_K25"
)


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def fix_file(path):
    data = load_json(path)

    entries = data.get("veris_to_mitre", [])

    fixed_entries = []
    fixed_count = 0

    for entry in entries:
        if isinstance(entry, dict):
            fixed_entries.append(entry)
            continue

        if isinstance(entry, str):
            fixed_count += 1

            fixed_entries.append(
                {
                    "veris_id": entry,
                    "veris_category": ".".join(entry.split(".")[:2]),
                    "veris_label": entry.split(".")[-1],
                    "no_mapping_found": True,
                    "mitre_mappings": [],
                    "ambiguous": False,
                    "notes": "Entrée réparée automatiquement : le LLM avait retourné une chaîne au lieu d'un objet JSON.",
                }
            )

            continue

        fixed_count += 1

    data["veris_to_mitre"] = fixed_entries

    write_json(path, data)

    return fixed_count


def main():
    total_fixed = 0

    for path in BASE_DIR.glob("*.json"):
        fixed_count = fix_file(path)

        if fixed_count > 0:
            print(f"{path.name} : {fixed_count} entrée(s) réparée(s)")

        total_fixed += fixed_count

    print(f"Réparation terminée. Total réparé : {total_fixed}")


if __name__ == "__main__":
    main()