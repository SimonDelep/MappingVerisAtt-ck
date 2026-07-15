from together import Together, AsyncTogether
import asyncio
import sys
import os
import argparse
import json
from pathlib import Path

# -------------------- ROOT PWD
pwd = os.getcwd()
if(pwd.split("/")[-1]=="Solution_PROMPT"):
    DEFAULT_DB_MAPPING="../data_for_work/attack-19.1_veris-1.4.1/"
else:
    DEFAULT_DB_MAPPING=None
    print("None default dir for default mapping")

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
    return parser


# --------------------- PATH $ DATA



# --------------------- PROMPT
def create_user_prompt(veris_version:str="", attack_version:str="", data_veris:str="", data_attack:str="", attack_domain:str="Enterprise"):
    user_prompt="""\
Prend en compte le system-prompt.md pour repondre
Voici les données de référence à utiliser pour ce mapping bidirectionnel. N'utilise aucune autre source ni connaissance externe que celles indiquées ci-dessous.

## Version des référentiels:
    - Version VERIS schema: {veris_version}
    - Version MITRE ATT&CK (matrice): {attack_version}
    - ATT&CK Domain: {attack_domain}

## Périmètre à traiter dans cette réponse
Je veux que tu me traite toutes les données en rapport de la capability group TODO:capability

## Données VERIS (catégorie(s), vector(s), variety(ies) avec leurs descriptions/définitions)
{data_veris}

## Catalogue MITRE ATT&CK (techniques et sub-techniques avec ID, nom, description,tactique(s))
{data_attack}

## Instruction finale
Produis le mapping bidirectionnel complet (VERIS → MITRE puis MITRE → VERIS) entre tous les éléments listés ci-dessus, en respectant strictement le format JSON et les règles définies dans le system prompt.
Traite tous les éléments fournis dans les deux sens, sans en omettre aucun, même pour indiquer "no_mapping_found": true.\
         """.format(veris_version=veris_version ,attack_version=attack_version , attack_domain=attack_domain , data_veris=data_veris , data_attack=data_attack )
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
    parser = build_arg_parse()
    args = parser.parse_args()

    # args
    path_data_work: Path | None = args.dw
    path_mitre: Path | None = args.m
    path_veris: Path | None = args.v

    if (path_mitre is None) ^ (path_veris is None):
        parser.error("Argument -m and -v should be use together")
    if path_mitre is None and path_veris is None and path_data_work is None:
        parser.error("At least -dw or -m AND -v is needed")

    if (path_data_work != None):
        data_work_fn = str(path_data_work).split("/")[-1]
        veris_fn = data_work_fn.split("_")[0]
        mitre_fn = data_work_fn.split("_")[1]

        path_veris = str(path_data_work) + "/" + veris_fn.replace("-", "_") + ".json"
        path_mitre = str(path_data_work) + "/" + mitre_fn.replace("-", "_") + ".json"
    
    # get data from json file (mitre & veris)
    veris_data, veris_version = get_data(path_veris)
    mitre_data, mitre_version = get_data(path_mitre)
    print(f"ATT&CK MITRE version: {mitre_version}\nVERIS version: {veris_version}")
    
    user_prompt = create_user_prompt(veris_version, mitre_version, veris_data, mitre_data)

    print(user_prompt)




if __name__ == "__main__":
    main()

"""
try:
    with open("", "x", encoding="utf-8") as f:
        f.write("response.choices[0].message.content")
    except FileExistsError:
        print("file already exists")
"""
