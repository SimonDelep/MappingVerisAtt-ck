"""Test rapide de la clé Together.ai (sans lancer le RAG).

Usage :
  cd Solution/Solution_RAG/Solution_RAG_Together
  python test_together_key.py
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
import os

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / "dev.env")
load_dotenv(HERE / "veris_mapping" / "dev.env")

API_KEY = (os.getenv("TOGETHER_API_KEY") or "").strip()
BASE_URL = (os.getenv("TOGETHER_BASE_URL") or "https://api.together.ai/v1").strip()
MODEL = (
    os.getenv("TOGETHER_CHAT_MODEL") or "meta-llama/Llama-3.3-70B-Instruct-Turbo"
).strip()


def main() -> int:
    if not API_KEY:
        print("ECHEC : TOGETHER_API_KEY absente dans dev.env")
        return 1

    print(f"Clé chargée   : oui (longueur={len(API_KEY)}, préfixe={API_KEY[:7]}...)")
    print(f"URL           : {BASE_URL}")
    print(f"Modèle        : {MODEL}")
    print("Appel API...")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Réponds uniquement : OK"}],
            max_tokens=16,
            temperature=0,
        )
        text = (response.choices[0].message.content or "").strip()
        print(f"SUCCES : réponse = {text!r}")
        return 0
    except Exception as error:
        print(f"ECHEC : {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
