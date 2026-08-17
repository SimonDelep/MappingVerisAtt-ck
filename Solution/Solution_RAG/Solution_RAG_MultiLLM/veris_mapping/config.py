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
# v2 Llama : plus de candidats / exemples pour remonter le rappel et le volume.
TOP_K_TECHNIQUES = int(os.getenv("RAG_TOP_K_TECHNIQUES", "60"))
TOP_M_EXAMPLES = int(os.getenv("RAG_TOP_M_EXAMPLES", "8"))
# Plafond d'IDs injectés dans le prompt après union retrieval ∪ exemples.
MAX_PROMPT_CANDIDATES = int(os.getenv("RAG_MAX_PROMPT_CANDIDATES", "60"))
EMBEDDING_BATCH_SIZE = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "64"))
GENERATION_TEMPERATURE = float(os.getenv("RAG_GENERATION_TEMPERATURE", "0.1"))
GENERATION_MAX_TOKENS = int(os.getenv("RAG_GENERATION_MAX_TOKENS", "1200"))

# v3/v4 : complément analogique après la décision LLM (sans nouvel appel API).
HYBRID_FILL = os.getenv("RAG_HYBRID_FILL", "0").strip().lower() in {"1", "true", "yes"}
HYBRID_FILL_VERSION = os.getenv("RAG_HYBRID_FILL_VERSION", "v3").strip().lower()
HYBRID_MAX_ADD = int(os.getenv("RAG_HYBRID_MAX_ADD", "5"))
RETRIEVAL_SIM_HIGH = float(os.getenv("RAG_RETRIEVAL_SIM_HIGH", "0.50"))
RETRIEVAL_SIM_MED = float(os.getenv("RAG_RETRIEVAL_SIM_MED", "0.38"))
# v4 : plafond d'ajouts par capability group (évite la sur-génération locale).
HYBRID_SCOPE_MAX_ADD = {
    "action.hacking": 5,
    "action.malware": 4,
    "action.social": 2,
    "attribute.integrity": 4,
    "attribute.confidentiality": 10,
    "attribute.availability": 3,
    "value_chain.development": 1,
}
# v5 : pas de fill sur les scopes déjà sur-générés en v2/v3.
HYBRID_V5_SKIP_SCOPES = {
    "action.social",
    "value_chain.development",
}
HYBRID_V5_MAX_ADD = {
    "action.hacking": 7,
    "action.malware": 6,
    "attribute.integrity": 5,
    "attribute.confidentiality": 12,
    "attribute.availability": 4,
}
# v6 : mêmes skips que v5, mais fill analogique type v3 (sans expansion famille).
HYBRID_V6_MAX_ADD = {
    "action.hacking": 5,
    "action.malware": 5,
    "attribute.integrity": 5,
    "attribute.confidentiality": 8,
    "attribute.availability": 4,
}
# v7 : skips v6 + uniquement IDs analogiques (pas de similarité seule).
HYBRID_V7_MAX_ADD = {
    "action.hacking": 7,
    "action.malware": 4,
    "attribute.integrity": 5,
    "attribute.confidentiality": 12,
    "attribute.availability": 4,
}
# v8 : v6 + 2e passe analogique (exemples ∩ candidats) sur scopes sous-générés.
HYBRID_V8_EXTRA_ADD = {
    "action.hacking": 3,
    "attribute.confidentiality": 8,
}
# v10 : N global constant (somme v9) mais N local = taille de l'exemple
# le plus proche du même groupe, puis réallocation grow/shrink.
HYBRID_V10_SHRINK_SCOPES = {
    "action.social",
    "value_chain.development",
}
HYBRID_V10_GROW_SCOPES = {
    "attribute.confidentiality",
    "action.hacking",
}
HYBRID_V10_SCOPE_MAX_MULT = {
    "action.hacking": 1.6,
    "action.malware": 1.2,
    "action.social": 1.0,
    "attribute.integrity": 1.5,
    "attribute.confidentiality": 6.0,
    "attribute.availability": 1.5,
    "value_chain.development": 1.0,
}
HYBRID_V10_SCOPE_TACTICS = {
    "action.social": {
        "initial-access",
        "reconnaissance",
        "execution",
        "resource-development",
        "lateral-movement",
    },
    "attribute.confidentiality": {
        "collection",
        "exfiltration",
        "credential-access",
    },
    "attribute.availability": {
        "impact",
    },
    "attribute.integrity": {
        "impact",
        "persistence",
        "privilege-escalation",
        "defense-evasion",
        "credential-access",
        "execution",
        "defense-impairment",
    },
    "value_chain.development": {
        "resource-development",
    },
}
# v11 : analogue same-label (union de K exemples), skip Unknown/Other,
# famille stricte, pas de padding hors-tactique.
HYBRID_V11_TOP_M = int(os.getenv("RAG_HYBRID_V11_TOP_M", "24"))
HYBRID_V11_ANALOG_EXAMPLES = int(os.getenv("RAG_HYBRID_V11_ANALOG_EXAMPLES", "3"))
HYBRID_V11_SKIP_LABELS = {
    "unknown",
    "other",
    "na",
    "n/a",
    "none",
}
# v12 : skip Unknown même s'il y a un analogue ; union de tous les
# same-label ; parent conservé ; LLM seulement si analogue vide.
HYBRID_V12_TOP_M = int(os.getenv("RAG_HYBRID_V12_TOP_M", "48"))
HYBRID_V12_LLM_MAX = int(os.getenv("RAG_HYBRID_V12_LLM_MAX", "5"))
# v13 : union analogique aussi pour Unknown/Other ; pas de fallback LLM.
HYBRID_V13_TOP_M = int(os.getenv("RAG_HYBRID_V13_TOP_M", "48"))
# v14 : corpus same-label + remap IDs ATT&CK (versions) + découverte résidu.
HYBRID_V14_TOP_M = int(os.getenv("RAG_HYBRID_V14_TOP_M", "48"))
HYBRID_V14_REMAP_MIN_JACC = float(os.getenv("RAG_HYBRID_V14_REMAP_MIN_JACC", "0.5"))
HYBRID_V14_DISCOVERY_SIM = float(os.getenv("RAG_HYBRID_V14_DISCOVERY_SIM", "0.55"))
HYBRID_V14_DISCOVERY_MAX = int(os.getenv("RAG_HYBRID_V14_DISCOVERY_MAX", "1"))
HYBRID_V14_LLM_MAX = int(os.getenv("RAG_HYBRID_V14_LLM_MAX", "0"))


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


def validate_config(require_api: bool = True) -> None:
    """Valide la présence des variables/fichiers essentiels."""
    if GENERATOR != "together":
        raise ValueError(
            f"Backend de génération inconnu : {GENERATOR}. "
            "Cette solution n'accepte que RAG_GENERATOR=together."
        )
    if require_api and not TOGETHER_API_KEY:
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
    print("max_prompt_cand:", MAX_PROMPT_CANDIDATES)
    print("Racine dépôt   :", REPO_ROOT)
    print("Version cible  :", TARGET_REF)
    print("VERIS file     :", VERIS_FILE)
    print("ATT&CK file    :", ATTACK_FILE)
    print("Chroma path    :", CHROMA_PATH)
    print("Sortie         :", RESULTAT_RAG_DIR)
    print("Exemples dirs  :", [p.name for p in list_example_work_dirs()])
    validate_config()
