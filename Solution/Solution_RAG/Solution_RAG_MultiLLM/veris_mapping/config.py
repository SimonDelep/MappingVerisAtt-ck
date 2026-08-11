"""Configuration du RAG multi-LLM VERIS -> ATT&CK (précision).

Même pipeline que Solution_RAG_Together (embeddings locaux + ChromaDB), mais
la décision de mapping est déléguée à N modèles cloud (API OpenAI-compatible /
Together.ai), sélectionnés en phase 1 via RAG_MULTI_LLM_MODELS.

Clés / secrets : `dev.env` / `.dev.env` à la racine SIEM.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

SOLUTION_DIR = Path(__file__).resolve().parent
MULTI_ROOT = SOLUTION_DIR.parent


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
load_dotenv(REPO_ROOT / ".dev.env")
load_dotenv(MULTI_ROOT / "dev.env")
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
RESULTAT_RAG_DIR = RESULTAT_DIR / "Resultat_RAG_MultiLLM"

WORK_DIR = DATA_FOR_WORK / WORK_SUBDIR
VERIS_FILE = WORK_DIR / f"veris_{VERIS_VERSION}.json"
ATTACK_FILE = WORK_DIR / f"attack_{ATTACK_VERSION}.json"


# ==================== GÉNÉRATION ====================
GENERATOR = os.getenv("RAG_GENERATOR", "together").lower()


# ==================== API OpenAI-compatible / Together ====================
TOGETHER_API_KEY = (
    os.getenv("TOGETHER_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
)
TOGETHER_BASE_URL = (
    os.getenv("TOGETHER_BASE_URL", "").strip()
    or os.getenv("OPENAI_BASE_URL", "").strip()
    or "https://api.together.ai/v1"
)

# Défauts phase 1 (serverless smoke-testés) — override via RAG_MULTI_LLM_MODELS.
_DEFAULT_MODELS = (
    "meta-llama/Llama-3.3-70B-Instruct-Turbo,"
    "Qwen/Qwen2.5-7B-Instruct-Turbo,"
    "moonshotai/Kimi-K3"
)


def _parse_models(raw: str) -> list[str]:
    models: list[str] = []
    for part in (raw or "").split(","):
        mid = part.strip()
        if mid and mid not in models:
            models.append(mid)
    return models


MULTI_LLM_MODELS = _parse_models(
    os.getenv("RAG_MULTI_LLM_MODELS", _DEFAULT_MODELS)
)
# Modèle courant pour un run unitaire (override CLI).
TOGETHER_CHAT_MODEL = os.getenv(
    "TOGETHER_CHAT_MODEL",
    MULTI_LLM_MODELS[0] if MULTI_LLM_MODELS else _DEFAULT_MODELS.split(",")[0],
).strip()


def model_slug(model_id: str) -> str:
    """Slug court pour les dossiers de sortie (stable, filesystem-safe)."""
    base = model_id.split("/")[-1]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()
    return slug[:48] or "model"


# ==================== EMBEDDINGS LOCAUX ====================
LOCAL_EMBEDDING_MODEL = os.getenv(
    "RAG_LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)


# ==================== CHROMADB ====================
# Par défaut store dédié ; peut pointer vers un chroma déjà ingéré via env.
CHROMA_PATH = str(
    Path(os.getenv("RAG_CHROMA_PATH", SOLUTION_DIR / "db" / "chroma_store")).resolve()
)
ATTACK_COLLECTION = os.getenv("RAG_ATTACK_COLLECTION", "attack_techniques")
EXAMPLES_COLLECTION = os.getenv("RAG_EXAMPLES_COLLECTION", "expert_examples")


# ==================== RETRIEVAL / GÉNÉRATION ====================
# top_k relevé : le LLM filtre (précision) ; plus de candidats à examiner.
TOP_K_TECHNIQUES = int(os.getenv("RAG_TOP_K_TECHNIQUES", "40"))
TOP_M_EXAMPLES = int(os.getenv("RAG_TOP_M_EXAMPLES", "5"))
EMBEDDING_BATCH_SIZE = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "64"))
GENERATION_TEMPERATURE = float(os.getenv("RAG_GENERATION_TEMPERATURE", "0.1"))
GENERATION_MAX_TOKENS = int(os.getenv("RAG_GENERATION_MAX_TOKENS", "1200"))


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
    """Dossiers data_for_work des *autres* versions (exemples experts)."""
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
            "TOGETHER_API_KEY (ou OPENAI_API_KEY) manquante. "
            "Ajoutez-la dans .dev.env à la racine SIEM."
        )
    if not MULTI_LLM_MODELS:
        raise ValueError(
            "Aucun modèle dans RAG_MULTI_LLM_MODELS. "
            "Voir Solution_RAG_MultiLLM/MODELS.md (phase 1)."
        )
    if not VERIS_FILE.is_file():
        raise FileNotFoundError(f"Fichier VERIS introuvable : {VERIS_FILE}")
    if not ATTACK_FILE.is_file():
        raise FileNotFoundError(f"Fichier ATT&CK introuvable : {ATTACK_FILE}")
    print("Configuration validée.")


if __name__ == "__main__":
    print("Generator      :", GENERATOR)
    print("Modèles multi  :", MULTI_LLM_MODELS)
    print("Modèle courant :", TOGETHER_CHAT_MODEL)
    print("Together URL   :", TOGETHER_BASE_URL)
    print("API key set    :", bool(TOGETHER_API_KEY))
    print("Embeddings     :", LOCAL_EMBEDDING_MODEL)
    print("top_k / top_m  :", TOP_K_TECHNIQUES, TOP_M_EXAMPLES)
    print("Racine dépôt   :", REPO_ROOT)
    print("Version cible  :", TARGET_REF)
    print("VERIS file     :", VERIS_FILE)
    print("ATT&CK file    :", ATTACK_FILE)
    print("Chroma path    :", CHROMA_PATH)
    print("Sortie         :", RESULTAT_RAG_DIR)
    print("Exemples dirs  :", [p.name for p in list_example_work_dirs()])
    validate_config()
