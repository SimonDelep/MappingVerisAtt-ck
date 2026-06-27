"""Étape de décision : choisir les techniques ATT&CK pour une capacité VERIS.

Trois backends (config.GENERATOR) renvoyant TOUS le même format :

    {
      "no_mapping_found": bool,
      "ambiguous": bool,
      "notes": str,
      "mappings": [
        {"attack_id": "Txxxx[.yyy]", "mapping_type": "related_to",
         "confidence": "high|medium|low", "justification": "..."}
      ]
    }

  - "retrieval" : sélection par similarité sémantique (aucun LLM) — défaut local.
  - "local_llm" : LLM local via transformers.
  - "llm"       : LLM Azure OpenAI.
"""

from __future__ import annotations

import json

import config
from prompt import SYSTEM_PROMPT, build_user_prompt


# ==================== Backend "retrieval" (sans LLM) ====================
def _retrieval_decision(candidates, examples, attack_index, use_examples) -> dict:
    # IDs soutenus par des mappings experts proches (toutes versions récupérées).
    support_ids: set[str] = set()
    # IDs suggérés par l'exemple le PLUS proche (analogique fort).
    closest_ids: list[str] = []
    if use_examples and examples:
        for ex in examples:
            for m in ex.get("mapped", []):
                aid = (m.get("attack_id") or "").strip().upper()
                if aid in attack_index:
                    support_ids.add(aid)
        for m in examples[0].get("mapped", []):
            aid = (m.get("attack_id") or "").strip().upper()
            if aid in attack_index and aid not in closest_ids:
                closest_ids.append(aid)

    mappings: list[dict] = []
    chosen: set[str] = set()

    for c in candidates:
        aid = (c.get("attack_id") or "").strip().upper()
        if not aid or aid in chosen:
            continue
        dist = c.get("distance")
        sim = (1.0 - dist) if isinstance(dist, (int, float)) else 0.0

        confidence = None
        if sim >= config.RETRIEVAL_SIM_HIGH:
            confidence = "high"
        elif sim >= config.RETRIEVAL_SIM_MED:
            confidence = "medium"
        elif use_examples and aid in support_ids:
            confidence = "medium"

        if confidence:
            note = f"Similarité sémantique={sim:.2f}."
            if aid in support_ids:
                note += " Soutenu par un mapping expert d'une version proche."
            mappings.append(
                {
                    "attack_id": aid,
                    "mapping_type": "related_to",
                    "confidence": confidence,
                    "justification": note,
                }
            )
            chosen.add(aid)

    # Ajouts "exemple seul" : techniques de l'exemple le plus proche non déjà retenues.
    if use_examples:
        added = 0
        for aid in closest_ids:
            if added >= config.RETRIEVAL_MAX_EXAMPLE_ONLY:
                break
            if aid in chosen:
                continue
            mappings.append(
                {
                    "attack_id": aid,
                    "mapping_type": "related_to",
                    "confidence": "low",
                    "justification": "Suggéré par le mapping expert le plus proche.",
                }
            )
            chosen.add(aid)
            added += 1

    return {
        "no_mapping_found": not mappings,
        "ambiguous": False,
        "notes": "" if mappings else "Aucune correspondance trouvée.",
        "mappings": mappings,
    }


# ==================== Parsing JSON commun aux backends LLM ====================
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


# ==================== Backend "llm" (Azure OpenAI) ====================
def _azure_llm_decision(group, label, description, candidates, examples) -> dict:
    from embeddings import get_azure_client

    user_prompt = build_user_prompt(group, label, description, candidates, examples)
    client = get_azure_client()
    response = client.chat.completions.create(
        model=config.OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=config.GENERATION_TEMPERATURE,
        response_format={"type": "json_object"},
    )
    return _parse_json(response.choices[0].message.content)


# ==================== Backend "local_llm" (transformers) ====================
_local_pipe = None


def _get_local_pipe():
    global _local_pipe
    if _local_pipe is None:
        from transformers import pipeline

        print(f"  [local_llm] chargement de {config.LOCAL_LLM_MODEL} ...")
        _local_pipe = pipeline(
            "text-generation",
            model=config.LOCAL_LLM_MODEL,
            torch_dtype="auto",
            device_map="auto",
        )
    return _local_pipe


def _local_llm_decision(group, label, description, candidates, examples) -> dict:
    pipe = _get_local_pipe()
    user_prompt = build_user_prompt(group, label, description, candidates, examples)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    out = pipe(messages, max_new_tokens=800, do_sample=False, return_full_text=False)
    text = out[0]["generated_text"]
    if isinstance(text, list):  # certains pipelines renvoient une liste de messages
        text = text[-1].get("content", "")
    return _parse_json(text)


# ==================== Point d'entrée ====================
def generate_decision(
    group: str,
    label: str,
    description: str,
    candidates: list[dict],
    examples: list[dict],
    attack_index: dict,
    use_examples: bool,
) -> dict:
    backend = config.GENERATOR
    if backend == "retrieval":
        return _retrieval_decision(candidates, examples, attack_index, use_examples)
    if backend == "llm":
        return _azure_llm_decision(group, label, description, candidates, examples)
    if backend == "local_llm":
        return _local_llm_decision(group, label, description, candidates, examples)
    raise ValueError(f"Backend de génération inconnu : {backend}")
