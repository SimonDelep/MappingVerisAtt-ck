# Configuration du projet RAG NordTrail Gear

## 📋 Overview

Ce projet implémente un **Retrieval Augmented Generation (RAG)** avec Azure AI Search et Azure OpenAI pour répondre aux questions clients sur les produits et politiques NordTrail Gear.

## 🚀 Quick Start

### 1. Installation des dépendances

```bash
pip install -r requirements.txt
```

### 2. Configuration (Crucial!)

Copie le fichier `.env.example` en `.env` et remplis tes clés API:

```bash
cp .env.example .env
```

Édite `.env` avec tes vraies clés:
```
AZURE_OPENAI_API_KEY=your-key-here
AZURE_SEARCH_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=your-endpoint-here
AZURE_SEARCH_ENDPOINT=your-endpoint-here
```

### 3. Ingestion des documents

Charge tous les documents du dossier `documents/` dans Azure AI Search:

```bash
python ingest_azure.py
```

Tu devrais voir:
```
🚀 INGESTION DES DOCUMENTS DANS AZURE AI SEARCH
📊 Trouvé 10 fichiers à traiter
✅ INGESTION TERMINÉE: XX chunks indexés au total
```

### 4. Test du RAG

Lance des questions sur les documents ingérés:

```bash
python rag_test.py
```

Exemple de sortie:
```
📌 Question 1: Quels sont les délais de livraison standard en France métropolitaine ?
✅ Réponse: ...
```

## 📁 Structure du projet

```
Rag_project/
├── config.py                 # Configuration centralisée
├── .env.example              # Template des variables d'environnement
├── .env                      # Variables d'environnement (À NE PAS COMMIT)
├── ingest_azure.py           # Script d'ingestion des documents
├── rag_test.py               # Script de test du RAG
├── rag.py                    # Logique principale du RAG
├── retrieve.py               # Recherche dans Azure AI Search
├── embeddings.py             # Gestion des embeddings
├── vectorstore.py            # Interface avec Azure AI Search
├── utils.py                  # Utilitaires
├── documents/                # Dossier contenant les documents source
│   ├── catalogue_produits.csv
│   ├── faq_livraison.md
│   ├── guide_tailles.md
│   └── ... (autres documents)
├── db/                       # Base de données locale (Chroma)
└── README.md                 # Ce fichier
```

## 🔐 Variables d'environnement

### Azure OpenAI
- `AZURE_OPENAI_API_KEY` - Clé API Azure OpenAI
- `AZURE_OPENAI_ENDPOINT` - Endpoint Azure OpenAI (ex: https://canadacentral.api.cognitive.microsoft.com/)
- `AZURE_OPENAI_API_VERSION` - Version API (défaut: 2024-02-01)
- `AZURE_OPENAI_EMBEDDING_MODEL` - Nom du modèle embedding déployé
- `AZURE_OPENAI_CHAT_MODEL` - Nom du modèle chat déployé

### Azure AI Search
- `AZURE_SEARCH_API_KEY` - Clé API Azure AI Search
- `AZURE_SEARCH_ENDPOINT` - Endpoint Azure AI Search
- `AZURE_SEARCH_INDEX_NAME` - Nom de l'index (défaut: index-rag-canadien)

### Document Processing
- `DOCUMENTS_FOLDER` - Chemin du dossier documents (défaut: ./documents)
- `CHUNK_SIZE` - Taille des chunks de texte en caractères (défaut: 1500)
- `CHUNK_OVERLAP` - Chevauchement entre chunks (défaut: 150)

## 🔑 Obtenir tes clés API

### Azure OpenAI

```bash
# Voir l'endpoint
az cognitiveservices account show \
  --name mon-service-ia-simon \
  --resource-group MonGroupeRAG1 \
  --query "properties.endpoint" \
  --output tsv

# Voir la clé API
az cognitiveservices account keys list \
  --name mon-service-ia-simon \
  --resource-group MonGroupeRAG1 \
  --query "key1" \
  --output tsv
```

### Azure AI Search

```bash
# Voir l'endpoint
az search service show \
  --name mon-moteur-search \
  --resource-group MonGroupeRAG1 \
  --query "endpoint" \
  --output tsv

# Voir la clé API
az search admin-key show \
  --service-name mon-moteur-search \
  --resource-group MonGroupeRAG1 \
  --query "primaryKey" \
  --output tsv
```

## 📚 Formats de documents supportés

- **PDF** (.pdf) - Extraction de texte automatique
- **Markdown** (.md) - Fichiers structurés
- **CSV** (.csv) - Données tabulaires
- **JSON** (.json) - Données structurées

## ⚙️ Personnalisation

### Modifier la taille des chunks

```python
# Dans .env
CHUNK_SIZE=2000
CHUNK_OVERLAP=200
```

Les chunks plus grands = contexte plus riche mais recherche moins précise
Les chunks plus petits = recherche plus précise mais moins de contexte

### Ajouter de nouveaux documents

1. Place tes fichiers dans le dossier `documents/`
2. Lance `python ingest_azure.py`
3. Les nouveaux documents seront automatiquement indexés

### Modifier la recherche (top-k)

Dans `rag_test.py`, modifie le paramètre `top` dans la fonction `interroger_rag()`:

```python
resultats = search_client.search(
    search_text=question,
    vector_queries=[requete_vectorielle],
    top=3  # Retourner les 3 meilleurs résultats au lieu de 1
)
```

## 🐛 Dépannage

### Erreur: "The request is invalid. Details: The property 'source' does not exist..."

Le champ `source` n'existe pas dans l'index. L'ingestion l'intègre maintenant au texte lui-même. Réingère les documents.

### Erreur: "Missing required environment variables..."

Assure-toi que ton fichier `.env` existe et contient les clés API:

```bash
cat .env  # Vérifier le contenu
```

### Résultats de recherche médiocres

Augmente le `CHUNK_SIZE` pour avoir plus de contexte, ou modifie le nombre de résultats avec `top=3` ou plus.

## 📖 Documentation utile

- [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/)
- [Azure OpenAI](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/)
- [Python SDK Azure Search](https://pypi.org/project/azure-search-documents/)
- [Python SDK Azure OpenAI](https://pypi.org/project/openai/)

## 📝 License

Projet interne NordTrail Gear

## 🤝 Questions?

Pour toute question, contacte l'équipe IA ou consulte la documentation Azure.
