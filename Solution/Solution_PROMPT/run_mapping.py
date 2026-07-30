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
            help="Modèle Together AI à utiliser",
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
            "--output-name",
            default="PROMPT",
            help="Nom du dossier de sortie",
            )
    parser.add_argument(
            "--mock",
            action="store_true",
            help="Mode test sans appel API",
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


def run_llm(client, user_prompt, model):
    messages = [
        {
            "role": "user",
            "content": user_prompt,
        }
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=4000,
    )

    content = response.choices[0].message.content

    try:
        return extract_json_object(content)

    except Exception as first_error:
        print("Réponse JSON invalide. Tentative de correction automatique...")

        correction_prompt = """
Le texte suivant devait être un JSON valide, mais il contient une erreur de format.

Corrige-le et retourne uniquement un objet JSON strictement valide.
N'ajoute aucune explication.
Utilise des guillemets doubles, null au lieu de None, et aucune virgule finale.

Texte à corriger :
""" + content

        correction_response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": correction_prompt,
                }
            ],
            temperature=0,
            max_tokens=4000,
        )

        corrected_content = correction_response.choices[0].message.content

        try:
            return extract_json_object(corrected_content)

        except Exception as second_error:
            debug_dir = Path("Resultat") / "debug_prompt_errors"
            debug_dir.mkdir(parents=True, exist_ok=True)

            debug_file = debug_dir / "last_invalid_response.txt"

            with open(debug_file, "w", encoding="utf-8") as file:
                file.write("=== REPONSE ORIGINALE ===\n")
                file.write(content)
                file.write("\n\n=== REPONSE CORRIGEE ===\n")
                file.write(corrected_content)

            raise ValueError(
                f"Impossible de parser la réponse JSON. Réponse sauvegardée dans {debug_file}"
            ) from second_error
    return extract_json_object(content)


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
        Path("Resultat")
        / "Resultat_PROMPT"
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
        "method": "PROMPT",
        "model": args.model,
        "mock": args.mock,
        "files": [],
    }

    for scope in SCOPES:
        print(f"\nTraitement du scope : {scope}")

        veris_scope_data = filter_veris_by_scope(veris_data, scope)

        if args.limit_per_scope is not None:
            veris_scope_data = veris_scope_data[:args.limit_per_scope]

        if args.mock:
            result_json = mock_response(
                veris_version=veris_version,
                attack_version=mitre_version,
                scope=scope,
                veris_items=veris_scope_data,
            )

        else:
            attack_candidates = select_attack_candidates_for_scope(
                veris_items=veris_scope_data,
                attack_data=mitre_data,
                top_k=args.top_k_attack,
            )

            user_prompt = create_user_prompt(
                veris_version=veris_version,
                attack_version=mitre_version,
                data_veris=veris_scope_data,
                data_attack=attack_candidates,
                attack_domain="Enterprise",
                capability_group=scope,
            )

            result_json = run_llm(
                client=client,
                user_prompt=user_prompt,
                model=args.model,
            )

        output_file = output_dir / f"{scope}.json"
        write_json(output_file, result_json)

        manifest["files"].append(
            {
                "scope": scope,
                "file": str(output_file),
                "entries": len(veris_scope_data),
            }
        )

        print(f"Fichier généré : {output_file}")

    write_json(output_dir / "manifest.json", manifest)

    print("\nPROMPT terminé.")
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
