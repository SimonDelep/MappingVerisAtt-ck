# Mapping VERIS → ATT&CK — RAG + Together.ai

Voir le [README](../README.md) du dossier parent pour l'installation et l'usage.

Variables principales (dans `dev.env`) :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `TOGETHER_API_KEY` | — | **Obligatoire** |
| `TOGETHER_BASE_URL` | `https://api.together.ai/v1` | Endpoint API |
| `TOGETHER_CHAT_MODEL` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | Modèle chat |
| `RAG_GENERATOR` | `together` | Backend (fixe pour cette solution) |
| `RAG_TOP_K_TECHNIQUES` | `20` | Candidats ATT&CK par capacité |
| `RAG_TOP_M_EXAMPLES` | `5` | Exemples experts (mode `with_examples`) |
