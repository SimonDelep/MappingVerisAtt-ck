#!/usr/bin/env python3
"""Liste les modèles accessibles via une API OpenAI-compatible (Together / OpenAI).

Usage (depuis la racine SIEM) :
  python tools/list_llm_models.py
  python tools/list_llm_models.py --filter llama
  python tools/list_llm_models.py --filter qwen --limit 30
  python tools/list_llm_models.py --json -o models.json

Variables d'env : TOGETHER_API_KEY / OPENAI_API_KEY (+ base URL associées).

Note : Together renvoie parfois une liste JSON nue (pas {"data": [...]}) ;
ce script appelle /models en HTTP direct pour rester robuste.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _llm_api_common import (  # noqa: E402
    mask_key,
    resolve_credentials,
)


def fetch_models(api_key: str, base_url: str) -> list[dict]:
    """GET /models en HTTP (plus robuste que le SDK OpenAI pour Together)."""
    import httpx

    url = f"{base_url.rstrip('/')}/models"
    response = httpx.get(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60.0,
    )
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, list):
        models = payload
    elif isinstance(payload, dict):
        models = payload.get("data", payload.get("models", []))
        if not isinstance(models, list):
            raise ValueError(f"Format /models inattendu : clé data={type(models)}")
    else:
        raise ValueError(f"Format /models inattendu : {type(payload)}")

    rows: list[dict] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        row = {
            "id": item.get("id") or "",
            "owned_by": item.get("owned_by")
            or item.get("organization")
            or "",
            "object": item.get("object"),
            "created": item.get("created"),
            "type": item.get("type"),
            "context_length": item.get("context_length"),
            "display_name": item.get("display_name"),
        }
        rows.append({k: v for k, v in row.items() if v is not None and v != ""})
    return rows


def _looks_chat(model_id: str, raw: dict) -> bool:
    """Heuristique : exclut embeddings / image / audio / rerank d'après l'id."""
    mid = (model_id or "").lower()
    exclude_tokens = (
        "embed",
        "embedding",
        "image",
        "vision",
        "whisper",
        "tts",
        "moderation",
        "rerank",
        "transcri",
    )
    if any(tok in mid for tok in exclude_tokens):
        return False
    mtype = str(raw.get("type") or "").lower()
    if mtype in {"embedding", "image", "audio", "moderation"}:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Liste les modèles exposés par l'API OpenAI-compatible du compte."
    )
    parser.add_argument(
        "--filter",
        default=None,
        help="Sous-chaîne insensible à la casse sur l'id (ex: llama, qwen, deepseek).",
    )
    parser.add_argument(
        "--chat-only",
        action="store_true",
        help="Garde type=chat si présent, sinon filtre heuristic sur l'id.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Nombre max de lignes après filtrage (0 = tout).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Sortie JSON (liste d'objets).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Écrit le JSON dans un fichier (implique --json).",
    )
    parser.add_argument("--base-url", default=None, help="Override base URL.")
    parser.add_argument("--api-key", default=None, help="Override clé API.")
    args = parser.parse_args()

    api_key, base_url, provider = resolve_credentials(args.api_key, args.base_url)
    if not api_key:
        print("ECHEC : aucune clé trouvée (TOGETHER_API_KEY ou OPENAI_API_KEY).")
        return 1

    want_json = args.json or bool(args.output)
    if not want_json:
        print("=== list_llm_models ===")
        print(f"Provider : {provider}")
        print(f"Clé      : {mask_key(api_key)}")
        print(f"Base URL : {base_url}")
        print("Appel GET /models ...")

    try:
        rows = fetch_models(api_key, base_url)
    except Exception as error:
        print(f"ECHEC ({type(error).__name__}) : {error}")
        return 1

    rows.sort(key=lambda r: (r.get("id") or "").lower())

    filt = (args.filter or "").strip().lower()
    if filt:
        rows = [r for r in rows if filt in (r.get("id") or "").lower()]
    if args.chat_only:
        typed_chat = [r for r in rows if r.get("type") == "chat"]
        if typed_chat:
            rows = typed_chat
        else:
            rows = [r for r in rows if _looks_chat(r.get("id") or "", r)]
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    if want_json:
        payload = json.dumps(rows, ensure_ascii=False, indent=2)
        if args.output:
            out_path = Path(args.output)
            out_path.write_text(payload + "\n", encoding="utf-8")
            print(f"OK : {len(rows)} modèle(s) écrits dans {out_path}")
        else:
            print(payload)
        return 0

    print(f"Total après filtres : {len(rows)}")
    print()
    for row in rows:
        mid = row.get("id") or "?"
        extra_bits = []
        if row.get("owned_by"):
            extra_bits.append(str(row["owned_by"]))
        if row.get("type"):
            extra_bits.append(str(row["type"]))
        if row.get("context_length"):
            extra_bits.append(f"ctx={row['context_length']}")
        if row.get("display_name"):
            extra_bits.append(str(row["display_name"]))
        suffix = f"  ({', '.join(extra_bits)})" if extra_bits else ""
        print(f"  {mid}{suffix}")

    print()
    print("Pour figer 3 modèles (phase 1) dans .dev.env :")
    print("  RAG_MULTI_LLM_MODELS=id1,id2,id3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
