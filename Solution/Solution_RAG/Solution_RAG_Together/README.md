# RAG VERIS → ATT&CK avec LLM Together.ai

Variante cloud du RAG local (`Solution/Solution_RAG/veris_mapping`).

| Composant | Rôle |
|-----------|------|
| Embeddings | locaux (`sentence-transformers`) |
| Index | ChromaDB |
| Décision | LLM Together.ai (API compatible OpenAI) |

## Prérequis

1. Installer les dépendances :

```bash
cd Solution/Solution_RAG/Solution_RAG_Together/veris_mapping
pip install -r requirements.txt
```

2. Renseigner la clé API dans `Solution_RAG_Together/dev.env` :

```env
TOGETHER_API_KEY=votre_cle
TOGETHER_BASE_URL=https://api.together.ai/v1
TOGETHER_CHAT_MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo
RAG_GENERATOR=together
```

3. Avoir `data_for_work/attack-19.1_veris-1.4.1/` préparé.

## Usage

```bash
cd Solution/Solution_RAG/Solution_RAG_Together/veris_mapping

# 1. Indexer ATT&CK (+ exemples experts des autres versions)
python ingest.py

# 2. Générer le mapping (Together.ai)
python generate_mapping.py --mode both
# test rapide :
python generate_mapping.py --mode attack_only --limit 5

# 3. Smoke-test hors-ligne (sans API)
python selftest_offline.py
```

## Sorties

Les fichiers JSON sont écrits dans :

```
Resultat/Resultat_RAG_Together/
  veris-1.4.1_attack-19.1-enterprise_RAG_Together_attack_only/
  veris-1.4.1_attack-19.1-enterprise_RAG_Together_with_examples/
```

Évaluation :

```bash
cd Resultat
python compare_veris_mappings_v2.py --solutions Resultat_RAG_Together
```
