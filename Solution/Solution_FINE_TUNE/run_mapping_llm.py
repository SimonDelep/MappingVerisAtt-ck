from together import Together
from dotenv import load_dotenv

import argparse
import json
import os
import re
from pathlib import Path

# -------------------- ROOT / DEFAULT PATHS

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

# -------------------- ArgParse
def build_arg_parse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
            description="Create a mapping between MITRE ATT&CK and Veris database with public LLM models",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Usage:
 $ python run_mapping -dw [path/to/data_for_work/combo-dir]
 # With custom versions of databases
 $ python run_mapping -m [path/to/mitre_attack] -v [path/to/veris]
-----

If there is no database selected, last version of database is selected by default
            """,
            )
    parser.add_argument(
            "-dw",
            type=Path,
            default=DEFAULT_DB_MAPPING,
            metavar="Path",
            help="Absolute path to the parent directory containing database",
            )
    parser.add_argument(
            "-m",
            type=Path,
            default=None,
            metavar="Path",
            help="Absolute path to the MITRE ATT&CK json file (database), with verion number",
            )
    parser.add_argument(
            "-v",
            type=Path,
            default=None,
            metavar="Path",
            help="Absolute path to the VERIS json file (database), with verion number",
            )
    parser.add_argument(
            "--model",
            default=os.getenv("TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
            help="LLM déjà instruction-tuned utilisé pour la génération fine-tuned",
            )
    parser.add_argument(
            "--top-k-attack",
            type=int,
            default=30,
            help="Nombre de techniques MITRE candidates envoyées au LLM",
            )
    parser.add_argument(
            "--limit-per-scope",
            type=int,
            default=None,
            help="Limite de capabilities par scope pour tester rapidement",
            )
    parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Traiter toutes les capabilities par lots de N éléments pour éviter les gros JSON invalides",
            )
    parser.add_argument(
            "--output-name", 
            default="FINE_TUNED_LLM", 
            help="Nom du dossier de sortie"
            )
    parser.add_argument(
            "--mock",
            action="store_true",
            help="Mode test sans appel API",
            )
    parser.add_argument(
            "--max-mappings-per-veris",
            type=int,
            default=None,
            help="Nombre maximum de mappings MITRE conservés par élément VERIS",
            )
    return parser


# --------------------- PATH $ DATA



# --------------------- PROMPT

def create_user_prompt(
    veris_version="",
    attack_version="",
    data_veris="",
    data_attack="",
    attack_domain="Enterprise",
    capability_group="",
):
    if not isinstance(data_veris, str):
        data_veris = json.dumps(data_veris, ensure_ascii=False, indent=2)

    if not isinstance(data_attack, str):
        data_attack = json.dumps(data_attack, ensure_ascii=False, indent=2)

    user_prompt = """\
Prend en compte le system-prompt.md pour repondre
Voici les données de référence à utiliser pour ce mapping bidirectionnel. N'utilise aucune autre source ni connaissance externe que celles indiquées ci-dessous.

## Version des référentiels:
    - Version VERIS schema: {veris_version}
    - Version MITRE ATT&CK (matrice): {attack_version}
    - ATT&CK Domain: {attack_domain}

## Périmètre à traiter dans cette réponse
Je veux que tu me traite toutes les données en rapport de la capability group {capability_group}

## Données VERIS (catégorie(s), vector(s), variety(ies) avec leurs descriptions/définitions)
{data_veris}

## Catalogue MITRE ATT&CK (techniques et sub-techniques avec ID, nom, description,tactique(s))
{data_attack}

## Instruction finale
Produis le mapping bidirectionnel complet (VERIS → MITRE puis MITRE → VERIS) entre tous les éléments listés ci-dessus, en respectant strictement le format JSON et les règles définies dans le system prompt.
Traite tous les éléments fournis dans les deux sens, sans en omettre aucun, même pour indiquer "no_mapping_found": true.\
         """.format(
        veris_version=veris_version,
        attack_version=attack_version,
        attack_domain=attack_domain,
        capability_group=capability_group,
        data_veris=data_veris,
        data_attack=data_attack,
    )

    return user_prompt


# -------------------- DB DATA
def get_data(data_path):
    try:
        with open(data_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        version = str(data["version"])
        return data, version

    except FileNotFoundError:
        raise FileNotFoundError(f"Fichier introuvable : {data_path}")


def find_work_files(data_work):
    veris_files = sorted(Path(data_work).glob("veris_*.json"))
    attack_files = sorted(Path(data_work).glob("attack_*.json"))

    if not veris_files:
        raise FileNotFoundError(f"Aucun fichier veris_*.json trouvé dans {data_work}")

    if not attack_files:
        raise FileNotFoundError(f"Aucun fichier attack_*.json trouvé dans {data_work}")

    return veris_files[0], attack_files[0]

def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def filter_veris_by_scope(veris_data, scope):
    capabilities = veris_data.get("capabilities", [])
    selected = []

    for capability in capabilities:
        if capability.get("capability_group") == scope:
            selected.append(capability)

    return selected
def select_attack_candidates_for_scope(veris_items, attack_data, top_k):
    techniques = attack_data.get("techniques", [])

    veris_text = json.dumps(veris_items, ensure_ascii=False).lower()
    veris_words = set(re.findall(r"[a-zA-Z0-9]+", veris_text))

    scored_techniques = []

    for technique in techniques:
        technique_text = " ".join(
            [
                str(technique.get("attack_id", "")),
                str(technique.get("name", "")),
                str(technique.get("description", "")),
                " ".join(technique.get("tactics", []) or []),
            ]
        ).lower()

        technique_words = set(re.findall(r"[a-zA-Z0-9]+", technique_text))
        score = len(veris_words.intersection(technique_words))

        scored_techniques.append((score, technique))

    scored_techniques.sort(key=lambda item: item[0], reverse=True)

    selected = []

    for score, technique in scored_techniques[:top_k]:
        selected.append(
            {
                "attack_id": technique.get("attack_id"),
                "name": technique.get("name"),
                "description": str(technique.get("description", ""))[:800],
                "tactics": technique.get("tactics", []),
                "is_subtechnique": technique.get("is_subtechnique", False),
                "parent_id": technique.get("parent_id"),
            }
        )

    return {
        "version": attack_data.get("version"),
        "domain": attack_data.get("domain", "enterprise"),
        "techniques": selected,
    }


def extract_json_object(text):
    text = text.strip()

    
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    # Trouve le premier début de JSON
    start = text.find("{")

    if start == -1:
        raise ValueError("Aucun début de JSON trouvé dans la réponse du modèle.")

    # Parse uniquement le premier objet JSON valide
    decoder = json.JSONDecoder()
    obj, end = decoder.raw_decode(text[start:])

    return obj


def get_message_content(response):
    choice = response.choices[0]
    message = choice.message

    if isinstance(message, dict):
        return message.get("content", "")

    return getattr(message, "content", "")


def get_stream_delta_content(chunk):
    try:
        choice = chunk.choices[0]
    except Exception:
        return ""

    delta = getattr(choice, "delta", None)

    if isinstance(delta, dict):
        return delta.get("content", "") or ""

    if delta is not None:
        return getattr(delta, "content", "") or ""

    if isinstance(choice, dict):
        delta = choice.get("delta", {})
        if isinstance(delta, dict):
            return delta.get("content", "") or ""

    return ""


def call_together_llm(client, user_prompt, model, stream=False):
    messages = [
        {
            "role": "system",
            "content": (
                "Tu es un expert en cybersécurité, VERIS et MITRE ATT&CK. "
                "Tu dois répondre uniquement avec un objet JSON valide, sans markdown."
            ),
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    if stream:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=4096,
            stream=True,
        )

        full_text = ""

        for chunk in response:
            full_text += get_stream_delta_content(chunk)

        return full_text

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        max_tokens=4096,
    )

    return get_message_content(response)


def call_together_auto(client, user_prompt, model):
    try:
        return call_together_llm(
            client=client,
            user_prompt=user_prompt,
            model=model,
            stream=False,
        )

    except Exception as error:
        error_text = str(error)

        if "streaming_required" in error_text or "only supports streaming" in error_text:
            print("Modèle streaming-only détecté : relance avec stream=True")

            return call_together_llm(
                client=client,
                user_prompt=user_prompt,
                model=model,
                stream=True,
            )

        raise


def run_llm(client, user_prompt, model):
    raw_text = call_together_auto(
        client=client,
        user_prompt=user_prompt,
        model=model,
    )

    try:
        return extract_json_object(raw_text)

    except Exception:
        print("Réponse JSON invalide. Tentative de correction automatique...")

        correction_prompt = f"""
Corrige la réponse suivante pour produire uniquement un objet JSON valide.
Ne rajoute aucun commentaire, aucun markdown, aucun texte avant ou après le JSON.

Réponse à corriger :
{raw_text}
"""

        corrected_text = call_together_auto(
            client=client,
            user_prompt=correction_prompt,
            model=model,
        )

        try:
            return extract_json_object(corrected_text)

        except Exception:
            debug_dir = ROOT_DIR / "Resultat" / "debug_prompt_errors"
            debug_dir.mkdir(parents=True, exist_ok=True)

            debug_file = debug_dir / "last_invalid_response.txt"

            with open(debug_file, "w", encoding="utf-8") as file:
                file.write(raw_text)
                file.write("\n\n--- CORRECTION ---\n\n")
                file.write(corrected_text)

            raise ValueError(
                f"Réponse JSON invalide même après correction. Debug : {debug_file}"
            )


def mock_response(veris_version, attack_version, scope, veris_items):
    return {
        "metadata": {
            "veris_version": veris_version,
            "mitre_attack_version": attack_version,
            "scope": scope,
            "method": "PROMPT",
            "mock": True,
        },
        "veris_to_mitre": [
            {
                "veris_id": item.get("capability_id", ""),
                "veris_category": item.get("capability_group", ""),
                "veris_label": item.get("value", ""),
                "no_mapping_found": True,
                "mitre_mappings": [],
                "ambiguous": False,
                "notes": "Mock response",
            }
            for item in veris_items
        ],
        "mitre_to_veris": [],
    }
"""
# -------------------- LLM
client = Together()
async_client = AsyncTogether()


def run_llm(user_prompt:str, model:str, system_prompt:str=None):
    messages=[]
    if system_prompt:
        message.append({"role": "system", "content":system_prompt})

    messages.append({"role":"user", "content":user_prompt})

    response = client.chat.completions.create(
            model=model,
            messages=message
    )

    return response.choices[0].message.content

async def run_llm_parallel(user_prompt:str, model:str, system_prompt:str=None):
    for sleep_time in [1,2,4]:
        try:
            messages=[]
            if system_prompt:
                messages.append({"role":"system", "content":system_prompt})
            messages.append({"role":"user", "content":user_prompt})
            
            reponse= await async_client.chat.completions.create(
                    model=model,
                    messages=messages
            )
            break
        except together.error.RateLimitError as e:
            await asyncio.sleep(sleep_time)
    return response.choices[0].message.content
"""
def normalize_prompt_payload(
    result_json,
    veris_scope_data,
    veris_version,
    mitre_version,
    scope,
    model,
):
    """
    Convertit une réponse LLM variable au format attendu par le comparateur :
    {
      "metadata": {...},
      "veris_to_mitre": [...]
    }
    """

    def clean_attack_id(value):
        if value is None:
            return None

        value = str(value).strip().upper()
        match = re.search(r"T\d{4}(?:\.\d{3})?", value)

        if match:
            return match.group(0)

        return None

    def split_attack_id(attack_id):
        attack_id = str(attack_id).strip().upper()

        if "." in attack_id:
            technique_id = attack_id.split(".", 1)[0]
            return technique_id, attack_id

        return attack_id, None

    def extract_attack_ids(value):
        found = []

        def add_from_text(text):
            text = str(text).upper()
            matches = re.findall(r"T\d{4}(?:\.\d{3})?", text)

            for attack_id in matches:
                if attack_id not in found:
                    found.append(attack_id)

        def walk(obj):
            if obj is None:
                return

            if isinstance(obj, str):
                add_from_text(obj)

            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

            elif isinstance(obj, dict):
                for key, val in obj.items():
                    add_from_text(key)
                    walk(val)

            else:
                add_from_text(obj)

        walk(value)

        return found

    def extract_justification(value):
        if not isinstance(value, dict):
            return ""

        possible_keys = [
            "justification",
            "description",
            "reason",
            "notes",
            "explanation",
        ]

        for key in possible_keys:
            if key in value and isinstance(value[key], str):
                return value[key]

        return ""

    def normalize_text(value):
        value = str(value).lower()
        value = re.sub(r"[^a-z0-9]+", "", value)
        return value

    def get_container(data):
        if isinstance(data, list):
            return data

        if not isinstance(data, dict):
            return {}

        possible_keys = [
            "veris_to_mitre",
            "VERIS_to_MITRE",
            "VERIS_TO_MITRE",
            "Veris_to_Mitre",
            "mappings",
            "mapping",
            "results",
            "result",
        ]

        for key in possible_keys:
            if key in data:
                return data[key]

        return data

    def find_raw_entry(container, veris_item):
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

                possible_ids = [
                    item.get("veris_id"),
                    item.get("VERIS_id"),
                    item.get("capability_id"),
                    item.get("capability"),
                ]

                for possible_id in possible_ids:
                    if normalize_text(possible_id) in normalized_aliases:
                        return item

                item_text = json.dumps(item, ensure_ascii=False)
                normalized_item_text = normalize_text(item_text)

                for alias in normalized_aliases:
                    if alias in normalized_item_text:
                        return item

        return None

    def build_mitre_mapping(attack_id, justification):
        technique_id, sub_technique_id = split_attack_id(attack_id)

        return {
            "technique_id": technique_id,
            "technique_name": "",
            "sub_technique_id": sub_technique_id,
            "sub_technique_name": None,
            "tactic(s)": [],
            "mapping_type": "related_to",
            "confidence": "medium",
            "justification": justification,
        }

    if isinstance(result_json, dict) and "veris_to_mitre" in result_json:
        if "metadata" not in result_json:
            result_json["metadata"] = {
                "veris_version": veris_version,
                "mitre_attack_version": mitre_version,
                "scope": scope,
                "method": "FINE_TUNED_LLM",
                "model": model,
            }

        return result_json

    container = get_container(result_json)

    entries = []

    for veris_item in veris_scope_data:
        veris_id = veris_item.get("capability_id", "")
        raw_entry = find_raw_entry(container, veris_item)

        attack_ids = extract_attack_ids(raw_entry)
        justification = extract_justification(raw_entry)

        mitre_mappings = []

        for attack_id in attack_ids:
            attack_id = clean_attack_id(attack_id)

            if attack_id:
                mitre_mappings.append(
                    build_mitre_mapping(
                        attack_id=attack_id,
                        justification=justification,
                    )
                )

        entries.append(
            {
                "veris_id": veris_id,
                "veris_category": veris_item.get("capability_group", scope),
                "veris_label": veris_item.get("value", ""),
                "no_mapping_found": len(mitre_mappings) == 0,
                "mitre_mappings": mitre_mappings,
                "ambiguous": len(mitre_mappings) > 1,
                "notes": "Normalisé depuis la sortie LLM.",
            }
        )

    return {
        "metadata": {
            "veris_version": veris_version,
            "mitre_attack_version": mitre_version,
            "scope": scope,
            "method": "FINE_TUNED_LLM",
            "model": model,
        },
        "veris_to_mitre": entries,
    }

def split_batches(items, batch_size):
    if batch_size is None:
        return [items]

    batches = []

    for index in range(0, len(items), batch_size):
        batches.append(items[index:index + batch_size])

    return batches


def merge_batch_results(results, veris_version, mitre_version, scope, model):
    all_entries = []

    for result in results:
        for entry in result.get("veris_to_mitre", []):
            all_entries.append(entry)

    return {
        "metadata": {
            "veris_version": veris_version,
            "mitre_attack_version": mitre_version,
            "scope": scope,
            "method": "FINE_TUNED_LLM",
            "model": model,
        },
        "veris_to_mitre": all_entries,
    }

def limit_mappings_per_veris(payload, max_mappings_per_veris):
    if max_mappings_per_veris is None:
        return payload

    if not isinstance(payload, dict):
        return payload

    entries = payload.get("veris_to_mitre", [])

    if not isinstance(entries, list):
        return payload

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        mappings = entry.get("mitre_mappings", [])

        if not isinstance(mappings, list):
            entry["mitre_mappings"] = []
            entry["no_mapping_found"] = True
            entry["ambiguous"] = False
            continue

        cleaned = []
        seen = set()

        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue

            attack_id = mapping.get("sub_technique_id") or mapping.get("technique_id")

            if not attack_id:
                continue

            if attack_id in seen:
                continue

            seen.add(attack_id)
            cleaned.append(mapping)

        cleaned = cleaned[:max_mappings_per_veris]

        entry["mitre_mappings"] = cleaned
        entry["no_mapping_found"] = len(cleaned) == 0
        entry["ambiguous"] = len(cleaned) > 1

    return payload

# -------------- Main
def main() -> None:
    load_dotenv("dev.env")
    load_dotenv(".env")

    parser = build_arg_parse()
    args = parser.parse_args()

    path_data_work: Path | None = args.dw
    path_mitre: Path | None = args.m
    path_veris: Path | None = args.v

    if (path_mitre is None) ^ (path_veris is None):
        parser.error("Argument -m and -v should be use together")

    if path_mitre is None and path_veris is None and path_data_work is None:
        parser.error("At least -dw or -m AND -v is needed")

    if path_data_work is not None:
        path_veris, path_mitre = find_work_files(Path(path_data_work))

    veris_data, veris_version = get_data(path_veris)
    mitre_data, mitre_version = get_data(path_mitre)

    print(f"ATT&CK MITRE version: {mitre_version}")
    print(f"VERIS version: {veris_version}")

    reference = f"veris-{veris_version}_attack-{mitre_version}-enterprise"

    output_dir = (
        ROOT_DIR
        / "Resultat"
        / "Resultat_FINE_TUNE"
        / f"{reference}_{args.output_name}"
    )

    client = None

    if not args.mock:
        api_key = os.getenv("TOGETHER_API_KEY")

        if not api_key:
            raise RuntimeError("TOGETHER_API_KEY manquante dans dev.env ou .env")

        client = Together(api_key=api_key)

    manifest = {
        "reference": reference,
        "method": "FINE_TUNED_LLM",
        "model": args.model,
        "mock": args.mock,
        "batch_size": args.batch_size,
        "top_k_attack": args.top_k_attack,
        "files": [],
    }

    for scope in SCOPES:
        print(f"\nTraitement du scope : {scope}")

        veris_scope_data = filter_veris_by_scope(veris_data, scope)

        if args.limit_per_scope is not None:
            veris_scope_data = veris_scope_data[:args.limit_per_scope]

        batches = split_batches(veris_scope_data, args.batch_size)

        batch_results = []

        for batch_index, batch_items in enumerate(batches, start=1):
            print(f"  Batch {batch_index}/{len(batches)} : {len(batch_items)} éléments")

            if args.mock:
                result_json = mock_response(
                    veris_version=veris_version,
                    attack_version=mitre_version,
                    scope=scope,
                    veris_items=batch_items,
                )

            else:
                attack_candidates = select_attack_candidates_for_scope(
                    veris_items=batch_items,
                    attack_data=mitre_data,
                    top_k=args.top_k_attack,
                )

                user_prompt = create_user_prompt(
                    veris_version=veris_version,
                    attack_version=mitre_version,
                    data_veris=batch_items,
                    data_attack=attack_candidates,
                    attack_domain="Enterprise",
                    capability_group=scope,
                )

                try:
                    result_json = run_llm(
                        client=client,
                        user_prompt=user_prompt,
                        model=args.model,
                    )

                except Exception as error:
                    print(f"Erreur LLM sur batch {batch_index}, fallback vide : {error}")

                    result_json = mock_response(
                        veris_version=veris_version,
                        attack_version=mitre_version,
                        scope=scope,
                        veris_items=batch_items,
                    )

            result_json = normalize_prompt_payload(
                result_json=result_json,
                veris_scope_data=batch_items,
                veris_version=veris_version,
                mitre_version=mitre_version,
                scope=scope,
                model=args.model,
            )
            result_json = limit_mappings_per_veris(
                payload=result_json,
                max_mappings_per_veris=args.max_mappings_per_veris,
            )

            batch_results.append(result_json)

        final_result = merge_batch_results(
            results=batch_results,
            veris_version=veris_version,
            mitre_version=mitre_version,
            scope=scope,
            model=args.model,
        )

        output_file = output_dir / f"{scope}.json"
        write_json(output_file, final_result)

        manifest["files"].append(
            {
                "scope": scope,
                "file": str(output_file),
                "entries": len(veris_scope_data),
                "batches": len(batches),
            }
        )

        print(f"Fichier généré : {output_file}")

    # Important : on ne génère pas manifest.json dans Resultat,
    # sinon le comparateur peut le marquer BAD.
    # write_json(output_dir / "manifest.json", manifest)

    print("\nFINE_TUNED_LLM terminé.")
    print(f"Résultats écrits dans : {output_dir}")

if __name__ == "__main__":
    main()

"""
try:
    with open("", "x", encoding="utf-8") as f:
        f.write("response.choices[0].message.content")
    except FileExistsError:
        print("file already exists")
"""
