"""Helpers partagés pour les scripts tools/ de diagnostic LLM (API OpenAI-compatible)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOGETHER_BASE_URL = "https://api.together.ai/v1"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TEST_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"


def load_env() -> None:
    """Charge dev.env / .env depuis la racine SIEM et le cwd."""
    load_dotenv(ROOT / "dev.env")
    load_dotenv(ROOT / ".dev.env")
    load_dotenv(ROOT / ".env")
    load_dotenv()


def resolve_credentials(
    api_key: str | None = None,
    base_url: str | None = None,
) -> tuple[str, str, str]:
    """Retourne (api_key, base_url, provider_label).

    Priorité clé : arg > TOGETHER_API_KEY > OPENAI_API_KEY.
    Priorité URL  : arg > URL du provider choisi > défaut Together/OpenAI.
    """
    load_env()

    together_key = (os.getenv("TOGETHER_API_KEY") or "").strip()
    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    key = (api_key or "").strip() or together_key or openai_key

    if not key:
        return "", "", ""

    if (api_key or "").strip():
        # Clé fournie en CLI : déduire le provider d'après base_url / défauts.
        if (base_url or "").strip():
            url = (base_url or "").strip()
            label = "custom"
        elif together_key and key == together_key:
            url = (
                (os.getenv("TOGETHER_BASE_URL") or "").strip()
                or DEFAULT_TOGETHER_BASE_URL
            )
            label = "together"
        elif openai_key and key == openai_key:
            url = (
                (os.getenv("OPENAI_BASE_URL") or "").strip()
                or DEFAULT_OPENAI_BASE_URL
            )
            label = "openai"
        else:
            url = (
                (base_url or "").strip()
                or (os.getenv("TOGETHER_BASE_URL") or "").strip()
                or (os.getenv("OPENAI_BASE_URL") or "").strip()
                or DEFAULT_TOGETHER_BASE_URL
            )
            label = "custom"
    elif together_key:
        url = (
            (base_url or "").strip()
            or (os.getenv("TOGETHER_BASE_URL") or "").strip()
            or DEFAULT_TOGETHER_BASE_URL
        )
        label = "together"
    else:
        url = (
            (base_url or "").strip()
            or (os.getenv("OPENAI_BASE_URL") or "").strip()
            or DEFAULT_OPENAI_BASE_URL
        )
        label = "openai"

    return key, url.rstrip("/"), label


def mask_key(api_key: str) -> str:
    if not api_key:
        return "(absente)"
    if len(api_key) <= 10:
        return f"{api_key[:3]}..."
    return f"{api_key[:7]}... (len={len(api_key)})"


def default_test_model() -> str:
    load_env()
    return (
        (os.getenv("TOGETHER_CHAT_MODEL") or "").strip()
        or (os.getenv("OPENAI_CHAT_MODEL") or "").strip()
        or DEFAULT_TEST_MODEL
    )


def make_client(api_key: str, base_url: str):
    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url)
