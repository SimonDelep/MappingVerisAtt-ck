# Phase 1 — Choix des 3 modèles multi-LLM

Date : 2026-08-05  
Provider : **Together.ai** (`https://api.together.ai/v1`)  
Outils : `tools/check_llm_api.py`, `tools/list_llm_models.py`

## Critères appliqués

1. **Accessibilité serverless** — l’id répond à `chat.completions` sans endpoint dédié.
2. **Chat / instruct** — type `chat`, capable d’instruction-following.
3. **Diversité familiale** — Meta Llama / Alibaba Qwen / DeepSeek.
4. **Coût / latence** — privilégier Turbo / Flash pour un run complet sur toutes les capacités VERIS.
5. **Smoke JSON-friendly** — réponse non vide au ping chat.

> **Note importante (Together)** : beaucoup d’ids apparaissent dans `GET /models`
> mais renvoient `model_not_available` (non-serverless). Seuls les 3 retenus
> ci-dessous ont été **smoke-testés avec succès** sur ce compte.

## Modèles retenus

| # | Id Together | Famille | Smoke | Rôle expérimental |
|---|---|---|---|---|
| 1 | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | Llama | OK → `OK` | Référence forte (déjà défaut RAG_Together) |
| 2 | `Qwen/Qwen2.5-7B-Instruct-Turbo` | Qwen | OK → `OK` | Variante plus légère, famille Qwen serverless |
| 3 | `moonshotai/Kimi-K3` | Moonshot | OK → `OK` (max_tokens≥128) | Remplace DeepSeek-V4-Flash pour le slot multi-LLM |

Config figée dans `.dev.env` :

```env
RAG_MULTI_LLM_MODELS=meta-llama/Llama-3.3-70B-Instruct-Turbo,Qwen/Qwen2.5-7B-Instruct-Turbo,moonshotai/Kimi-K3
```

## Candidats écartés / historiques (utiles au rapport)

| Id | Raison |
|---|---|
| `deepseek-ai/DeepSeek-V4-Flash-0731` | Ancien slot multi-LLM ; remplacé par Kimi-K3 (meilleure dispo crédit sur le compte) |
| `Qwen/Qwen2.5-72B-Instruct-Turbo` | Listé mais **non-serverless** (endpoint dédié requis) |
| `Qwen/Qwen3-235B-A22B-Instruct-2507-FP8` | Non-serverless (trop cher / setup dédié) |
| `deepseek-ai/DeepSeek-R1-0528` | Non-serverless sur ce compte |
| `deepseek-ai/DeepSeek-V3.1` | Non-serverless |
| `deepseek-ai/DeepSeek-R1-Distill-Llama-70B` | Non-serverless |
| `Qwen/Qwen3.5-9B` | Appel accepté mais **contenu vide** (raisonnement seul) — fragile pour JSON mapping |
| `deepseek-ai/DeepSeek-V4-Pro` | Serverless OK, mais plus lourd/coûteux que Flash pour le premier run multi-modèle |

## Justifications (1–2 phrases)

1. **Llama 3.3 70B Turbo** — meilleur équilibre qualité / disponibilité déjà validé dans le projet ; baseline LLM forte pour l’expérience précision.
2. **Qwen2.5 7B Turbo** — seule variante Qwen **serverless + réponse stable** trouvable rapidement ; permet de comparer une famille distincte (même si plus petit) sans endpoint dédié.
3. **Kimi-K3** — modèle Moonshot serverless validé sur le compte ; remplace DeepSeek-V4-Flash comme 3ᵉ famille expérimentale pour le multi-LLM.

## Reproductibilité

```bash
python tools/check_llm_api.py
python tools/list_llm_models.py --filter llama --chat-only
python tools/list_llm_models.py --filter qwen --chat-only
python tools/list_llm_models.py --filter deepseek --chat-only
python tools/check_llm_api.py --model meta-llama/Llama-3.3-70B-Instruct-Turbo
python tools/check_llm_api.py --model Qwen/Qwen2.5-7B-Instruct-Turbo
python tools/check_llm_api.py --model moonshotai/Kimi-K3 --max-tokens 128
```

## Suite (phase 2)

Implémenter `Solution_RAG_MultiLLM` qui boucle sur `RAG_MULTI_LLM_MODELS`.
