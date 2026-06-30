from __future__ import annotations

import re
import unicodedata
from datetime import date
from urllib.parse import urlparse


TURKISH_MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "agustos": 8,
    "eylül": 9,
    "eylul": 9,
    "ekim": 10,
    "kasım": 11,
    "kasim": 11,
    "aralık": 12,
    "aralik": 12,
}


def normalize_month_token(value: str) -> str:
    token = unicodedata.normalize("NFKD", value.casefold())
    token = "".join(ch for ch in token if not unicodedata.combining(ch))
    token = token.replace("ı", "i")
    return token

TEXT_DATE_RE = re.compile(
    r"\b(?P<day>\d{1,2})\s+"
    r"(?P<month>Ocak|Şubat|Subat|Mart|Nisan|Mayıs|Mayis|Haziran|Temmuz|Ağustos|Agustos|Eylül|Eylul|Ekim|Kasım|Kasim|Aralık|Aralik)"
    r"\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)
DMY_RE = re.compile(r"\b(?P<day>\d{1,2})[./](?P<month>\d{1,2})[./](?P<year>\d{4})\b")
ISO_RE = re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")
MONTH_NAME_PATTERN = (
    r"Ocak|Şubat|Subat|Mart|Nisan|Mayıs|Mayis|Haziran|Temmuz|Ağustos|Agustos|"
    r"Eylül|Eylul|Ekim|Kasım|Kasim|Aralık|Aralik"
)
TEXT_DATE_RANGE_SAME_MONTH_RE = re.compile(
    rf"\b(?P<start_day>\d{{1,2}})\s*[-–]\s*(?P<end_day>\d{{1,2}})\s+"
    rf"(?P<month>{MONTH_NAME_PATTERN})\s+(?P<year>\d{{4}})\b",
    re.IGNORECASE,
)
TEXT_DATE_RANGE_FULL_RE = re.compile(
    rf"\b(?P<start_day>\d{{1,2}})\s+(?P<start_month>{MONTH_NAME_PATTERN})"
    rf"(?:\s+(?P<start_year>\d{{4}}))?\s*[-–]\s*"
    rf"(?P<end_day>\d{{1,2}})\s+(?P<end_month>{MONTH_NAME_PATTERN})\s+(?P<end_year>\d{{4}})\b",
    re.IGNORECASE,
)
DMY_RANGE_RE = re.compile(
    r"\b(?P<start_day>\d{1,2})[./](?P<start_month>\d{1,2})[./](?P<start_year>\d{4})"
    r"\s*[-–]\s*"
    r"(?P<end_day>\d{1,2})[./](?P<end_month>\d{1,2})[./](?P<end_year>\d{4})\b"
)
URL_DATE_RE = re.compile(
    r"(?:/|-|_)(?P<year>20\d{2})(?:/|-|_)(?P<month>\d{1,2})(?:/|-|_)(?P<day>\d{1,2})(?:/|-|_|$)"
)
CAMPAIGN_CONTEXT_RE = re.compile(
    r"(kampanya\s*(?:tarihi|dönemi|donemi|geçerlilik tarihi|gecerlilik tarihi|son tarihi)|"
    r"son katılım tarihi|son katilim tarihi|son kullanım tarihi|son kullanim tarihi|"
    r"puan kullanım tarihi|puan kullanim tarihi|kampanya|maxipuan|maximum|ticari kart|bankamatik)",
    re.IGNORECASE,
)
CAMPAIGN_END_CONTEXT_RE = re.compile(
    r"(tarihine kadar|['’]?(?:ya|ye|a|e)\s+kadar|kadar geçerlidir|kadar gecerlidir|son katılım tarihi|son katilim tarihi|"
    r"son başvuru tarihi|son basvuru tarihi|son kullanım tarihi|son kullanim tarihi|"
    r"kampanya bitiş tarihi|kampanya bitis tarihi|kampanya son tarihi|geçerlilik bitiş tarihi|"
    r"gecerlilik bitis tarihi|puan kullanım son tarihi|puan kullanim son tarihi|"
    r"puan kullanım tarihi|puan kullanim tarihi|son tarih|son gün|son gun|bitiş tarihi|bitis tarihi)",
    re.IGNORECASE,
)
CAMPAIGN_START_CONTEXT_RE = re.compile(
    r"(kampanya başlangıç tarihi|kampanya baslangic tarihi|kampanya başlangıcı|kampanya baslangici|"
    r"kampanya dönemi|kampanya donemi)",
    re.IGNORECASE,
)
PRESS_CONTEXT_RE = re.compile(r"(basın|basin|bülten|bulten|duyuru|haber|press|release|news|kurumsal-iletisim)", re.IGNORECASE)

SEMANTIC_DATE_FIELDS = [
    "publication_date",
    "announcement_date",
    "campaign_start_date",
    "campaign_end_date",
    "event_date_type",
    "recency_basis_date",
    "recency_basis_reason",
    "date_confidence",
    "raw_date_text",
]


def empty_result(raw_date_text: str = "", date_source: str = "missing") -> dict[str, str]:
    return {
        "normalized_date": "",
        "date_confidence": "Yok",
        "date_source": date_source,
        "raw_date_text": raw_date_text,
    }


def _build_result(year: int, month: int, day: int, raw: str, confidence: str, source: str) -> dict[str, str]:
    try:
        normalized = date(year, month, day).isoformat()
    except ValueError:
        return empty_result(raw, source)
    return {
        "normalized_date": normalized,
        "date_confidence": confidence,
        "date_source": source,
        "raw_date_text": raw,
    }


def _iso_date(year: int, month: int, day: int) -> str:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _month_number(value: str) -> int:
    return TURKISH_MONTHS[normalize_month_token(value)]


def empty_semantic_result(raw_date_text: str = "") -> dict[str, str]:
    result = {field: "" for field in SEMANTIC_DATE_FIELDS}
    result["event_date_type"] = "Belirsiz"
    result["date_confidence"] = "Yok"
    result["raw_date_text"] = raw_date_text
    result["normalized_date"] = ""
    result["date_source"] = "missing"
    return result


def parse_turkish_date(text: str, date_source: str = "inferred_from_text", confidence: str = "Düşük") -> dict[str, str]:
    value = str(text or "")
    if not value.strip():
        return empty_result()

    match = TEXT_DATE_RE.search(value)
    if match:
        month_name = normalize_month_token(match.group("month"))
        return _build_result(
            int(match.group("year")),
            TURKISH_MONTHS[month_name],
            int(match.group("day")),
            match.group(0),
            confidence,
            date_source,
        )

    match = DMY_RE.search(value)
    if match:
        return _build_result(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            match.group(0),
            confidence,
            date_source,
        )

    match = ISO_RE.search(value)
    if match:
        return _build_result(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            match.group(0),
            confidence,
            date_source,
        )

    return empty_result()


def parse_turkish_date_ranges(text: str) -> list[dict[str, str]]:
    value = str(text or "")
    ranges: list[dict[str, str]] = []

    for match in DMY_RANGE_RE.finditer(value):
        start_date = _iso_date(int(match.group("start_year")), int(match.group("start_month")), int(match.group("start_day")))
        end_date = _iso_date(int(match.group("end_year")), int(match.group("end_month")), int(match.group("end_day")))
        if start_date and end_date:
            ranges.append({"start_date": start_date, "end_date": end_date, "raw_date_text": match.group(0)})

    for match in TEXT_DATE_RANGE_SAME_MONTH_RE.finditer(value):
        month = _month_number(match.group("month"))
        year = int(match.group("year"))
        start_date = _iso_date(year, month, int(match.group("start_day")))
        end_date = _iso_date(year, month, int(match.group("end_day")))
        if start_date and end_date:
            ranges.append({"start_date": start_date, "end_date": end_date, "raw_date_text": match.group(0)})

    for match in TEXT_DATE_RANGE_FULL_RE.finditer(value):
        end_year = int(match.group("end_year"))
        start_year = int(match.group("start_year") or end_year)
        start_date = _iso_date(start_year, _month_number(match.group("start_month")), int(match.group("start_day")))
        end_date = _iso_date(end_year, _month_number(match.group("end_month")), int(match.group("end_day")))
        if start_date and end_date:
            ranges.append({"start_date": start_date, "end_date": end_date, "raw_date_text": match.group(0)})

    dedup = {}
    for item in ranges:
        dedup[(item["start_date"], item["end_date"], item["raw_date_text"])] = item
    return list(dedup.values())


def has_campaign_end_context(text: str, raw_date_text: str = "") -> bool:
    value = str(text or "")
    if CAMPAIGN_END_CONTEXT_RE.search(value):
        return True
    raw = str(raw_date_text or "")
    if raw:
        idx = value.find(raw)
        if idx >= 0:
            window = value[max(0, idx - 90) : idx + len(raw) + 90]
            return bool(CAMPAIGN_END_CONTEXT_RE.search(window))
    return False


def has_campaign_start_context(text: str, raw_date_text: str = "") -> bool:
    value = str(text or "")
    if CAMPAIGN_START_CONTEXT_RE.search(value):
        return True
    raw = str(raw_date_text or "")
    if raw:
        idx = value.find(raw)
        if idx >= 0:
            window = value[max(0, idx - 90) : idx + len(raw) + 90]
            return bool(CAMPAIGN_START_CONTEXT_RE.search(window))
    return False


def parse_url_date(url: str) -> dict[str, str]:
    parsed = urlparse(str(url or ""))
    text = f"{parsed.path} {parsed.query}"
    match = URL_DATE_RE.search(text)
    if match:
        return _build_result(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            match.group(0).strip("/_-"),
            "Orta",
            "url_date",
        )
    return empty_result(date_source="missing")


def best_item_date(
    visible_text: str = "",
    url: str = "",
    listing_text: str = "",
    metadata_text: str = "",
    inferred_text: str = "",
) -> dict[str, str]:
    checks = [
        (visible_text, "detail_page_visible_date", "Yüksek"),
        (url, "url_date", "Orta"),
        (listing_text, "listing_page_nearby_date", "Orta"),
        (metadata_text, "metadata_date", "Orta"),
        (inferred_text, "inferred_from_text", "Düşük"),
    ]
    for text, source, confidence in checks:
        result = parse_url_date(text) if source == "url_date" else parse_turkish_date(text, source, confidence)
        if result["normalized_date"]:
            return result
    return empty_result()


def extract_date_semantics(
    visible_text: str = "",
    url: str = "",
    listing_text: str = "",
    metadata_text: str = "",
    inferred_text: str = "",
    source_type: str = "",
) -> dict[str, str]:
    combined = "\n".join(str(part or "") for part in [visible_text, listing_text, metadata_text, inferred_text])
    raw_context = combined[:6000]
    source_blob = f"{source_type} {url} {listing_text} {visible_text}"
    is_campaign = bool(CAMPAIGN_CONTEXT_RE.search(source_blob) or CAMPAIGN_CONTEXT_RE.search(raw_context))
    is_press = bool(PRESS_CONTEXT_RE.search(source_blob))

    result = empty_semantic_result()
    ranges = parse_turkish_date_ranges(raw_context)
    if ranges and is_campaign:
        selected = ranges[0]
        result["campaign_start_date"] = selected["start_date"]
        result["campaign_end_date"] = selected["end_date"]
        result["raw_date_text"] = selected["raw_date_text"]
        result["date_confidence"] = "Yüksek"

    single_checks = [
        (visible_text, "detail_page_visible_date", "Yüksek"),
        (listing_text, "listing_page_nearby_date", "Orta"),
        (url, "url_date", "Orta"),
        (metadata_text, "metadata_date", "Orta"),
        (inferred_text, "inferred_from_text", "Düşük"),
    ]
    single = empty_result()
    for text, source, confidence in single_checks:
        parsed = parse_url_date(text) if source == "url_date" else parse_turkish_date(text, source, confidence)
        if parsed.get("normalized_date"):
            single = parsed
            break

    if single.get("normalized_date"):
        raw_single = single.get("raw_date_text", "")
        single_used = True
        if is_campaign and has_campaign_end_context(raw_context, raw_single) and not result["campaign_end_date"]:
            result["campaign_end_date"] = single["normalized_date"]
        elif is_campaign and has_campaign_start_context(raw_context, raw_single) and not result["campaign_start_date"] and not result["campaign_end_date"]:
            result["campaign_start_date"] = single["normalized_date"]
        elif is_campaign and not result["campaign_start_date"] and not result["campaign_end_date"]:
            result["campaign_start_date"] = single["normalized_date"]
        elif is_campaign and (result["campaign_start_date"] or result["campaign_end_date"]):
            single_used = False
        elif is_press:
            result["publication_date"] = single["normalized_date"]
        else:
            result["publication_date"] = single["normalized_date"]
        if single_used:
            result["raw_date_text"] = result["raw_date_text"] or raw_single
            result["date_confidence"] = single.get("date_confidence", "Orta")

    if result["publication_date"]:
        result["event_date_type"] = "Yayın Tarihi"
        result["recency_basis_date"] = result["publication_date"]
        result["recency_basis_reason"] = "Yayın tarihi bulundu; recency için kullanıldı."
        result["date_source"] = "publication_date"
    elif result["announcement_date"]:
        result["event_date_type"] = "Duyuru Tarihi"
        result["recency_basis_date"] = result["announcement_date"]
        result["recency_basis_reason"] = "Duyuru/basın tarihi bulundu; recency için kullanıldı."
        result["date_source"] = "announcement_date"
    elif result["campaign_start_date"]:
        result["event_date_type"] = "Kampanya Başlangıç Tarihi"
        result["recency_basis_date"] = result["campaign_start_date"]
        result["recency_basis_reason"] = "Kampanya başlangıç tarihi bulundu; recency için kullanıldı."
        result["date_source"] = "campaign_start_date"
    elif result["campaign_end_date"]:
        result["event_date_type"] = "Kampanya Bitiş Tarihi"
        result["recency_basis_date"] = result["campaign_end_date"]
        result["recency_basis_reason"] = "Sadece kampanya bitiş tarihi bulundu; varsayılan recency kapısından geçmez."
        result["date_source"] = "campaign_end_date"

    result["normalized_date"] = result["recency_basis_date"]
    return result
