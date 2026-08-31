from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_ITEMS = 5
DEFAULT_MAX_CHARS = 8000
DEFAULT_TIMEOUT_SECONDS = 60

logger = logging.getLogger(__name__)


class MissingApiKeyError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    has_api_key: bool
    max_items_per_run: int
    max_chars_per_item: int


def _load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")


def _safe_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default


def get_llm_config() -> LLMConfig:
    _load_env()
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower() or DEFAULT_PROVIDER
    model = os.getenv("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return LLMConfig(
        provider=provider,
        model=model,
        has_api_key=bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
        max_items_per_run=_safe_int("MAX_LLM_ITEMS_PER_RUN", DEFAULT_MAX_ITEMS),
        max_chars_per_item=_safe_int("MAX_CHARS_PER_ITEM", DEFAULT_MAX_CHARS),
    )


def summarize_with_anthropic(prompt: str, model: str | None = None, max_tokens: int = 1200) -> str:
    _load_env()
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise MissingApiKeyError("ANTHROPIC_API_KEY bulunamadı.")
    if Anthropic is None:
        raise RuntimeError("anthropic paketi yüklü değil. requirements.txt içinden yükleyin.")

    selected_model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    timeout_seconds = _safe_int("LLM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    client = Anthropic(api_key=api_key, timeout=timeout_seconds)
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            message = client.messages.create(
                model=selected_model,
                max_tokens=max_tokens,
                temperature=0.2,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            if not message.content:
                return ""
            first = message.content[0]
            return getattr(first, "text", "") or ""
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Anthropic çağrısı başarısız oldu; deneme=%s, hata=%s: %s",
                attempt + 1,
                type(exc).__name__,
                exc,
            )
            if attempt == 0:
                time.sleep(1)
    raise RuntimeError(f"Anthropic çağrısı tamamlanamadı: {type(last_error).__name__}: {last_error}")
