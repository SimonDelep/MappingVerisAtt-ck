import argparse
import json
import os
import pickle
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MultiLabelBinarizer


ROOT_DIR = Path(__file__).resolve().parents[2]

DEFAULT_DB_MAPPING = ROOT_DIR / "data_for_work" / "attack-19.1_veris-1.4.1"

SCOPES = [
    "action.hacking",
    "action.malware",
    "action.social",
    "attribute.availability",
    "attribute.confidentiality",
    "attribute.integrity",
    "value_chain.development",
]


def build_arg_parse():
    parser = argparse.ArgumentParser(
        description="Fine-tune local pour générer un mapping VERIS -> MITRE ATT&CK"
    )

    parser.add_argument(
        "-dw",
        type=Path,
        default=DEFAULT_DB_MAPPING,
        help="Dossier contenant veris_*.json, attack_*.json et mapping_des_experts.json",
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=0.20,
        help="Seuil minimum de confiance pour garder une technique ATT&CK",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Nombre maximum de techniques ATT&CK gardées par capability VERIS",
    )

    parser.add_argument(
        "--output-name",
        default="FINE_TUNE",
        help="Nom du dossier de sortie",
    )

    return parser

def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def find_work_files(data_work):
    data_work = Path(data_work)

    veris_files = sorted(data_work.glob("veris_*.json"))
    attack_files = sorted(data_work.glob("attack_*.json"))
    mapping_files = sorted(data_work.glob("mapping_des_experts.json"))

    if not veris_files:
        raise FileNotFoundError(f"Aucun fichier veris_*.json trouvé dans {data_work}")

    if not attack_files:
        raise FileNotFoundError(f"Aucun fichier attack_*.json trouvé dans {data_work}")

    if not mapping_files:
        raise FileNotFoundError(f"Aucun fichier mapping_des_experts.json trouvé dans {data_work}")

    return veris_files[0], attack_files[0], mapping_files[0]


def build_veris_lookup(veris_data):
    lookup = {}

    for capability in veris_data.get("capabilities", []):
        capability_id = capability.get("capability_id")

        if capability_id:
            lookup[capability_id] = capability

    return lookup


def build_attack_lookup(attack_data):
    lookup = {}

    for technique in attack_data.get("techniques", []):
        attack_id = technique.get("attack_id")

        if attack_id:
            lookup[attack_id.upper()] = technique

    return lookup


def capability_to_text(capability):
    text = " ".join(
        [
            str(capability.get("capability_id", "")),
            str(capability.get("capability_group", "")),
            str(capability.get("value", "")),
            str(capability.get("description", "")),
        ]
    )

    return text


def build_training_dataset(mapping_data, veris_lookup):
    grouped = {}

    for item in mapping_data.get("mapping_objects", []):
        capability_id = item.get("capability_id")
        attack_id = item.get("attack_object_id")

        if not capability_id or not attack_id:
            continue

        if capability_id not in veris_lookup:
            continue

        if capability_id not in grouped:
            grouped[capability_id] = set()

        grouped[capability_id].add(attack_id.upper())

    texts = []
    labels = []

    for capability_id, attack_ids in grouped.items():
        capability = veris_lookup[capability_id]

        texts.append(capability_to_text(capability))
        labels.append(sorted(attack_ids))

    return texts, labels

def train_model(texts, labels):
    label_binarizer = MultiLabelBinarizer()
    y = label_binarizer.fit_transform(labels)

    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    max_features=20000,
                ),
            ),
            (
                "classifier",
                OneVsRestClassifier(
                    LogisticRegression(
                        max_iter=2000,
                    )
                ),
            ),
        ]
    )

    model.fit(texts, y)

    return model, label_binarizer


def split_attack_id(attack_id):
    attack_id = attack_id.upper().strip()

    if "." in attack_id:
        parent_id = attack_id.split(".", 1)[0]
        return parent_id, attack_id

    return attack_id, None


def predict_attack_ids(model, label_binarizer, capability, threshold, top_k):
    text = capability_to_text(capability)

    probabilities = model.predict_proba([text])[0]

    scored = []

    for attack_id, score in zip(label_binarizer.classes_, probabilities):
        scored.append((attack_id, float(score)))

    scored.sort(key=lambda item: item[1], reverse=True)

    selected = []

    for attack_id, score in scored:
        if score >= threshold:
            selected.append((attack_id, score))

        if len(selected) >= top_k:
            break

    if not selected and scored:
        selected.append(scored[0])

    return selected


def build_mitre_mapping(attack_id, score, attack_lookup):
    technique_id, sub_technique_id = split_attack_id(attack_id)

    technique_meta = attack_lookup.get(technique_id, {})
    sub_meta = attack_lookup.get(sub_technique_id or "", {})

    if score >= 0.75:
        confidence = "high"
    elif score >= 0.45:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "technique_id": technique_id,
        "technique_name": technique_meta.get("name", ""),
        "sub_technique_id": sub_technique_id,
        "sub_technique_name": sub_meta.get("name") if sub_technique_id else None,
        "tactic(s)": sub_meta.get("tactics") or technique_meta.get("tactics") or [],
        "mapping_type": "related_to",
        "confidence": confidence,
        "confidence_score": round(score, 4),
        "justification": "Mapping généré par un modèle local fine-tuned sur les mappings experts VERIS -> ATT&CK.",
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
                    "confidence_score": mapping.get("confidence_score"),
                    "justification": mapping.get("justification"),
                }
            )

    return sorted(grouped.values(), key=lambda item: item["attack_id"])
def generate_scope_file(
    scope,
    capabilities,
    model,
    label_binarizer,
    attack_lookup,
    veris_version,
    attack_version,
    threshold,
    top_k,
):
    entries = []

    for capability in capabilities:
        predictions = predict_attack_ids(
            model=model,
            label_binarizer=label_binarizer,
            capability=capability,
            threshold=threshold,
            top_k=top_k,
        )

        mitre_mappings = []

        for attack_id, score in predictions:
            mitre_mappings.append(
                build_mitre_mapping(
                    attack_id=attack_id,
                    score=score,
                    attack_lookup=attack_lookup,
                )
            )

        entry = {
            "veris_id": capability.get("capability_id", ""),
            "veris_category": capability.get("capability_group", ""),
            "veris_label": capability.get("value", ""),
            "no_mapping_found": len(mitre_mappings) == 0,
            "mitre_mappings": mitre_mappings,
            "ambiguous": len(mitre_mappings) > 1,
            "notes": "",
        }

        entries.append(entry)

    payload = {
        "metadata": {
            "veris_version": veris_version,
            "mitre_attack_version": attack_version,
            "scope": scope,
            "method": "FINE_TUNE",
            "model": "TF-IDF + OneVsRest LogisticRegression",
        },
        "veris_to_mitre": entries,
        "mitre_to_veris": build_mitre_to_veris(entries),
    }

    return payload


def main():
    parser = build_arg_parse()
    args = parser.parse_args()

    path_veris, path_attack, path_mapping = find_work_files(args.dw)

    veris_data = load_json(path_veris)
    attack_data = load_json(path_attack)
    mapping_data = load_json(path_mapping)

    veris_version = str(veris_data.get("version"))
    attack_version = str(attack_data.get("version"))

    reference = f"veris-{veris_version}_attack-{attack_version}-enterprise"

    output_dir = (
        ROOT_DIR
        / "Resultat"
        / "Resultat_FINE_TUNE"
        / f"{reference}_{args.output_name}"
    )

    model_dir = ROOT_DIR / "Solution" / "Solution_FINE_TUNE" / "model"
    model_dir.mkdir(parents=True, exist_ok=True)

    print(f"ATT&CK MITRE version : {attack_version}")
    print(f"VERIS version : {veris_version}")
    print(f"Mapping expert : {path_mapping}")
    print(f"Sortie : {output_dir}")

    veris_lookup = build_veris_lookup(veris_data)
    attack_lookup = build_attack_lookup(attack_data)

    texts, labels = build_training_dataset(
        mapping_data=mapping_data,
        veris_lookup=veris_lookup,
    )

    print(f"Exemples d'entraînement : {len(texts)}")
    print("Entraînement du modèle local FINE_TUNE...")

    model, label_binarizer = train_model(texts, labels)

    model_file = model_dir / "fine_tune_model.pkl"

    with open(model_file, "wb") as file:
        pickle.dump(
            {
                "model": model,
                "label_binarizer": label_binarizer,
            },
            file,
        )

    print(f"Modèle sauvegardé : {model_file}")

    capabilities = veris_data.get("capabilities", [])

    manifest = {
        "reference": reference,
        "method": "FINE_TUNE",
        "model": "TF-IDF + OneVsRest LogisticRegression",
        "training_examples": len(texts),
        "threshold": args.threshold,
        "top_k": args.top_k,
        "files": [],
    }

    for scope in SCOPES:
        print(f"\nTraitement du scope : {scope}")

        scope_capabilities = []

        for capability in capabilities:
            if capability.get("capability_group") == scope:
                scope_capabilities.append(capability)

        payload = generate_scope_file(
            scope=scope,
            capabilities=scope_capabilities,
            model=model,
            label_binarizer=label_binarizer,
            attack_lookup=attack_lookup,
            veris_version=veris_version,
            attack_version=attack_version,
            threshold=args.threshold,
            top_k=args.top_k,
        )

        output_file = output_dir / f"{scope}.json"
        write_json(output_file, payload)

        mapped_entries = 0

        for entry in payload["veris_to_mitre"]:
            if not entry["no_mapping_found"]:
                mapped_entries += 1

        manifest["files"].append(
            {
                "scope": scope,
                "file": str(output_file),
                "entries": len(scope_capabilities),
                "mapped_entries": mapped_entries,
            }
        )

        print(f"Fichier généré : {output_file}")

    write_json(output_dir / "manifest.json", manifest)

    print("\nFINE_TUNE terminé.")
    print(f"Résultats écrits dans : {output_dir}")


if __name__ == "__main__":
    main()