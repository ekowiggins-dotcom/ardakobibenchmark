from __future__ import annotations

import re
from pathlib import Path


def normalize_whitespace(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_for_llm(text: str, max_chars: int = 24000) -> str:
    text = normalize_whitespace(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TRUNCATED FOR LLM REVIEW]"


def read_cleaned_text(root_dir: Path, cleaned_text_path: str) -> str:
    path = root_dir / cleaned_text_path
    if not path.exists():
        return ""
    return normalize_whitespace(path.read_text(encoding="utf-8", errors="ignore"))


if __name__ == "__main__":
    print("clean_text.py provides helper functions for the pipeline.")
