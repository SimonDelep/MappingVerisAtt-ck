import argparse
import json
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]

DEFAULT_DATA_DIR = ROOT_DIR / "data_for_work" / "attack-19.1_veris-1.4.1"

SCOPES = [
    "action.hacking",
    "action.malware",
    "action.social",
    "attribute.availability",
    "attribute.confidentiality",
    "attribute.integrity",
    "value_chain.development",
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def find_work_files(data_dir):
    veris_files = sorted(Path(data_dir).glob("veris_*.json"))
    attack_files = sorted(Path(data_dir).glob("attack_*.json"))

    if not veris_files:
        raise FileNotFoundError(f"Aucun fichier veris_*.json dans {data_dir}")

    if not attack_files:
        raise FileNotFoundError(f"Aucun fichier attack_*.json dans {data_dir}")

    return veris_files[0], attack_files[0]


def find_llm_input_dir(reference):
    candidates = [
        ROOT_DIR / "Resultat" / "Resultat_FINE_TUNE" / f"{reference}_FINE_TUNED_LLM",
        ROOT_DIR / "Resultat_HORS_COMPARAISON" / f"{reference}_FINE_TUNED_LLM",
        ROOT_DIR / "Resultat_HORS_COMPARAISON" / "Resultat_FINE_TUNE" / f"{reference}_FINE_TUNED_LLM",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Impossible de trouver le dossier FINE_TUNED_LLM. "
        "Vérifie s'il est dans Resultat ou Resultat_HORS_COMPARAISON."
    )


def build_attack_lookup(attack_data):
    lookup = {}

    for technique in attack_data.get("techniques", []):
        attack_id = technique.get("attack_id")

        if attack_id:
            lookup[attack_id.upper()] = technique

    return lookup


def filter_veris_by_scope(veris_data, scope):
    items = []

    for capability in veris_data.get("capabilities", []):
        if capability.get("capability_group") == scope:
            items.append(capability)

    return items


def split_attack_id(attack_id):
    attack_id = str(attack_id).strip().upper()

    if "." in attack_id:
        return attack_id.split(".", 1)[0], attack_id

    return attack_id, None


def clean_attack_id(value):
    if value is None:
        return None

    value = str(value).strip().upper()

    match = re.search(r"T\d{4}(?:\.\d{3})?", value)

    if match:
        return match.group(0)

    return None


def get_raw_mapping_container(raw_data):
    """
    Récupère la partie utile même si le LLM a changé le nom des clés.
    """

    if not isinstance(raw_data, dict):
        return {}

    possible_keys = [
        "veris_to_mitre",
        "VERIS_to_MITRE",
        "VERIS_TO_MITRE",
        "Veris_to_Mitre",
        "mappings",
        "mapping",
    ]

    for key in possible_keys:
        if key in raw_data:
            return raw_data[key]

    return raw_data


def extract_attack_ids_from_value(value):
    """
    Recherche récursive des IDs MITRE dans n'importe quelle structure JSON.
    Exemple détecté : T1110, T1110.001, T1059, etc.
    """

    found = []

    def add_attack_ids(text):
        text = str(text).upper()

        matches = re.findall(r"T\d{4}(?:\.\d{3})?", text)

        for attack_id in matches:
            if attack_id not in found:
                found.append(attack_id)

    def walk(obj):
        if obj is None:
            return

        if isinstance(obj, str):
            add_attack_ids(obj)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

        elif isinstance(obj, dict):
            for key, value in obj.items():
                add_attack_ids(key)
                walk(value)

        else:
            add_attack_ids(obj)

    walk(value)

    return found


def extract_justification(value):
    if not isinstance(value, dict):
        return ""

    for key in ["justification", "description", "reason", "notes", "explanation"]:
        if key in value and isinstance(value[key], str):
            return value[key]

    return ""


def normalize_text(value):
    value = str(value).lower()
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def find_raw_entry_for_veris(container, veris_item):
    """
    Retrouve l'entrée correspondant à une capability VERIS.
    Le LLM peut utiliser l'id complet, le label, ou seulement la fin du label.
    """

    veris_id = str(veris_item.get("capability_id", ""))
    veris_label = str(veris_item.get("value", ""))

    aliases = [
        veris_id,
        veris_label,
        veris_id.split(".")[-1],
    ]

    normalized_aliases = []

    for alias in aliases:
        alias = normalize_text(alias)

        if alias and alias not in normalized_aliases:
            normalized_aliases.append(alias)

    if isinstance(container, dict):
        for key, value in container.items():
            normalized_key = normalize_text(key)

            for alias in normalized_aliases:
                if normalized_key == alias:
                    return value

        for key, value in container.items():
            normalized_key = normalize_text(key)

            for alias in normalized_aliases:
                if alias in normalized_key or normalized_key in alias:
                    return value

    if isinstance(container, list):
        for item in container:
            if not isinstance(item, dict):
                continue

            text = json.dumps(item, ensure_ascii=False)
            normalized_text = normalize_text(text)

            for alias in normalized_aliases:
                if alias in normalized_text:
                    return item

    return None

def build_mitre_mapping(attack_id, justification, attack_lookup):
    technique_id, sub_technique_id = split_attack_id(attack_id)

    technique_meta = attack_lookup.get(technique_id, {})
    sub_meta = attack_lookup.get(sub_technique_id or "", {})

    return {
        "technique_id": technique_id,
        "technique_name": technique_meta.get("name", ""),
        "sub_technique_id": sub_technique_id,
        "sub_technique_name": sub_meta.get("name") if sub_technique_id else None,
        "tactic(s)": sub_meta.get("tactics") or technique_meta.get("tactics") or [],
        "mapping_type": "related_to",
        "confidence": "medium",
        "justification": justification,
    }


def build_mitre_to_veris(veris_to_mitre):
    grouped = {}

    for entry in veris_to_mitre:
        for mapping in entry.get("mitre_mappings", []):
            attack_id = mapping.get("sub_technique_id") or mapping.get("technique_id")

            if not attack_id:
                continue

            if attack_id not in grouped:
                grouped[attack_id] = {
                    "attack_id": attack_id,
                    "technique_id": mapping.get("technique_id"),
                    "technique_name": mapping.get("technique_name"),
                    "sub_technique_id": mapping.get("sub_technique_id"),
                    "sub_technique_name": mapping.get("sub_technique_name"),
                    "veris_mappings": [],
                }

            grouped[attack_id]["veris_mappings"].append(
                {
                    "veris_id": entry.get("veris_id"),
                    "veris_label": entry.get("veris_label"),
                    "justification": mapping.get("justification"),
                }
            )

    return sorted(grouped.values(), key=lambda item: item["attack_id"])


def normalize_scope(raw_data, veris_items, attack_lookup, veris_version, attack_version, scope):
    container = get_raw_mapping_container(raw_data)

    entries = []

    for item in veris_items:
        veris_id = item.get("capability_id", "")
        raw_entry = find_raw_entry_for_veris(container, item)

        attack_ids = extract_attack_ids_from_value(raw_entry)
        justification = extract_justification(raw_entry)

        mitre_mappings = []

        for attack_id in attack_ids:
            mitre_mappings.append(
                build_mitre_mapping(
                    attack_id=attack_id,
                    justification=justification,
                    attack_lookup=attack_lookup,
                )
            )

        entries.append(
            {
                "veris_id": veris_id,
                "veris_category": item.get("capability_group", scope),
                "veris_label": item.get("value", ""),
                "no_mapping_found": len(mitre_mappings) == 0,
                "mitre_mappings": mitre_mappings,
                "ambiguous": len(mitre_mappings) > 1,
                "notes": "Normalisé depuis la sortie brute du LLM Llama.",
            }
        )

    return {
        "metadata": {
            "veris_version": veris_version,
            "mitre_attack_version": attack_version,
            "scope": scope,
            "method": "FINE_TUNED_LLM_NORMALIZED",
            "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        },
        "veris_to_mitre": entries,
        "mitre_to_veris": build_mitre_to_veris(entries),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Normalise les sorties du LLM Llama au format veris_to_mitre"
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Dossier contenant veris_*.json et attack_*.json",
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Dossier brut FINE_TUNED_LLM à normaliser",
    )

    parser.add_argument(
        "--output-name",
        default="FINE_TUNED_LLM_NORMALIZED",
        help="Nom du dossier normalisé",
    )

    args = parser.parse_args()

    path_veris, path_attack = find_work_files(args.data_dir)

    veris_data = load_json(path_veris)
    attack_data = load_json(path_attack)

    veris_version = str(veris_data.get("version"))
    attack_version = str(attack_data.get("version"))

    reference = f"veris-{veris_version}_attack-{attack_version}-enterprise"

    input_dir = args.input_dir

    if input_dir is None:
        input_dir = find_llm_input_dir(reference)

    output_dir = (
        ROOT_DIR
        / "Resultat"
        / "Resultat_FINE_TUNE"
        / f"{reference}_{args.output_name}"
    )

    attack_lookup = build_attack_lookup(attack_data)

    print(f"Dossier source : {input_dir}")
    print(f"Dossier sortie : {output_dir}")

    for scope in SCOPES:
        input_file = input_dir / f"{scope}.json"

        if not input_file.exists():
            print(f"Fichier absent, ignoré : {input_file}")
            continue

        raw_data = load_json(input_file)
        veris_items = filter_veris_by_scope(veris_data, scope)

        normalized = normalize_scope(
            raw_data=raw_data,
            veris_items=veris_items,
            attack_lookup=attack_lookup,
            veris_version=veris_version,
            attack_version=attack_version,
            scope=scope,
        )

        output_file = output_dir / f"{scope}.json"
        write_json(output_file, normalized)

        mapped = 0

        for entry in normalized["veris_to_mitre"]:
            if not entry["no_mapping_found"]:
                mapped += 1

        print(f"{scope} : {mapped}/{len(veris_items)} entrées avec mapping")

    print("\nNormalisation terminée.")


if __name__ == "__main__":
    main()