# RAG multi-LLM (précision) — VERIS → MITRE ATT&CK

Variante isolée de `Solution_RAG` / `Solution_RAG_Together` : **même retrieval
local** (MiniLM + ChromaDB), décision par **N LLM cloud** (phase 1) avec un
prompt orienté **précision**.

## Phases

| Phase | État | Détail |
|---|---|---|
| 0 | tools/ | `check_llm_api.py`, `list_llm_models.py` |
| 1 | MODELS.md | 3 modèles serverless figés |
| 2 | ce dossier | pipeline + runner multi-modèles |
| 3 | eval | `compare_veris_mappings_v2.py` |
| 4 | Latex | rédaction résultats |

## Modèles (phase 1)

Voir [MODELS.md](MODELS.md). Défaut :

```
meta-llama/Llama-3.3-70B-Instruct-Turbo
Qwen/Qwen2.5-7B-Instruct-Turbo
deepseek-ai/DeepSeek-V4-Flash-0731
```

Override dans `.dev.env` : `RAG_MULTI_LLM_MODELS=id1,id2,id3`.

## Prérequis

```bash
# clé API (racine SIEM)
# TOGETHER_API_KEY=...

pip install -r veris_mapping/requirements.txt
```

Smoke clé :

```bash
# racine SIEM
python tools/check_llm_api.py
```

## Utilisation

```bash
cd Solution/Solution_RAG/Solution_RAG_MultiLLM/veris_mapping

# 1. config
python config.py

# 2. ingestion vectorielle (ou pointer RAG_CHROMA_PATH vers un store existant)
python ingest.py

# 3. un modèle
python generate_mapping.py --mode with_examples \
  --model meta-llama/Llama-3.3-70B-Instruct-Turbo
# smoke :
python generate_mapping.py --mode with_examples --model ... --limit 3

# 4. les 3 modèles
python run_all_models.py --mode with_examples
# smoke multi :
python run_all_models.py --mode with_examples --limit 3
```

## Sorties

`Resultat/Resultat_RAG_MultiLLM/veris-1.4.1_attack-19.1-enterprise_RAG_MultiLLM_<slug>_<mode>/`

7 JSON par dossier (capability groups).

## Évaluation

```bash
# racine SIEM
python Resultat/compare_veris_mappings_v2.py --solutions Resultat_RAG_MultiLLM
```
