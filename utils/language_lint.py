from __future__ import annotations

import re

import pandas as pd


VISIBLE_TEXT_FIELDS = [
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "awareness_reason",
    "triage_reason",
    "cluster_title",
    "cluster_summary",
    "cluster_core_assessment",
    "why_it_matters",
    "competitor_intent",
    "management_takeaway",
]

FORMAL_SUFFIX_PATTERNS = [
    r"\b\w+maktadır\b",
    r"\b\w+mektedir\b",
    r"\b\w+mıştır\b",
    r"\b\w+miştir\b",
    r"\b\w+acaktır\b",
    r"\b\w+ecektir\b",
]

BUREAUCRATIC_PATTERNS = [
    r"\bgereklidir\b",
    r"\bgerekir\b",
    r"\bedilmelidir\b",
    r"\bdeğerlendirilmelidir\b",
    r"\balınmalıdır\b",
    r"\byapılmalıdır\b",
    r"\bolmalıdır\b",
    r"\bizlenmelidir\b",
    r"\beklenmelidir\b",
]

PASSIVE_REPORTING_PATTERNS = [
    r"\bbulunmaktadır\b",
    r"\bsunulmaktadır\b",
    r"\bsağlanmaktadır\b",
    r"\bgösterilmektedir\b",
    r"\byansıtılmaktadır\b",
    r"\bbelirtilmektedir\b",
    r"\bifade edilmektedir\b",
]

HARD_BANNED_PHRASES = [
    "teşkil ediyor",
    "teşkil etmektedir",
    "önem arz ediyor",
    "önem arz etmektedir",
    "stratejik açıdan önemlidir",
    "değer yaratma potansiyeli",
    "değer yaratma potansiyeli taşımaktadır",
    "konumlanmasını güçlendiriyor",
    "konumlanmasını güçlendirmektedir",
    "rekabetçi avantaj sağlamaktadır",
    "rekabetçi hamle olarak değerlendirilmelidir",
    "doğrudan rakip bir hamle",
    "doğrudan rakip pozisyon",
    "portföyünü büyütmeyi hedefliyor",
    "portföyünü büyütmeyi hedeflemektedir",
    "müşteri deneyimi açısından değer yaratıyor",
]

FILLER_WORDS = [
    "açısından",
    "kapsamında",
    "yönelik",
]

BROKEN_TEXT_PATTERNS = {
    r"\bmüştdilde\b": "Bozuk birleşik kelime: 'müştdilde'",
    r"\b\w+tdilde\b": "Olası bozuk birleşik kelime",
}


def clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _field_text(row) -> str:
    return "\n".join(clean(row.get(column, "")) for column in VISIBLE_TEXT_FIELDS)


def _add_regex_warnings(text: str, patterns: list[str], weight: int, label: str, warnings: list[str]) -> int:
    score = 0
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if not matches:
            continue
        found = sorted({str(match).strip() for match in matches if str(match).strip()})
        warnings.append(f"{label}: {', '.join(found)} (+{weight * len(matches)})")
        score += weight * len(matches)
    return score


def lint_llm_language(row) -> dict:
    text = _field_text(row)
    lowered = text.casefold()
    warnings: list[str] = []
    score = 0

    for phrase in HARD_BANNED_PHRASES:
        count = lowered.count(phrase.casefold())
        if count:
            warnings.append(f"Sert yasaklı ifade: '{phrase}' (+{3 * count})")
            score += 3 * count

    score += _add_regex_warnings(text, FORMAL_SUFFIX_PATTERNS, 2, "Resmi zaman/ek", warnings)
    score += _add_regex_warnings(text, BUREAUCRATIC_PATTERNS, 3, "Bürokratik zorunluluk dili", warnings)
    score += _add_regex_warnings(text, PASSIVE_REPORTING_PATTERNS, 3, "Pasif rapor dili", warnings)

    for filler in FILLER_WORDS:
        count = len(re.findall(rf"\b{re.escape(filler)}\b", lowered, flags=re.IGNORECASE))
        if count:
            warnings.append(f"Dolgu kelime: '{filler}' (+{count})")
            score += count

    for pattern, warning in BROKEN_TEXT_PATTERNS.items():
        count = len(re.findall(pattern, lowered, flags=re.IGNORECASE))
        if count:
            warnings.append(f"{warning} (+{3 * count})")
            score += 3 * count

    unique_warnings = list(dict.fromkeys(warnings))
    return {
        "language_lint_score": int(score),
        "language_lint_warnings": unique_warnings,
        "needs_language_review": score >= 3,
        "needs_rewrite": score >= 6,
    }
