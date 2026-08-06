#!/usr/bin/env python3
"""Test rapide d'une clé API OpenAI-compatible (Together / OpenAI).

Charge les secrets depuis la racine SIEM (dev.env / .dev.env / .env).
N'affiche jamais la clé en clair (préfixe + longueur seulement).

Usage (depuis la racine SIEM) :
  python tools/check_llm_api.py
  python tools/check_llm_api.py --model meta-llama/Llama-3.3-70B-Instruct-Turbo
  python tools/check_llm_api.py --base-url https://api.together.ai/v1

Variables d'env :
  TOGETHER_API_KEY (prioritaire) ou OPENAI_API_KEY
  TOGETHER_BASE_URL / OPENAI_BASE_URL
  TOGETHER_CHAT_MODEL / OPENAI_CHAT_MODEL (modèle de test par défaut)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permet d'importer _llm_api_common quand on lance `python tools/check_llm_api.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _llm_api_common import (  # noqa: E402
    default_test_model,
    make_client,
    mask_key,
    resolve_credentials,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vérifie qu'une clé API OpenAI-compatible fonctionne (ping chat)."
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Id du modèle pour le ping chat (défaut: TOGETHER_CHAT_MODEL ou Llama 3.3)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Endpoint OpenAI-compatible (override env).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Clé API (override env ; à éviter, préfére dev.env).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=16,
        help="max_tokens du ping (défaut: 16).",
    )
    args = parser.parse_args()

    api_key, base_url, provider = resolve_credentials(args.api_key, args.base_url)
    model = (args.model or default_test_model()).strip()

    print("=== check_llm_api ===")
    if not api_key:
        print("ECHEC : aucune clé trouvée.")
        print("  Ajoutez TOGETHER_API_KEY ou OPENAI_API_KEY dans dev.env (racine SIEM).")
        print("  Template : copier .dev.env.example vers dev.env")
        return 1

    print(f"Provider      : {provider}")
    print(f"Clé           : {mask_key(api_key)}")
    print(f"Base URL      : {base_url}")
    print(f"Modèle test   : {model}")
    print("Appel chat.completions...")

    try:
        client = make_client(api_key, base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Réponds uniquement : OK"}],
            max_tokens=args.max_tokens,
            temperature=0,
        )
        text = (response.choices[0].message.content or "").strip()
        print(f"SUCCES : réponse = {text!r}")
        return 0
    except Exception as error:
        err_name = type(error).__name__
        print(f"ECHEC ({err_name}) : {error}")
        print()
        print("Pistes :")
        print("  - 401 / Invalid authentication : cle invalide ou absente")
        print("  - 404 model_not_found       : mauvais id -> list_llm_models.py")
        print("  - timeout / connection      : reseau ou base URL incorrecte")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
