"""Décision multi-LLM via API OpenAI-compatible (Together par défaut).

Le LLM choisit les techniques ATT&CK parmi les candidats du retrieval.
Le paramètre `model` est fourni par le runner (1 des N modèles phase 1).

Format de sortie (identique aux autres solutions RAG) :

    {
      "no_mapping_found": bool,
      "ambiguous": bool,
      "notes": str,
      "mappings": [
        {"attack_id": "Txxxx[.yyy]", "mapping_type": "related_to",
         "confidence": "high|medium|low", "justification": "..."}
      ]
    }
"""

from __future__ import annotations

import json
import time

import config
from prompt import SYSTEM_PROMPT, build_user_prompt

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        if not config.TOGETHER_API_KEY:
            raise ValueError("TOGETHER_API_KEY (ou OPENAI_API_KEY) manquante.")
        print(f"  [llm] base_url={config.TOGETHER_BASE_URL}")
        _client = OpenAI(
            api_key=config.TOGETHER_API_KEY,
            base_url=config.TOGETHER_BASE_URL,
        )
    return _client


def _parse_json(content: str) -> dict:
    content = (content or "").strip()
    # Certains modèles (raisonnement) mettent le texte hors JSON.
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
        content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start : end + 1])
        raise


def _filter_to_candidates(result: dict, candidates: list[dict]) -> dict:
    """Garde-fou : n'accepte que des attack_id présents dans le top-k retrieval."""
    allowed = {
        (c.get("attack_id") or "").strip().upper()
        for c in candidates
        if c.get("attack_id")
    }
    mappings: list[dict] = []
    seen: set[str] = set()
    for item in result.get("mappings", []) or []:
        aid = (item.get("attack_id") or "").strip().upper()
        if not aid or aid in seen or aid not in allowed:
            continue
        mappings.append(
            {
                "attack_id": aid,
                "mapping_type": item.get("mapping_type", "related_to") or "related_to",
                "confidence": item.get("confidence", "medium") or "medium",
                "justification": item.get("justification", "") or "",
            }
        )
        seen.add(aid)

    return {
        "no_mapping_found": not mappings,
        "ambiguous": bool(result.get("ambiguous", False)),
        "notes": result.get("notes", "")
        or ("" if mappings else "Aucune correspondance trouvée."),
        "mappings": mappings,
    }


def _message_text(message) -> str:
    """Extrait le texte utile (content prioritaire, puis reasoning si JSON dedans)."""
    content = getattr(message, "content", None) or ""
    if isinstance(content, str) and content.strip():
        return content

    # DeepSeek V4 / modèles "reasoning" : contenu parfois vide, JSON dans reasoning.
    extras: list[str] = []
    for attr in ("reasoning", "reasoning_content"):
        val = getattr(message, attr, None)
        if isinstance(val, str) and val.strip():
            extras.append(val)
    dump = None
    if hasattr(message, "model_dump"):
        try:
            dump = message.model_dump()
        except Exception:
            dump = None
    if isinstance(dump, dict):
        for key in ("reasoning", "reasoning_content", "content"):
            val = dump.get(key)
            if isinstance(val, str) and val.strip():
                extras.append(val)

    for text in extras:
        if "{" in text and "}" in text:
            return text
    return content or (extras[0] if extras else "")


def _llm_decision(
    group: str,
    label: str,
    description: str,
    candidates: list[dict],
    examples: list[dict],
    model: str,
) -> dict:
    client = _get_client()
    user_prompt = build_user_prompt(group, label, description, candidates, examples)
    # Renfort pour modèles reasoning / réponses vides.
    user_prompt_strict = (
        user_prompt
        + "\nIMPORTANT : ta réponse finale doit être UNIQUEMENT l'objet JSON "
        "(commence par { et termine par }), sans markdown ni texte libre."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt_strict},
    ]

    # Les modèles reasoning consomment des tokens avant le JSON final.
    max_tokens = max(config.GENERATION_MAX_TOKENS, 2048)
    if "deepseek" in model.lower() or "reason" in model.lower():
        max_tokens = max(max_tokens, 4096)

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=config.GENERATION_TEMPERATURE,
                max_tokens=max_tokens,
                messages=messages,
            )
            text = _message_text(response.choices[0].message)
            if not (text or "").strip():
                raise ValueError("Réponse LLM vide (content/reasoning).")
            parsed = _parse_json(text)
            return _filter_to_candidates(parsed, candidates)
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as err:
            last_error = err
            if attempt == 0:
                time.sleep(0.8)
                # Second essai : message ultra court de rappel.
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": user_prompt
                        + "\nRéponds maintenant par un unique objet JSON valide.",
                    },
                ]
                continue
            raise
        except Exception as err:
            last_error = err
            if attempt == 0:
                time.sleep(1.2)
                continue
            raise

    raise RuntimeError(f"Échec génération LLM : {last_error}")


def generate_decision(
    group: str,
    label: str,
    description: str,
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    use_examples: bool,
    model: str | None = None,
) -> dict:
    del attack_index, use_examples
    backend = config.GENERATOR
    if backend != "together":
        raise ValueError(
            f"Backend de génération inconnu : {backend}. "
            "Cette solution n'accepte que RAG_GENERATOR=together."
        )
    model_id = (model or config.TOGETHER_CHAT_MODEL).strip()
    if not model_id:
        raise ValueError("Aucun modèle fourni (model / TOGETHER_CHAT_MODEL).")
    return _llm_decision(group, label, description, candidates, examples, model_id)
