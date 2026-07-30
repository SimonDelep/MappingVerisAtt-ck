"""Étape de décision via Together.ai (API compatible OpenAI).

Backend unique de cette solution : le LLM cloud choisit les techniques ATT&CK
parmi les candidats récupérés par similarité sémantique.

Format de sortie (identique au RAG local) :

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

import config
from prompt import SYSTEM_PROMPT, build_user_prompt

_together_client = None


def _get_together_client():
    """Client OpenAI pointé vers l'API Together.ai."""
    global _together_client
    if _together_client is None:
        from openai import OpenAI

        if not config.TOGETHER_API_KEY:
            raise ValueError("TOGETHER_API_KEY manquante.")
        print(
            f"  [together] modèle={config.TOGETHER_CHAT_MODEL} "
            f"url={config.TOGETHER_BASE_URL}"
        )
        _together_client = OpenAI(
            api_key=config.TOGETHER_API_KEY,
            base_url=config.TOGETHER_BASE_URL,
        )
    return _together_client


def _parse_json(content: str) -> dict:
    content = (content or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1:
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


def _together_decision(group, label, description, candidates, examples) -> dict:
    client = _get_together_client()
    user_prompt = build_user_prompt(group, label, description, candidates, examples)
    response = client.chat.completions.create(
        model=config.TOGETHER_CHAT_MODEL,
        temperature=config.GENERATION_TEMPERATURE,
        max_tokens=config.GENERATION_MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    text = response.choices[0].message.content or ""
    parsed = _parse_json(text)
    return _filter_to_candidates(parsed, candidates)


def generate_decision(
    group: str,
    label: str,
    description: str,
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    use_examples: bool,
) -> dict:
    del attack_index, use_examples  # filtrés côté prompt / candidates
    backend = config.GENERATOR
    if backend == "together":
        return _together_decision(group, label, description, candidates, examples)
    raise ValueError(
        f"Backend de génération inconnu : {backend}. "
        "Cette solution n'accepte que RAG_GENERATOR=together."
    )
