"""Construction du prompt LLM (visée F1 + volume sol≈exp) pour VERIS -> ATT&CK.

Le LLM ne renvoie qu'une décision minimale par technique retenue :
identifiant ATT&CK, type de relation, confiance et justification. Les noms de
techniques et les tactiques sont ensuite ré-enrichis depuis le catalogue ATT&CK
local (cf. generate_mapping.py), ce qui évite les hallucinations de libellés.
"""

from __future__ import annotations

import json

# Longueur max d'extrait de description ATT&CK injecté dans le prompt.
DESC_TRUNCATE = 280

SYSTEM_PROMPT = """\
Tu es un expert en cybersécurité spécialisé dans le mapping entre le vocabulaire
VERIS (description d'incidents) et le framework MITRE ATT&CK (techniques adverses).

Ta tâche : pour UNE capacité VERIS, sélectionner parmi une liste fermée de
techniques ATT&CK candidates celles qui correspondent de façon justifiée à
cette capacité.

Objectif prioritaire : MAXIMISER LE F1 (bon compromis précision / rappel) et
produire un VOLUME de mappings réaliste.
Une capacité VERIS a souvent PLUSIEURS techniques ATT&CK associées : ne te
limite pas à 1 ou 2 si plusieurs candidats sont clairement pertinents.
Évite toutefois de tout sélectionner : omets seulement les relations faibles
ou hors sujet.

Règles strictes :
- Choisis UNIQUEMENT des techniques présentes dans la liste de candidats fournie.
- Utilise EXACTEMENT les identifiants ATT&CK fournis (ex: T1059 ou T1059.001).
- N'invente jamais d'identifiant hors de la liste.
- Une capacité peut correspondre à 0, 1 ou plusieurs techniques.
- Si aucune technique candidate ne correspond, renvoie
  no_mapping_found = true et mappings = [].
- Retiens une technique si la correspondance est claire OU si elle est
  soutenue par un exemple expert proche (même si la similarité pure est moyenne).
- Confiance "high" si la correspondance sémantique est nette, sinon "medium".
  N'utilise "low" que pour une relation faible mais encore utile.
- Les exemples experts (autres versions) sont une INSPIRATION utile, pas une
  vérité à copier aveuglément (libellés et techniques peuvent différer).
- Réponds STRICTEMENT en JSON valide, sans markdown, sans texte autour, au
  schéma demandé.
"""

# Pondération confiance -> score numérique (aligné sur les fichiers de résultat).
CONFIDENCE_SCORES = {"high": 1.0, "medium": 0.6, "low": 0.3}


def _truncate(text: str, limit: int = DESC_TRUNCATE) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


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
        desc = _truncate(c.get("document") or c.get("description") or "")
        line = f"- {c['attack_id']} | {c['name']} | tactiques: {tactics}"
        if desc:
            line += f" | desc: {desc}"
        candidate_lines.append(line)
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
            "(autres versions, inspiration seulement) :\n"
            + "\n".join(example_lines)
            + "\n"
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
        f"Techniques ATT&CK candidates (liste FERMÉE) :\n{candidates_block}\n"
        f"{examples_block}\n"
        f"Consignes de sélection :\n"
        f"- Retiens toutes les techniques clairement alignées ou soutenues "
        f"par un exemple expert proche.\n"
        f"- Une capacité a souvent plusieurs mappings : vise la couverture "
        f"réaliste, pas le minimum.\n"
        f"- Omets seulement si la relation est faible / hors sujet.\n"
        f"- Qualité et couverture comptent toutes les deux (F1).\n\n"
        f"Renvoie UNIQUEMENT un objet JSON respectant ce schéma :\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n"
    )
