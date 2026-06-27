"""Configuration centralisée du RAG de mapping VERIS -> MITRE ATT&CK.

Toutes les clés/secrets restent dans `dev.env` (racine du dépôt SIEM) ou un
`.env` local ; rien n'est écrit en dur dans le code.

Le pipeline confronte deux référentiels bruts :
  - VERIS   : les capacités à mapper (les "questions")
  - ATT&CK  : les techniques candidates (les "candidats")
et, en option, les mappings experts des *anciennes* versions comme exemples.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Solution/Solution_RAG/veris_mapping/config.py -> racine = SIEM
REPO_ROOT = Path(__file__).resolve().parents[3]
SOLUTION_DIR = Path(__file__).resolve().parent

load_dotenv(REPO_ROOT / "dev.env")
load_dotenv(SOLUTION_DIR / "dev.env")
load_dotenv(SOLUTION_DIR / ".env")
load_dotenv(".env")


# ==================== VERSIONS ====================
# Version cible à mapper (= la version évaluée contre les experts).
VERIS_VERSION = os.getenv("RAG_VERIS_VERSION", "1.4.1")
ATTACK_VERSION = os.getenv("RAG_ATTACK_VERSION", "19.1")

# Référence "veris-x_attack-y-enterprise" attendue par compare_veris_mappings_v2.
TARGET_REF = f"veris-{VERIS_VERSION}_attack-{ATTACK_VERSION}-enterprise"
WORK_SUBDIR = f"attack-{ATTACK_VERSION}_veris-{VERIS_VERSION}"


# ==================== CHEMINS ====================
DATA_FOR_WORK = REPO_ROOT / "data_for_work"
RESULTAT_DIR = REPO_ROOT / "Resultat"
RESULTAT_RAG_DIR = RESULTAT_DIR / "Resultat_RAG"

WORK_DIR = DATA_FOR_WORK / WORK_SUBDIR
VERIS_FILE = WORK_DIR / f"veris_{VERIS_VERSION}.json"
ATTACK_FILE = WORK_DIR / f"attack_{ATTACK_VERSION}.json"


# ==================== FOURNISSEUR (local / azure) ====================
# "local" : embeddings sentence-transformers + génération sans Azure.
# "azure" : embeddings + LLM via Azure OpenAI (nécessite dev.env).
PROVIDER = os.getenv("RAG_PROVIDER", "local").lower()

# Backend de génération :
#   - "retrieval" : sélection par similarité sémantique (aucun LLM).
#   - "local_llm" : LLM local via transformers.
#   - "llm"       : LLM Azure OpenAI.
_default_generator = "llm" if PROVIDER == "azure" else "retrieval"
GENERATOR = os.getenv("RAG_GENERATOR", _default_generator).lower()


# ==================== EMBEDDINGS LOCAUX ====================
LOCAL_EMBEDDING_MODEL = os.getenv(
    "RAG_LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
# Modèle LLM local (backend "local_llm").
LOCAL_LLM_MODEL = os.getenv("RAG_LOCAL_LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")


# ==================== SEUILS GÉNÉRATION "retrieval" ====================
# Similarité cosinus (= 1 - distance) au-dessus de laquelle un candidat est retenu.
RETRIEVAL_SIM_HIGH = float(os.getenv("RAG_RETRIEVAL_SIM_HIGH", "0.50"))
RETRIEVAL_SIM_MED = float(os.getenv("RAG_RETRIEVAL_SIM_MED", "0.38"))
# Nb max d'ajouts "exemple seul" (techniques suggérées par l'exemple le plus proche).
RETRIEVAL_MAX_EXAMPLE_ONLY = int(os.getenv("RAG_RETRIEVAL_MAX_EXAMPLE_ONLY", "12"))


# ==================== AZURE OPENAI ====================
OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT", "https://canadacentral.api.cognitive.microsoft.com/"
)
OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

# Noms des *déploiements* Azure (pas seulement des modèles).
OPENAI_EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "mon-embedding")
OPENAI_CHAT_MODEL = os.getenv("AZURE_OPENAI_CHAT_MODEL", "mon-llm-chat")


# ==================== CHROMADB ====================
CHROMA_PATH = str(
    Path(os.getenv("RAG_CHROMA_PATH", SOLUTION_DIR / "db" / "chroma_store")).resolve()
)
ATTACK_COLLECTION = os.getenv("RAG_ATTACK_COLLECTION", "attack_techniques")
EXAMPLES_COLLECTION = os.getenv("RAG_EXAMPLES_COLLECTION", "expert_examples")


# ==================== RETRIEVAL / GÉNÉRATION ====================
# Nombre de techniques ATT&CK candidates récupérées par capacité VERIS.
TOP_K_TECHNIQUES = int(os.getenv("RAG_TOP_K_TECHNIQUES", "20"))
# Nombre d'exemples de mappings experts (anciennes versions) récupérés.
TOP_M_EXAMPLES = int(os.getenv("RAG_TOP_M_EXAMPLES", "5"))
# Taille des lots d'embeddings (un appel API par lot).
EMBEDDING_BATCH_SIZE = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "64"))
# Température de génération (faible = déterministe).
GENERATION_TEMPERATURE = float(os.getenv("RAG_GENERATION_TEMPERATURE", "0.1"))


# ==================== GROUPES VERIS ====================
# Les 7 capability_groups officiels mappés vers ATT&CK.
CAPABILITY_GROUPS = [
    "action.hacking",
    "action.malware",
    "action.social",
    "attribute.integrity",
    "attribute.confidentiality",
    "attribute.availability",
    "value_chain.development",
]


def list_example_work_dirs() -> list[Path]:
    """Dossiers data_for_work des *autres* versions (exemples experts).

    On exclut explicitement la version cible pour éviter toute fuite de la
    vérité-terrain utilisée par l'évaluation.
    """
    dirs: list[Path] = []
    for path in sorted(DATA_FOR_WORK.glob("attack-*_veris-*")):
        if path.name == WORK_SUBDIR:
            continue
        if (path / "mapping_des_experts.json").is_file():
            dirs.append(path)
    return dirs


def validate_config() -> None:
    """Valide la présence des variables/fichiers essentiels."""
    needs_azure = PROVIDER == "azure" or GENERATOR == "llm"
    if needs_azure and not OPENAI_API_KEY:
        raise ValueError(
            "AZURE_OPENAI_API_KEY manquant alors que le mode Azure est demandé.\n"
            f"Renseignez-le dans {REPO_ROOT / 'dev.env'} (voir dev.env.example), "
            "ou passez en mode local (RAG_PROVIDER=local)."
        )
    if not VERIS_FILE.is_file():
        raise FileNotFoundError(f"Fichier VERIS introuvable : {VERIS_FILE}")
    if not ATTACK_FILE.is_file():
        raise FileNotFoundError(f"Fichier ATT&CK introuvable : {ATTACK_FILE}")
    print("Configuration validée.")


if __name__ == "__main__":
    print("Provider       :", PROVIDER)
    print("Generator      :", GENERATOR)
    print("Embeddings     :", LOCAL_EMBEDDING_MODEL if PROVIDER == "local" else OPENAI_EMBEDDING_MODEL)
    print("Racine dépôt   :", REPO_ROOT)
    print("Version cible  :", TARGET_REF)
    print("VERIS file     :", VERIS_FILE)
    print("ATT&CK file    :", ATTACK_FILE)
    print("Chroma path    :", CHROMA_PATH)
    print("Exemples dirs  :", [p.name for p in list_example_work_dirs()])
