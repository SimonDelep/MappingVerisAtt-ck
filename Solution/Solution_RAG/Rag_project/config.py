"""
Configuration centralisée pour le projet RAG NordTrail Gear.
Charge les variables d'environnement depuis un fichier .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / "dev.env")
load_dotenv(".env")


def _resolve_from_repo(raw: str) -> str:
    """Chemin absolu depuis la racine du dépôt (indépendant du cwd)."""
    path = Path(raw)
    if not path.is_absolute():
        path = (_REPO_ROOT / raw).resolve()
    return str(path)


# ==================== AZURE OPENAI CONFIGURATION ====================
# Clés et endpoints pour Azure OpenAI
OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://canadacentral.api.cognitive.microsoft.com/")
OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

# Noms des modèles déployés dans Azure OpenAI
OPENAI_EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "mon-embedding")
OPENAI_CHAT_MODEL = os.getenv("AZURE_OPENAI_CHAT_MODEL", "mon-llm-chat")

# ==================== AZURE AI SEARCH CONFIGURATION ====================
# Endpoints et clés pour Azure AI Search
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "https://mon-moteur-search.search.windows.net")
SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")
SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "index-rag-canadien")

# ==================== CHROMA CONFIGURATION (Local Vector Store) ====================
_chroma_raw = os.getenv("CHROMA_PATH", "./db/chroma_store")
CHROMA_PATH = _resolve_from_repo(_chroma_raw)
os.environ["CHROMA_PATH"] = CHROMA_PATH
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "nordtrail_documents")

# ==================== DOCUMENT INGESTION CONFIGURATION ====================
_docs_raw = os.getenv("DOCUMENTS_FOLDER", "Rag_project/documents")
DOCUMENTS_FOLDER = _resolve_from_repo(_docs_raw)
DOCUMENTS_PATH = DOCUMENTS_FOLDER
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
TOP_K = int(os.getenv("TOP_K", "5"))

# ==================== LOGGING & DEBUG ====================
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# ==================== VALIDATION ====================
def validate_config():
    """Valide que les variables essentielles sont configurées."""
    required_vars = {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "SEARCH_API_KEY": SEARCH_API_KEY,
    }
    
    missing = [name for name, value in required_vars.items() if not value]
    
    if missing:
        raise ValueError(
            f"❌ Variables d'environnement manquantes: {', '.join(missing)}\n"
            f"   Veuillez créer un fichier .env avec ces variables."
        )
    
    print("✅ Configuration validée avec succès")


if __name__ == "__main__":
    validate_config()
    print("\n📋 Configuration chargée:")
    print(f"  • OpenAI Endpoint: {OPENAI_ENDPOINT}")
    print(f"  • Search Endpoint: {SEARCH_ENDPOINT}")
    print(f"  • Index: {SEARCH_INDEX_NAME}")
    print(f"  • Documents folder: {DOCUMENTS_FOLDER}")
    print(f"  • Chunk size: {CHUNK_SIZE} chars, overlap: {CHUNK_OVERLAP}")

