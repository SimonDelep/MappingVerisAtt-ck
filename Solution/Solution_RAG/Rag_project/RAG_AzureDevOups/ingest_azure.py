"""
Script pour ingérer les documents du dossier 'documents/' dans Azure AI Search.
Support: PDF, Markdown, CSV, JSON
"""

import os
import json
import csv
from pathlib import Path
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from openai import AzureOpenAI
from pypdf import PdfReader
from azure.search.documents.models import VectorizedQuery

# Import de la configuration centralisée
from config import (
    OPENAI_API_KEY,
    OPENAI_ENDPOINT,
    OPENAI_API_VERSION,
    OPENAI_EMBEDDING_MODEL,
    SEARCH_ENDPOINT,
    SEARCH_API_KEY,
    SEARCH_INDEX_NAME,
    DOCUMENTS_FOLDER,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    validate_config
)

# Valider la configuration avant de démarrer
validate_config()

# Initialisation des clients Azure
ai_client = AzureOpenAI(api_key=OPENAI_API_KEY, api_version=OPENAI_API_VERSION, azure_endpoint=OPENAI_ENDPOINT)
search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=SEARCH_INDEX_NAME, credential=AzureKeyCredential(SEARCH_API_KEY))


def extraire_texte_pdf(chemin_pdf: str) -> str:
    """Extrait le texte d'un fichier PDF."""
    texte = []
    try:
        lecteur = PdfReader(chemin_pdf)
        for page in lecteur.pages:
            texte.append(page.extract_text() or "")
        return "\n".join(texte)
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du PDF {chemin_pdf}: {e}")
        return ""


def extraire_texte_markdown(chemin_md: str) -> str:
    """Extrait le texte d'un fichier Markdown."""
    try:
        with open(chemin_md, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du Markdown {chemin_md}: {e}")
        return ""


def extraire_texte_csv(chemin_csv: str) -> str:
    """Extrait le texte d'un fichier CSV."""
    try:
        lignes = []
        with open(chemin_csv, 'r', encoding='utf-8') as f:
            lecteur = csv.DictReader(f)
            for ligne in lecteur:
                lignes.append(str(ligne))
        return "\n".join(lignes)
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du CSV {chemin_csv}: {e}")
        return ""


def extraire_texte_json(chemin_json: str) -> str:
    """Extrait le texte d'un fichier JSON."""
    try:
        with open(chemin_json, 'r', encoding='utf-8') as f:
            donnees = json.load(f)
        return json.dumps(donnees, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du JSON {chemin_json}: {e}")
        return ""


def extraire_texte(chemin_fichier: str) -> str:
    """Route le fichier vers le bon extracteur selon son extension."""
    extension = Path(chemin_fichier).suffix.lower()
    
    if extension == ".pdf":
        return extraire_texte_pdf(chemin_fichier)
    elif extension == ".md":
        return extraire_texte_markdown(chemin_fichier)
    elif extension == ".csv":
        return extraire_texte_csv(chemin_fichier)
    elif extension == ".json":
        return extraire_texte_json(chemin_fichier)
    else:
        print(f"⚠️  Format non supporté: {extension}")
        return ""


def vectoriser_texte(texte: str) -> list:
    """Convertit un texte en vecteur via Azure OpenAI."""
    if not texte.strip():
        return []
    
    try:
        res = ai_client.embeddings.create(input=[texte], model="mon-embedding")
        return res.data[0].embedding
    except Exception as e:
        print(f"❌ Erreur lors de la vectorisation: {e}")
        return []


def nettoyer_texte(texte: str) -> str:
    """Nettoie le texte."""
    texte = texte.replace("\x00", " ")
    texte = " ".join(texte.split())
    return texte.strip()


def chunker_texte(texte: str, taille_chunk: int = None, chevauchement: int = None) -> list:
    """Divise le texte en chunks avec chevauchement."""
    if taille_chunk is None:
        taille_chunk = CHUNK_SIZE
    if chevauchement is None:
        chevauchement = CHUNK_OVERLAP
    
    chunks = []
    start = 0
    longueur = len(texte)
    
    while start < longueur:
        end = start + taille_chunk
        chunk = texte[start:end]
        chunks.append(chunk)
        start += (taille_chunk - chevauchement)
    
    return chunks


def indexer_document(chemin_fichier: str, nom_fichier: str) -> int:
    """Charge un document, le chunke et l'indexe dans Azure."""
    print(f"\n📄 Traitement: {nom_fichier}")
    
    # Extraction du texte
    texte = extraire_texte(chemin_fichier)
    if not texte.strip():
        print(f"⚠️  Aucun texte extrait de {nom_fichier}")
        return 0
    
    # Nettoyage
    texte = nettoyer_texte(texte)
    print(f"✓ Texte extrait ({len(texte)} caractères)")
    
    # Chunking
    chunks = chunker_texte(texte)
    print(f"✓ Document divisé en {len(chunks)} chunks")
    
    # Vectorisation et indexation
    documents_a_indexer = []
    for i, chunk in enumerate(chunks):
        vecteur = vectoriser_texte(chunk)
        if not vecteur:
            continue
        
        doc_id = f"{Path(nom_fichier).stem}_chunk_{i}"
        documents_a_indexer.append({
            "id": doc_id,
            "text": f"{nom_fichier}: {chunk}",
            "vector": vecteur
        })
    
    # Upload dans Azure
    if documents_a_indexer:
        try:
            search_client.upload_documents(documents=documents_a_indexer)
            print(f"✓ {len(documents_a_indexer)} chunks indexés avec succès")
            return len(documents_a_indexer)
        except Exception as e:
            print(f"❌ Erreur lors de l'indexation: {e}")
            return 0
    
    return 0


def ingerer_tous_les_documents():
    """Ingère tous les documents du dossier 'documents/'."""
    print("=" * 60)
    print("🚀 INGESTION DES DOCUMENTS DANS AZURE AI SEARCH")
    print("=" * 60)
    
    if not os.path.exists(DOCUMENTS_PATH):
        print(f"❌ Dossier {DOCUMENTS_PATH} introuvable")
        return
    
    fichiers = [f for f in os.listdir(DOCUMENTS_PATH) if os.path.isfile(os.path.join(DOCUMENTS_PATH, f))]
    fichiers_supportes = [f for f in fichiers if Path(f).suffix.lower() in ['.pdf', '.md', '.csv', '.json']]
    
    print(f"📊 Trouvé {len(fichiers_supportes)} fichiers à traiter")
    
    total_chunks = 0
    for nom_fichier in fichiers_supportes:
        chemin_complet = os.path.join(DOCUMENTS_PATH, nom_fichier)
        chunks_indexes = indexer_document(chemin_complet, nom_fichier)
        total_chunks += chunks_indexes
    
    print("\n" + "=" * 60)
    print(f"✅ INGESTION TERMINÉE: {total_chunks} chunks indexés au total")
    print("=" * 60)


if __name__ == "__main__":
    ingerer_tous_les_documents()
