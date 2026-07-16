from together import AsyncTogether, RateLimitError
import asyncio
import sys
import os
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

CAPABILITY=["action.hacking", "action.malware", "attribute.integrity", "attribute.confidentiality", "attribute.availability", "action.social", "value_chain.development"]

# -------------------- ROOT PWD
DEFAULT_DB_MAPPING = Path(__file__).resolve().parents[2] / "data_for_work" / "attack-19.1_veris-1.4.1"
OUTPUT_RESULT = Path(__file__).resolve().parents[2] / "Resultat" / "Resultat_PROMPT" 

# -------------------- ArgParse
def build_arg_parse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
            description="Create a mapping between MITRE ATT&CK and Veris database with public LLM models",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Usage:
 $ python run_mapping -dw [path/to/data_for_work/combo-dir]
 # With custom versions of databases
 $ python run_mapping -a [path/to/mitre_attack] -v [path/to/veris]
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
            "-a",
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
    return parser


# --------------------- PROMPT
def create_user_prompt(veris_version:str="", attack_version:str="", data_veris:str="", data_attack:str="", capability:str="", attack_domain:str="Enterprise"):
    user_prompt="""\
Prend en compte le system-prompt.md pour repondre
Voici les données de référence à utiliser pour ce mapping bidirectionnel. N'utilise aucune autre source ni connaissance externe que celles indiquées ci-dessous.

## Version des référentiels:
    - Version VERIS schema: {veris_version}
    - Version MITRE ATT&CK (matrice): {attack_version}
    - ATT&CK Domain: {attack_domain}

## Périmètre à traiter dans cette réponse
Je veux que tu me traite toutes les données en rapport de la capability group {capability}

## Données VERIS (catégorie(s), vector(s), variety(ies) avec leurs descriptions/définitions)
{data_veris}

## Catalogue MITRE ATT&CK (techniques et sub-techniques avec ID, nom, description,tactique(s))
{data_attack}

## Instruction finale
Produis le mapping bidirectionnel complet (VERIS → MITRE puis MITRE → VERIS) entre tous les éléments listés ci-dessus, en respectant strictement le format JSON et les règles définies dans le system prompt.
Traite tous les éléments fournis dans les deux sens, sans en omettre aucun, même pour indiquer "no_mapping_found": true.\
         """.format(veris_version=veris_version ,attack_version=attack_version , attack_domain=attack_domain , data_veris=data_veris , data_attack=data_attack , capability=capability )
    return user_prompt


# -------------------- DB DATA
def get_data(data_path:str) -> tuple[str, str]:
    try:
        with open(data_path, "r") as file:
            data = json.load(file)
        version = data["version"]
        return data, version
    except FileNotFoundError:
        print("error:"+data_path.split("/")[-1]+"file was not found")
        raise SystemExit(1)

# -------------------- LLM
async def run_llm_parallel(async_client, user_prompt:str, model:str, system_prompt:str=None):
    response = None
    for sleep_time in [1,2,4]:
        try:
            messages=[]
            if system_prompt:
                messages.append({"role":"system", "content":system_prompt})
            messages.append({"role":"user", "content":user_prompt})
            
            response= await async_client.chat.completions.create(
                    model=model,
                    messages=messages
            )
            break
        except RateLimitError as e:
            print(e)
            await asyncio.sleep(sleep_time)
    if (response==None):
        raise RuntimeError("Failed after retry, rate limit !!")
    return response.choices[0].message.content

# --------------- Run Parallel Request Per Capabilities
async def map_per_capability(async_client, mapping_prompt_capability: dict, system_prompt: str, model: str) -> dict:
    capabilities = list(mapping_prompt_capability.keys())
    tasks = [
            run_llm_parallel(async_client, mapping_prompt_capability[c], model, system_prompt)
            for c in capabilities
            ]
    results = await asyncio.gather(*tasks)
    return dict(zip(capabilities, results))

def write_mapping_per_capability(full_path:str, capabilities:list, dict_res:dict):
    for c in capabilities:
        file_pwd = full_path / f"{c}.json"
        json_file = open(file_pwd, "a")
        json_file.write(dict_res[c])
        json_file.close()


# -------------- Main
def main() -> None:
    parser = build_arg_parse()
    args = parser.parse_args()

    # args
    path_data_work: Path | None = args.dw
    path_attack: Path | None = args.a
    path_veris: Path | None = args.v

    if (path_attack is None) ^ (path_veris is None):
        parser.error("Argument -m and -v should be use together")
    if path_attack is None and path_veris is None and path_data_work is None:
        parser.error("At least -dw or -m AND -v is needed")

    if (path_data_work != None) and (path_attack == None) and (path_veris == None):
        data_work_fn = str(path_data_work).split("/")[-1]
        attack_fn = data_work_fn.split("_")[0]
        veris_fn = data_work_fn.split("_")[1]

        path_veris = str(path_data_work) + "/" + veris_fn.replace("-", "_") + ".json"
        path_attack = str(path_data_work) + "/" + attack_fn.replace("-", "_") + ".json"
    
    # get data from json file (mitre & veris)
    veris_data, veris_version = get_data(path_veris)
    attack_data, attack_version = get_data(path_attack)
    print(f"ATT&CK MITRE version: {attack_version}\nVERIS version: {veris_version}")

    # init together connexion
    load_dotenv(Path(__file__).resolve().parents[2] / ".dev.env")
    async_client = AsyncTogether(
        api_key=os.environ.get("TOGETHER_API_KEY")
    )
    
    user_prompts = []
    for c in CAPABILITY:
        user_prompts.append(create_user_prompt(veris_version, attack_version, veris_data, attack_data, c))
    mapping_prompt_capability = dict(zip(CAPABILITY, user_prompts))
    system_prompt = (Path(__file__).parent / "system-prompt.md").read_text(encoding="utf-8")
   
    model_code = input("Choose a model between: \n(1) - Qwen3-235B-A22B-Intruct-2507-tput \n(2) - DeepSeek-R1-0528\n")
    model = (
        "Qwen/Qwen3-235B-A22B-Instruct-2507-tput" if model_code == "1"
        else "deepseek-ai/DeepSeek-R1-0528" if model_code == "2"
        else None
    )
    if model == None:
        print("error: value out or range\n abort !")
        return
    print(f"Chosen model is {model}. \nGeneration of mapping...\n")

    llm_response = asyncio.run(
        map_per_capability(async_client, mapping_prompt_capability, system_prompt, model)
    )

    # create output folder w attack & veris version
    dir_name = f"veris-{veris_version}_attack-{attack_version}-enterprise_PROMPT"
    full_path = OUTPUT_RESULT / dir_name 
    try:
        os.mkdir(full_path)
    except FileExistsError:
        print(f"Directory '{full_path}' already exists")
    except PermissionError:
        print(f"Permission denied: Unable to create '{full_path}'")
    except Exception as e:
        print(f"An error occurred: {e}")

    # write json generated by llm
    write_mapping_per_capability(full_path, CAPABILITY, llm_response)

if __name__ == "__main__":
    main()

