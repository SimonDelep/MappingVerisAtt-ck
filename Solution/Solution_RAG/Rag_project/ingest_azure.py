"""
Script pour ingérer les documents du dossier 'documents/' dans Azure AI Search.
Support: PDF, Markdown, CSV, JSON
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from openai import AzureOpenAI
from pypdf import PdfReader

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DOCUMENTS_FOLDER,
    OPENAI_API_KEY,
    OPENAI_API_VERSION,
    OPENAI_EMBEDDING_MODEL,
    OPENAI_ENDPOINT,
    SEARCH_API_KEY,
    SEARCH_ENDPOINT,
    SEARCH_INDEX_NAME,
    validate_config,
)
from embeddings import get_embedding

REPO_ROOT = Path(__file__).resolve().parent.parent
RAG_ROOT = Path(__file__).resolve().parent

EXCLUDED_FILES = {"emails_clients_test.csv"}


def _resolve_documents_path() -> Path:
    documents_path = Path(DOCUMENTS_FOLDER)
    candidates = [
        documents_path,
        REPO_ROOT / DOCUMENTS_FOLDER,
        RAG_ROOT / "documents",
        RAG_ROOT / DOCUMENTS_FOLDER,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return RAG_ROOT / "documents"


DOCUMENTS_PATH = _resolve_documents_path()

validate_config()

ai_client = AzureOpenAI(
    api_key=OPENAI_API_KEY,
    api_version=OPENAI_API_VERSION,
    azure_endpoint=OPENAI_ENDPOINT,
)
index_client = SearchIndexClient(
    endpoint=SEARCH_ENDPOINT,
    credential=AzureKeyCredential(SEARCH_API_KEY),
)
search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=SEARCH_INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_API_KEY),
)


def ensure_search_index(vector_dimensions: int) -> None:
    """Crée l'index vectoriel dans Azure AI Search s'il n'existe pas."""
    try:
        index_client.get_index(SEARCH_INDEX_NAME)
        print(f"Index existant : {SEARCH_INDEX_NAME}")
        return
    except Exception:
        print(f"Création de l'index : {SEARCH_INDEX_NAME}")

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="text", type=SearchFieldDataType.String, searchable=True),
        SearchField(
            name="vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=vector_dimensions,
            vector_search_profile_name="nordtrail-hnsw",
        ),
    ]
    vector_search = VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="nordtrail-hnsw",
                algorithm_configuration_name="nordtrail-hnsw-algo",
            )
        ],
        algorithms=[HnswAlgorithmConfiguration(name="nordtrail-hnsw-algo")],
    )
    index = SearchIndex(
        name=SEARCH_INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
    )
    index_client.create_index(index)
    print("Index créé avec succès.")


def extraire_texte_pdf(chemin_pdf: str) -> str:
    texte = []
    try:
        lecteur = PdfReader(chemin_pdf)
        for page in lecteur.pages:
            texte.append(page.extract_text() or "")
        return "\n".join(texte)
    except Exception as e:
        print(f"Erreur lecture PDF {chemin_pdf}: {e}")
        return ""


def extraire_texte_markdown(chemin_md: str) -> str:
    try:
        with open(chemin_md, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Erreur lecture Markdown {chemin_md}: {e}")
        return ""


def extraire_texte_csv(chemin_csv: str) -> str:
    try:
        lignes = []
        with open(chemin_csv, encoding="utf-8") as f:
            lecteur = csv.DictReader(f)
            for ligne in lecteur:
                lignes.append(str(ligne))
        return "\n".join(lignes)
    except Exception as e:
        print(f"Erreur lecture CSV {chemin_csv}: {e}")
        return ""


def extraire_texte_json(chemin_json: str) -> str:
    try:
        with open(chemin_json, encoding="utf-8") as f:
            donnees = json.load(f)
        return json.dumps(donnees, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Erreur lecture JSON {chemin_json}: {e}")
        return ""


def extraire_texte(chemin_fichier: str) -> str:
    extension = Path(chemin_fichier).suffix.lower()

    if extension == ".pdf":
        return extraire_texte_pdf(chemin_fichier)
    if extension == ".md":
        return extraire_texte_markdown(chemin_fichier)
    if extension == ".csv":
        return extraire_texte_csv(chemin_fichier)
    if extension == ".json":
        return extraire_texte_json(chemin_fichier)

    print(f"Format non supporté: {extension}")
    return ""


def vectoriser_texte(texte: str) -> list[float]:
    if not texte.strip():
        return []
    try:
        return get_embedding(texte)
    except Exception as e:
        print(f"Erreur vectorisation: {e}")
        return []


def nettoyer_texte(texte: str) -> str:
    texte = texte.replace("\x00", " ")
    return " ".join(texte.split()).strip()


def chunker_texte(
    texte: str,
    taille_chunk: int | None = None,
    chevauchement: int | None = None,
) -> list[str]:
    taille_chunk = taille_chunk or CHUNK_SIZE
    chevauchement = chevauchement or CHUNK_OVERLAP

    chunks = []
    start = 0
    longueur = len(texte)

    while start < longueur:
        end = start + taille_chunk
        chunks.append(texte[start:end])
        start += taille_chunk - chevauchement

    return chunks


def indexer_document(chemin_fichier: str, nom_fichier: str) -> int:
    print(f"\nTraitement: {nom_fichier}")

    texte = extraire_texte(chemin_fichier)
    if not texte.strip():
        print(f"Aucun texte extrait de {nom_fichier}")
        return 0

    texte = nettoyer_texte(texte)
    print(f"Texte extrait ({len(texte)} caractères)")

    chunks = chunker_texte(texte)
    print(f"Document divisé en {len(chunks)} chunks")

    documents_a_indexer = []
    for i, chunk in enumerate(chunks):
        vecteur = vectoriser_texte(chunk)
        if not vecteur:
            continue

        doc_id = f"{Path(nom_fichier).stem}_chunk_{i}"
        documents_a_indexer.append(
            {
                "id": doc_id,
                "text": f"{nom_fichier}: {chunk}",
                "vector": vecteur,
            }
        )

    if not documents_a_indexer:
        return 0

    try:
        search_client.upload_documents(documents=documents_a_indexer)
        print(f"{len(documents_a_indexer)} chunks indexés")
        return len(documents_a_indexer)
    except Exception as e:
        print(f"Erreur indexation: {e}")
        return 0


def ingerer_tous_les_documents() -> None:
    print("=" * 60)
    print("INGESTION DES DOCUMENTS DANS AZURE AI SEARCH")
    print("=" * 60)
    print(f"Dossier documents : {DOCUMENTS_PATH}")

    if not DOCUMENTS_PATH.exists():
        print(f"Dossier introuvable : {DOCUMENTS_PATH}")
        return

    sample_embedding = get_embedding("dimension test")
    ensure_search_index(len(sample_embedding))

    fichiers = [
        f
        for f in os.listdir(DOCUMENTS_PATH)
        if os.path.isfile(DOCUMENTS_PATH / f)
        and f not in EXCLUDED_FILES
        and Path(f).suffix.lower() in {".pdf", ".md", ".csv", ".json"}
    ]

    print(f"Trouvé {len(fichiers)} fichiers à traiter")

    total_chunks = 0
    for nom_fichier in fichiers:
        chemin_complet = str(DOCUMENTS_PATH / nom_fichier)
        total_chunks += indexer_document(chemin_complet, nom_fichier)

    print("\n" + "=" * 60)
    print(f"INGESTION TERMINÉE: {total_chunks} chunks indexés au total")
    print("=" * 60)


if __name__ == "__main__":
    ingerer_tous_les_documents()
