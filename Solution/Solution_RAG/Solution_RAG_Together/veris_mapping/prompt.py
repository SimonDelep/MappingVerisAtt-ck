"""Construction du prompt LLM pour le mapping d'une capacité VERIS.

Le LLM ne renvoie qu'une décision minimale par technique retenue :
identifiant ATT&CK, type de relation, confiance et justification. Les noms de
techniques et les tactiques sont ensuite ré-enrichis depuis le catalogue ATT&CK
local (cf. generate_mapping.py), ce qui évite les hallucinations de libellés.
"""

from __future__ import annotations

import json

SYSTEM_PROMPT = """\
Tu es un expert en cybersécurité spécialisé dans le mapping entre le vocabulaire
VERIS (description d'incidents) et le framework MITRE ATT&CK (techniques adverses).

Ta tâche : pour UNE capacité VERIS, choisir parmi une liste de techniques ATT&CK
candidates celles qui correspondent réellement à cette capacité.

Règles :
- Choisis uniquement des techniques présentes dans la liste de candidats fournie.
- Utilise EXACTEMENT les identifiants ATT&CK fournis (ex: T1059 ou T1059.001).
- N'invente jamais d'identifiant ni de technique hors de la liste.
- Une capacité peut correspondre à 0, 1 ou plusieurs techniques.
- Si aucune technique candidate ne correspond, renvoie no_mapping_found = true.
- Inspire-toi des exemples de mappings experts s'ils sont fournis, sans les copier
  aveuglément (ils proviennent d'autres versions).
- Réponds STRICTEMENT en JSON valide, sans texte autour, au schéma demandé.
"""

# Pondération confiance -> score numérique (aligné sur les fichiers de résultat).
CONFIDENCE_SCORES = {"high": 1.0, "medium": 0.6, "low": 0.3}


def build_user_prompt(
    capability_group: str,
    label: str,
    description: str,
    candidates: list[dict],
    examples: list[dict],
) -> str:
    candidate_lines = []
    for c in candidates:
        tactics = ", ".join(c.get("tactics", [])) or "n/a"
        candidate_lines.append(
            f"- {c['attack_id']} | {c['name']} | tactiques: {tactics}"
        )
    candidates_block = "\n".join(candidate_lines) if candidate_lines else "(aucun)"

    if examples:
        example_lines = []
        for e in examples:
            example_lines.append(
                f"- [VERIS {e.get('source_version', '?')}] « {e.get('label', '')} » "
                f"-> {e.get('mapped_summary', '')}"
            )
        examples_block = (
            "\nExemples de mappings experts pour des capacités similaires "
            "(autres versions) :\n" + "\n".join(example_lines) + "\n"
        )
    else:
        examples_block = ""

    schema = {
        "no_mapping_found": "boolean",
        "ambiguous": "boolean",
        "notes": "string (vide si rien à signaler)",
        "mappings": [
            {
                "attack_id": "Txxxx ou Txxxx.yyy (parmi les candidats)",
                "mapping_type": "related_to",
                "confidence": "high | medium | low",
                "justification": "phrase courte expliquant la correspondance",
            }
        ],
    }

    return (
        f"Capacité VERIS à mapper :\n"
        f"- groupe : {capability_group}\n"
        f"- libellé : {label}\n"
        f"- description : {description or label}\n\n"
        f"Techniques ATT&CK candidates :\n{candidates_block}\n"
        f"{examples_block}\n"
        f"Renvoie un objet JSON respectant ce schéma :\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n"
    )
