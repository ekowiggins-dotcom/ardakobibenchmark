from __future__ import annotations

import re


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def clean_display_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return re.sub(r"\s+", " ", text)


def split_sentences(text: str) -> list[str]:
    text = clean_display_text(text)
    if not text:
        return []
    parts = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    if len(parts) == 1 and len(parts[0]) > 220:
        return [parts[0]]
    return parts


def normalize_for_compare(text: str) -> str:
    text = clean_display_text(text).casefold()
    text = re.sub(r"[^\wğüşöçıİĞÜŞÖÇ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_repetitive(candidate: str, existing: list[str]) -> bool:
    candidate_norm = normalize_for_compare(candidate)
    if not candidate_norm:
        return True
    candidate_words = set(candidate_norm.split())
    for sentence in existing:
        existing_norm = normalize_for_compare(sentence)
        if not existing_norm:
            continue
        if candidate_norm in existing_norm or existing_norm in candidate_norm:
            return True
        existing_words = set(existing_norm.split())
        if len(candidate_words) >= 5 and len(existing_words) >= 5:
            overlap = len(candidate_words & existing_words) / max(len(candidate_words), 1)
            if overlap >= 0.72:
                return True
    return False


def build_executive_why_it_matters(core_assessment: object, strategic_relevance: object) -> str:
    selected: list[str] = []
    for text in [clean_display_text(core_assessment), clean_display_text(strategic_relevance)]:
        for sentence in split_sentences(text):
            if len(selected) >= 2:
                break
            if not is_repetitive(sentence, selected):
                selected.append(sentence)
        if len(selected) >= 2:
            break
    return " ".join(selected)


def compact_summary(summary: object, max_chars: int = 280) -> str:
    sentences = split_sentences(clean_display_text(summary))
    if not sentences:
        return ""
    text = " ".join(sentences[:2])
    if len(text) <= max_chars:
        return text
    trimmed = text[: max_chars - 3].rstrip()
    last_space = trimmed.rfind(" ")
    if last_space > 180:
        trimmed = trimmed[:last_space].rstrip()
    return f"{trimmed}..."
