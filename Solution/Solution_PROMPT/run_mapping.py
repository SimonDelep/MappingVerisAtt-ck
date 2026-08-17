from together import AsyncTogether, RateLimitError, APITimeoutError
import asyncio
import sys
import os
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

CAPABILITY=["action.hacking", "action.malware", "attribute.integrity", "attribute.confidentiality", "attribute.availability", "action.social", "value_chain.development"]

# Global variables 
REQUEST_TIMEOUT_S = 900.0
MAX_PARALLEL_REQUESTS = 1
RETRY_SLEEP_S = [5, 15, 30]
MAX_TOKENS = 100000
ATTACK_DESC_MAX = 250

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
Produis UNIQUEMENT le mapping VERIS → MITRE au format JSON du system prompt (IDs seulement).
- veris_to_mitre: une entrée pour CHAQUE capacité VERIS fournie, avec la liste complète des attack_ids pertinents (pas de plafond).
- mitre_to_veris: [].
Réponds uniquement avec un JSON valide et complet, sans markdown.\
         """.format(veris_version=veris_version ,attack_version=attack_version , attack_domain=attack_domain , data_veris=data_veris , data_attack=data_attack , capability=capability )
    return user_prompt


# -------------------- DB DATA
def get_data(data_path:str) -> tuple[str, str]:
    try:
        with open(data_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        version = data["version"]
        return data, version
    except FileNotFoundError:
        print(f"error: {Path(data_path).name} file was not found")
        raise SystemExit(1)

# -------------------- Filter & compact data to optimize token size limitation
def filter_veris_for_capability(veris_data: dict, capability: str) -> dict:
    caps = []
    for c in veris_data["capabilities"]:
        if c.get("capability_group") != capability:
            continue
        caps.append({
            "capability_id": c["capability_id"],
            "value": c.get("value", ""),
            "description": c.get("description", ""),
        })
    return {
        "version": veris_data["version"],
        "capability_group": capability,
        "capability_count": len(caps),
        "capabilities": caps,
    }

def compact_attack(attack_data: dict, max_desc: int = ATTACK_DESC_MAX) -> dict:
    techs = []
    for t in attack_data["techniques"]:
        desc = t.get("description") or ""
        if len(desc) > max_desc:
            desc = desc[:max_desc].rsplit(" ", 1)[0] + "..."
        techs.append({
            "attack_id": t["attack_id"],
            "name": t["name"],
            "tactics": t.get("tactics", []),
            "description": desc,
        })
    return {
        "version": attack_data["version"],
        "technique_count": len(techs),
        "techniques": techs,
    }

# -------------------- LLM
async def run_llm_parallel(async_client, user_prompt: str, model: str, system_prompt: str = None, sem: asyncio.Semaphore | None = None, capability: str = ""):
    response = None
    last_error = None
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    async def _once():
        return await async_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=0,
        )

    for attempt, sleep_time in enumerate(RETRY_SLEEP_S, start=1):
        try:
            print(f"[{capability}] request attempt {attempt}/{len(RETRY_SLEEP_S)}...", flush=True)

            if sem is None:
                response = await _once()
            else:
                async with sem:
                    response = await _once()

            msg = response.choices[0].message
            content = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
            finish = getattr(response.choices[0], "finish_reason", None)
            print(f"[{capability}] finish_reason={finish} chars={len(content)}", flush=True)

            if finish == "length":
                # Retenter le même prompt ne change rien: la sortie dépasse max_tokens.
                raise RuntimeError(
                    f"Truncated output (finish_reason=length, chars={len(content)}). "
                    "Ne sera pas retenté."
                )
            if not content:
                raise RuntimeError(f"Empty content (finish_reason={finish})")

            print(f"[{capability}] done.", flush=True)
            return content
        except RuntimeError as e:
            last_error = e
            print(f"[{capability}] {type(e).__name__}: {e}", flush=True)
            if "Truncated output" in str(e):
                break
            if attempt < len(RETRY_SLEEP_S):
                print(f"[{capability}] retry in {sleep_time}s...", flush=True)
                await asyncio.sleep(sleep_time)
        except (RateLimitError, APITimeoutError) as e:
            last_error = e
            print(f"[{capability}] {type(e).__name__}: {e}", flush=True)
            if attempt < len(RETRY_SLEEP_S):
                print(f"[{capability}] retry in {sleep_time}s...", flush=True)
                await asyncio.sleep(sleep_time)
    raise RuntimeError(
        f"Failed after retries for {capability or 'capability'}: {last_error!r}"
    )

# --------------- Run Parallel Request Per Capabilities
async def map_per_capability(async_client, mapping_prompt_capability: dict, system_prompt: str, model: str, output_dir: Path) -> dict:
    capabilities = list(mapping_prompt_capability.keys())
    results = {}
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    def _load_valid(path: Path) -> str | None:
        if not path.exists() or path.stat().st_size <= 0:
            return None
        try:
            text = path.read_text(encoding="utf-8")
            json.loads(text)
            return text
        except json.JSONDecodeError:
            return None

    for c in capabilities:
        raw_file = raw_dir / f"{c}.json"
        out_file = output_dir / f"{c}.json"

        existing = _load_valid(raw_file) or _load_valid(out_file)
        if existing is not None:
            # Si seul le final enrichi existe, on skip la génération LLM
            if _load_valid(raw_file) is None and _load_valid(out_file) is not None:
                print(f"[{c}] skip (mapping final déjà présent) -> {out_file}", flush=True)
            else:
                print(f"[{c}] skip (brut LLM déjà présent) -> {raw_file}", flush=True)
            results[c] = existing
            continue

        print(f"\n=== Starting {c} ===", flush=True)
        try:
            content = await run_llm_parallel(
                async_client, mapping_prompt_capability[c], model, system_prompt,
                sem=None, capability=c,
            )
            if content.startswith("```"):
                content = content.strip("`")
                if content.startswith("json"):
                    content = content[4:].strip()
            json.loads(content)
            raw_file.write_text(content, encoding="utf-8")
            results[c] = content
            print(f"[{c}] raw written -> {raw_file}", flush=True)
        except Exception as e:
            print(f"[{c}] FAILED: {e}", flush=True)
            continue
    return results

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

    if (path_data_work is not None) and (path_attack is None) and (path_veris is None):
        # Sur Windows, Path.name est fiable (split("/") casse avec les \).
        path_data_work = Path(path_data_work)
        data_work_fn = path_data_work.name  # ex: attack-19.1_veris-1.4.1
        attack_fn, veris_fn = data_work_fn.split("_", 1)
        path_veris = path_data_work / f"{veris_fn.replace('-', '_')}.json"
        path_attack = path_data_work / f"{attack_fn.replace('-', '_')}.json"
    
    # get data from json file (mitre & veris)
    veris_data, veris_version = get_data(path_veris)
    attack_data, attack_version = get_data(path_attack)
    print(f"ATT&CK MITRE version: {attack_version}\nVERIS version: {veris_version}")

    # init together connexion
    load_dotenv(Path(__file__).resolve().parents[2] / ".dev.env")
    async_client = AsyncTogether(
        api_key=os.environ.get("TOGETHER_API_KEY"),
        timeout=REQUEST_TIMEOUT_S,
    )
    
    attack_compact = compact_attack(attack_data)
    user_prompts = []
    for c in CAPABILITY:
        veris_c = filter_veris_for_capability(veris_data, c)
        user_prompts.append(
            create_user_prompt(
                veris_version,
                attack_version,
                json.dumps(veris_c, ensure_ascii=False),
                json.dumps(attack_compact, ensure_ascii=False),
                c,
            )
        )
    mapping_prompt_capability = dict(zip(CAPABILITY, user_prompts))
    system_prompt = (Path(__file__).parent / "system-prompt.md").read_text(encoding="utf-8")
   
    model_code = input("Choose a model between: \n(1) - Kimi-K3 \n(2) - DeepSeek-V4-Pro\n")
    model = (
        "moonshotai/Kimi-K3" if model_code == "1"
        else "deepseek-ai/DeepSeek-V4-Pro" if model_code == "2"
        else None
    )
    if model == None:
        print("error: value out or range\n abort !")
        return
    print(f"Chosen model is {model}. \nGeneration of mapping...\n", flush=True)

    model_tag = "Kimi-K3" if model_code == "1" else "DeepSeek-V4-Pro"
    dir_name = f"veris-{veris_version}_attack-{attack_version}-enterprise_PROMPT_{model_tag}"
    full_path = OUTPUT_RESULT / dir_name
    full_path.mkdir(parents=True, exist_ok=True)

    llm_response = asyncio.run(
        map_per_capability(async_client, mapping_prompt_capability, system_prompt, model, full_path)
    )

    ok = [c for c in CAPABILITY if c in llm_response]
    ko = [c for c in CAPABILITY if c not in llm_response]
    print(f"\nDone. OK={ok}", flush=True)
    if ko:
        print(f"FAILED (à relancer): {ko}", flush=True)

    if ok:
        try:
            from reconstruct_mapping import reconstruct_directory

            raw_dir = full_path / "_raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            # S'assure que chaque OK a un brut dans _raw (génération fraîche)
            for c in ok:
                raw_file = raw_dir / f"{c}.json"
                if raw_file.exists() and raw_file.stat().st_size > 0:
                    continue
                # fallback: si seul le final existe, on ne peut pas ré-enrichir depuis IDs
                # (déjà enrichi) — reconstruct saura lire mitre_mappings aussi
                out_file = full_path / f"{c}.json"
                if out_file.exists() and out_file.stat().st_size > 0:
                    raw_file.write_text(out_file.read_text(encoding="utf-8"), encoding="utf-8")

            print(
                f"\nReconstruction mapping final (comparaison chercheurs) -> {full_path}",
                flush=True,
            )
            reconstruct_directory(raw_dir, full_path, veris_data, attack_data)
            print(f"Bruts LLM dans {raw_dir}", flush=True)
            print(f"Mappings finaux dans {full_path}/*.json", flush=True)
        except Exception as e:
            print(f"Reconstruction échouée: {e}", flush=True)
            print(
                "Tu peux relancer à la main: "
                f"python reconstruct_mapping.py -i {full_path}/_raw -o {full_path}",
                flush=True,
            )

    
if __name__ == "__main__":
    main()

