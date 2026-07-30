"""Configuration du RAG VERIS -> ATT&CK avec génération via Together.ai.

Même pipeline que Solution_RAG (embeddings locaux + ChromaDB), mais la
décision de mapping est déléguée à un LLM cloud (API compatible OpenAI).

Clés / secrets : `dev.env` à la racine du dépôt SIEM, ou `dev.env` / `.env`
dans ce dossier. Rien n'est écrit en dur dans le code.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

SOLUTION_DIR = Path(__file__).resolve().parent
# Solution_RAG_Together/ (peut être déplacé dans l'arborescence)
TOGETHER_ROOT = SOLUTION_DIR.parent


def _find_repo_root() -> Path:
    """Remonte jusqu'à la racine SIEM (data_for_work + Resultat)."""
    for candidate in [SOLUTION_DIR, *SOLUTION_DIR.parents]:
        if (candidate / "data_for_work").is_dir() and (candidate / "Resultat").is_dir():
            return candidate
    raise FileNotFoundError(
        "Racine du dépôt SIEM introuvable (dossiers data_for_work et Resultat)."
    )


REPO_ROOT = _find_repo_root()

load_dotenv(REPO_ROOT / "dev.env")
load_dotenv(TOGETHER_ROOT / "dev.env")
load_dotenv(SOLUTION_DIR / "dev.env")
load_dotenv(SOLUTION_DIR / ".env")
load_dotenv(".env")


# ==================== VERSIONS ====================
VERIS_VERSION = os.getenv("RAG_VERIS_VERSION", "1.4.1")
ATTACK_VERSION = os.getenv("RAG_ATTACK_VERSION", "19.1")

TARGET_REF = f"veris-{VERIS_VERSION}_attack-{ATTACK_VERSION}-enterprise"
WORK_SUBDIR = f"attack-{ATTACK_VERSION}_veris-{VERIS_VERSION}"


# ==================== CHEMINS ====================
DATA_FOR_WORK = REPO_ROOT / "data_for_work"
RESULTAT_DIR = REPO_ROOT / "Resultat"
# Dossier de sortie dédié (ne mélange pas avec le RAG retrieval local).
RESULTAT_RAG_DIR = RESULTAT_DIR / "Resultat_RAG_Together"

WORK_DIR = DATA_FOR_WORK / WORK_SUBDIR
VERIS_FILE = WORK_DIR / f"veris_{VERIS_VERSION}.json"
ATTACK_FILE = WORK_DIR / f"attack_{ATTACK_VERSION}.json"


# ==================== GÉNÉRATION ====================
# Backend unique de cette solution : LLM Together.ai.
GENERATOR = os.getenv("RAG_GENERATOR", "together").lower()


# ==================== TOGETHER.AI ====================
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "").strip()
TOGETHER_BASE_URL = os.getenv(
    "TOGETHER_BASE_URL", "https://api.together.ai/v1"
).strip()
TOGETHER_CHAT_MODEL = os.getenv(
    "TOGETHER_CHAT_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo"
).strip()


# ==================== EMBEDDINGS LOCAUX ====================
# Le retrieval reste local (sentence-transformers) ; seul le LLM est cloud.
LOCAL_EMBEDDING_MODEL = os.getenv(
    "RAG_LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)


# ==================== CHROMADB ====================
CHROMA_PATH = str(
    Path(os.getenv("RAG_CHROMA_PATH", SOLUTION_DIR / "db" / "chroma_store")).resolve()
)
ATTACK_COLLECTION = os.getenv("RAG_ATTACK_COLLECTION", "attack_techniques")
EXAMPLES_COLLECTION = os.getenv("RAG_EXAMPLES_COLLECTION", "expert_examples")


# ==================== RETRIEVAL / GÉNÉRATION ====================
TOP_K_TECHNIQUES = int(os.getenv("RAG_TOP_K_TECHNIQUES", "20"))
TOP_M_EXAMPLES = int(os.getenv("RAG_TOP_M_EXAMPLES", "5"))
EMBEDDING_BATCH_SIZE = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "64"))
GENERATION_TEMPERATURE = float(os.getenv("RAG_GENERATION_TEMPERATURE", "0.1"))
# Tokens max pour la réponse JSON du LLM.
GENERATION_MAX_TOKENS = int(os.getenv("RAG_GENERATION_MAX_TOKENS", "800"))


# ==================== GROUPES VERIS ====================
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
    if GENERATOR != "together":
        raise ValueError(
            f"Backend de génération inconnu : {GENERATOR}. "
            "Cette solution n'accepte que RAG_GENERATOR=together."
        )
    if not TOGETHER_API_KEY:
        raise ValueError(
            "TOGETHER_API_KEY manquante. "
            "Ajoutez-la dans Solution_RAG_Together/dev.env "
            "(ou veris_mapping/dev.env / racine SIEM)."
        )
    if not VERIS_FILE.is_file():
        raise FileNotFoundError(f"Fichier VERIS introuvable : {VERIS_FILE}")
    if not ATTACK_FILE.is_file():
        raise FileNotFoundError(f"Fichier ATT&CK introuvable : {ATTACK_FILE}")
    print("Configuration validée.")


if __name__ == "__main__":
    print("Generator      :", GENERATOR)
    print("Together model :", TOGETHER_CHAT_MODEL)
    print("Together URL   :", TOGETHER_BASE_URL)
    print("API key set    :", bool(TOGETHER_API_KEY))
    print("Embeddings     :", LOCAL_EMBEDDING_MODEL)
    print("Racine dépôt   :", REPO_ROOT)
    print("Version cible  :", TARGET_REF)
    print("VERIS file     :", VERIS_FILE)
    print("ATT&CK file    :", ATTACK_FILE)
    print("Chroma path    :", CHROMA_PATH)
    print("Sortie         :", RESULTAT_RAG_DIR)
    print("Exemples dirs  :", [p.name for p in list_example_work_dirs()])
    validate_config()
