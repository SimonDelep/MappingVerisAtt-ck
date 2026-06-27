# Assistant RAG pour service client — NordTrail Gear

Ce projet implémente la base documentaire du système d'assistant IA : un **RAG** (*Retrieval-Augmented Generation*) capable de répondre à des courriels clients en s'appuyant sur les politiques et documents internes de NordTrail Gear.

Les agents [`single_agent/`](../single_agent/) et [`multi_agent/`](../multi_agent/) consomment cette base via **ChromaDB** (`retrieve.py`) par défaut. Une variante **Azure AI Search** reste disponible pour un déploiement cloud.

---

## Contexte du projet

Boutique en ligne spécialisée outdoor (randonnée, trail, bivouac). Le service client reçoit des demandes sur les retours, annulations, garanties, livraisons et recommandations produits.

Le RAG permet à l'assistant de s'appuyer sur les documents internes plutôt que sur les seules connaissances générales du modèle.

---

## Ce que fait le système RAG

**Backend par défaut (ChromaDB — agents)**

```text
Question ou courriel client
        ↓
Recherche vectorielle dans ChromaDB (embeddings Azure OpenAI)
        ↓
Récupération des passages les plus pertinents
        ↓
Injection de ces passages dans le prompt (agent ou rag.py)
        ↓
Génération d'une réponse contextualisée
        ↓
Retour de la réponse avec les sources utilisées
```

**Variante Azure AI Search (option cloud)**

```text
Question → recherche hybride (texte + vecteur) dans Azure AI Search → passages → LLM
```

---

## Documents utilisés

```text
documents/
├── politique_retours.pdf
├── politique_garantie.pdf
├── faq_livraison.md
├── conditions_annulation.md
├── guide_tailles.md
├── procedure_sav_interne.md
├── catalogue_produits.csv
├── clients_exemples.json
├── commandes_exemples.json
└── emails_clients_test.csv   # évaluation uniquement — non indexé
```

---

## Structure du projet

```text
Rag_project/
├── config.py              # Variables d'environnement (lit dev.env à la racine)
├── utils.py               # Chargement, nettoyage, chunking
├── embeddings.py          # Embeddings Azure OpenAI
├── ingest.py              # Ingestion → ChromaDB (backend par défaut des agents)
├── retrieve.py            # Recherche ChromaDB (backend par défaut des agents)
├── vectorstore.py         # Interface ChromaDB
├── ingest_azure.py        # Ingestion → Azure AI Search (option cloud)
├── retrieve_azure.py      # Recherche hybride Azure AI Search (option cloud)
├── rag.py                 # Pipeline RAG complet (retrieve + LLM)
├── rag_test.py            # Tests Azure Search + LLM
├── documents/
└── README.md
```

| Fichier | Rôle |
|---|---|
| `ingest.py` / `retrieve.py` | Ingestion et recherche ChromaDB (utilisé par `single_agent` et `multi_agent`) |
| `ingest_azure.py` / `retrieve_azure.py` | Variante Azure AI Search (option cloud) |
| `rag.py` | Pipeline RAG autonome avec génération LLM |
| `embeddings.py` | Génération des embeddings via Azure OpenAI |

---

## Installation

```bash
pip install openai chromadb pypdf python-dotenv azure-search-documents
```

Ou, depuis la racine du dépôt :

```bash
pip install -r single_agent/requirements.txt
```

---

## Configuration

Les variables sont centralisées dans `dev.env` à la **racine du dépôt** (`Agent_IA/dev.env`). `config.py` charge ce fichier automatiquement.

```bash
cp ../dev.env.example ../dev.env
```

Variables essentielles :

```env
# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_VERSION=2025-04-01-preview
AZURE_OPENAI_EMBEDDING_MODEL=nordtrail-embedding
AZURE_OPENAI_DEPLOYMENT=nordtrail-llm          # pour rag.py

# ChromaDB (backend par défaut des agents)
CHROMA_PATH=./db/chroma_store
CHROMA_COLLECTION=nordtrail_documents

# Ingestion
DOCUMENTS_FOLDER=Rag_project/documents
CHUNK_SIZE=1500
CHUNK_OVERLAP=150
TOP_K=5
```

Variables optionnelles pour Azure AI Search :

```env
AZURE_SEARCH_API_KEY=...
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_INDEX_NAME=index-rag-canadien
```

Voir aussi [`.env.example`](.env.example) pour la liste complète.

---

## Ingestion — ChromaDB (recommandé pour les agents)

```bash
python Rag_project/ingest.py
```

Ce script :

1. lit les documents du dossier `documents/` ;
2. nettoie et découpe les textes (chunks de 1500 caractères, overlap 150) ;
3. génère un embedding Azure OpenAI par chunk ;
4. stocke les vecteurs dans ChromaDB (`CHROMA_PATH`, défaut `./db/chroma_store` à la racine du dépôt).

> Fermez Streamlit ou tout autre processus utilisant Chroma avant de réingérer.

---

## Ingestion — Azure AI Search (option cloud)

Pour un index cloud sans ChromaDB local :

```bash
cd Rag_project
python ingest_azure.py
```

Exemple de sortie :

```text
INGESTION DES DOCUMENTS DANS AZURE AI SEARCH
Trouvé 9 fichiers à traiter
INGESTION TERMINÉE: 57 chunks indexés au total
```

Adaptez ensuite `single_agent/rag_tool.py` pour utiliser `retrieve_azure` si vous basculez les agents vers Azure Search.

---

## Recherche documentaire

**ChromaDB** (backend `single_agent` / `multi_agent`) :

```python
from retrieve import retrieve
results = retrieve("politique de retour chaussures", top_k=5)
```

Ou en ligne de commande :

```bash
python retrieve.py
```

**Azure AI Search** (option cloud) :

```python
from retrieve_azure import retrieve
results = retrieve("politique de retour chaussures", top_k=5)
```

Par défaut, `top_k = 5` passages récupérés.

---

## Pipeline RAG complet (avec LLM)

Le fichier `rag.py` enchaîne retrieval + génération de réponse :

```bash
python rag.py
```

Pour tester Azure Search avec plusieurs questions :

```bash
python rag_test.py
```

---

## Intégration avec les agents

Les agents appellent `search_company_documents` qui délègue à `retrieve.py` (ChromaDB). Flux :

```text
single_agent.main / multi_agent.main
    → agent(s) (Azure OpenAI)
    → rag_tool.py → retrieve.py → ChromaDB
    → mcp_client.py → API FastAPI :8001
```

Dans [`multi_agent/`](../multi_agent/), l'appel RAG est tracé dans LangSmith sous le span `nordtrail.tool.search_company_documents` (`run_type: tool`), avec l'agent propriétaire (`tool_agent: document`) et, si `AUDIT_VERBOSE_TRACING=true`, la requête tronquée dans les inputs redacted.

Voir [`single_agent/README.md`](../single_agent/README.md) et [`multi_agent/README.md`](../multi_agent/README.md) pour le démarrage complet, le guardrail d'entrée et la configuration LangSmith.

---

## Stratégie de chunking

Paramètres par défaut (`dev.env`) :

```text
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 150
```

Ces valeurs conservent des passages métier complets tout en limitant le bruit dans le contexte injecté au LLM.

---

## Évaluation

Le fichier `emails_clients_test.csv` sert aux tests d'évaluation et **n'est pas indexé** dans la base RAG.

Métriques possibles : faithfulness, answer relevancy, context recall, context precision.

---

## Dépannage

| Problème | Action |
|---|---|
| RAG vide dans les agents | Relancer `python Rag_project/ingest.py`, vérifier `CHROMA_PATH` et `AZURE_OPENAI_EMBEDDING_MODEL` |
| Erreur embedding | Vérifier `AZURE_OPENAI_EMBEDDING_MODEL` (nom du déploiement Azure) |
| Erreur Chroma `default_tenant` | API NordTrail sur port **8001**, `chromadb>=1.0`, réingérer après fermeture des clients Chroma |
| Index Azure introuvable | `ingest_azure.py` crée l'index automatiquement au premier lancement |
| Encodage console Windows | `$env:PYTHONIOENCODING="utf-8"` avant les scripts Python |

Guide détaillé : [`SETUP.md`](SETUP.md).

---

## Résumé

Ce projet fournit :

- l'ingestion documentaire vers **ChromaDB** (agents locaux) ou **Azure AI Search** (cloud) ;
- la recherche sémantique pour alimenter `single_agent` et `multi_agent` ;
- un pipeline RAG autonome (`rag.py`) pour tests et démonstrations ;
- des réponses traçables avec citation des sources documentaires.
