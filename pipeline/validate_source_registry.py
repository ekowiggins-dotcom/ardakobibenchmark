from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
REGISTRY_PATH = DATA_DIR / "source_registry.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

WEEKLY_SOURCE_TYPES = {
    "Resmi Haber Sayfası",
    "Official Press Release Page",
    "Official Campaign Page",
    "Regulator",
    "Industry Association",
    "News Site",
    "Fintech News",
    "Business News",
    "Resmi Basın Bülteni Sayfası",
    "Resmi Kampanya Sayfası",
    "Regülatör",
    "Sektör Birliği",
    "Haber Sitesi",
    "Fintech Haberi",
    "İş/Ekonomi Haberi",
}

BLOCKED_RE = re.compile(
    r"(captcha|access denied|forbidden|request blocked|temporarily blocked|cloudflare|güvenlik doğrulaması)",
    re.I,
)
USEFUL_LINK_RE = re.compile(
    r"(kampanya|duyuru|haber|basın|bulten|bülten|kobi|ticari|pos|üye|uye|kredi|tahsilat|ödeme|odeme)",
    re.I,
)


@dataclass
class ValidationResult:
    source_id: str
    source_name: str
    url: str
    final_url: str
    source_type: str
    extraction_mode: str
    active: str
    collection_method: str
    coverage_scope: str
    coverage_priority: str
    mvp_active: str
    source_validation_status: str
    collector_capability: str
    status_code: str
    content_length: int
    total_links: int
    useful_links: int
    turkish_ok: bool
    suspected_blocked: bool
    redirected: bool
    eligible_weekly: bool
    category: str
    error_message: str = ""


def truthy(value) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "evet"}


def normalize(value) -> str:
    return str(value or "").strip()


def source_is_eligible(row: pd.Series) -> bool:
    return (
        truthy(row.get("active", ""))
        and normalize(row.get("collection_method", "")).casefold() == "static_scrape"
        and normalize(row.get("extraction_mode", "")).casefold() in {"weekly_development", "both"}
        and normalize(row.get("source_type", "")) in WEEKLY_SOURCE_TYPES
    )


def has_turkish_chars(text: str) -> bool:
    return any(ch in text for ch in "çğıöşüÇĞİÖŞÜ")


def same_site(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url).netloc.casefold().removeprefix("www.")
    target = urlparse(candidate_url).netloc.casefold().removeprefix("www.")
    return not base or not target or target == base or target.endswith(f".{base}")


def validate_row(row: pd.Series) -> ValidationResult:
    url = normalize(row.get("url", ""))
    eligible = source_is_eligible(row)
    try:
        response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        html = response.text or ""
        soup = BeautifulSoup(html, "html.parser")
        total_links = 0
        useful_links = 0
        for anchor in soup.find_all("a"):
            href = normalize(anchor.get("href") or "")
            text = normalize(anchor.get_text(" ", strip=True))
            if not href:
                continue
            absolute = urljoin(response.url, href)
            if not same_site(response.url, absolute):
                continue
            total_links += 1
            if USEFUL_LINK_RE.search(f"{text} {absolute}"):
                useful_links += 1
        text_sample = soup.get_text(" ", strip=True)[:5000]
        blocked = response.status_code in {401, 403, 429} or bool(BLOCKED_RE.search(html[:5000]))
        if blocked:
            category = "blocked"
        elif response.status_code >= 400:
            category = "failed"
        elif eligible and useful_links > 0:
            category = "weekly-development eligible"
        elif eligible:
            category = "static-only"
        else:
            category = "not eligible"
        return ValidationResult(
            source_id=normalize(row.get("source_id", "")),
            source_name=normalize(row.get("source_name", "")),
            url=url,
            final_url=response.url,
            source_type=normalize(row.get("source_type", "")),
            extraction_mode=normalize(row.get("extraction_mode", "")),
            active=normalize(row.get("active", "")),
            collection_method=normalize(row.get("collection_method", "")),
            coverage_scope=normalize(row.get("coverage_scope", "")),
            coverage_priority=normalize(row.get("coverage_priority", "")),
            mvp_active=normalize(row.get("mvp_active", "")),
            source_validation_status=normalize(row.get("source_validation_status", "")),
            collector_capability=normalize(row.get("collector_capability", "")),
            status_code=str(response.status_code),
            content_length=len(response.content),
            total_links=total_links,
            useful_links=useful_links,
            turkish_ok=has_turkish_chars(html) or has_turkish_chars(text_sample),
            suspected_blocked=blocked,
            redirected=response.url.rstrip("/") != url.rstrip("/"),
            eligible_weekly=eligible,
            category=category,
        )
    except Exception as exc:
        return ValidationResult(
            source_id=normalize(row.get("source_id", "")),
            source_name=normalize(row.get("source_name", "")),
            url=url,
            final_url="",
            source_type=normalize(row.get("source_type", "")),
            extraction_mode=normalize(row.get("extraction_mode", "")),
            active=normalize(row.get("active", "")),
            collection_method=normalize(row.get("collection_method", "")),
            coverage_scope=normalize(row.get("coverage_scope", "")),
            coverage_priority=normalize(row.get("coverage_priority", "")),
            mvp_active=normalize(row.get("mvp_active", "")),
            source_validation_status=normalize(row.get("source_validation_status", "")),
            collector_capability=normalize(row.get("collector_capability", "")),
            status_code="",
            content_length=0,
            total_links=0,
            useful_links=0,
            turkish_ok=False,
            suspected_blocked=False,
            redirected=False,
            eligible_weekly=eligible,
            category="failed",
            error_message=str(exc)[:300],
        )


def filter_registry(registry: pd.DataFrame, institution: str | None) -> pd.DataFrame:
    if not institution:
        return registry.copy()
    token = institution.strip().casefold()
    return registry[
        registry["institution_name"].astype(str).str.casefold().str.contains(token, regex=False)
        | registry["institution_id"].astype(str).str.casefold().str.contains(token, regex=False)
        | registry["source_name"].astype(str).str.casefold().str.contains(token, regex=False)
    ].copy()


def print_results(results: list[ValidationResult]) -> None:
    buckets = {
        "valid sources": [item for item in results if item.status_code == "200" and not item.suspected_blocked],
        "failed sources": [item for item in results if item.category == "failed"],
        "redirected sources": [item for item in results if item.redirected],
        "blocked sources": [item for item in results if item.suspected_blocked],
        "static-only sources": [item for item in results if item.category == "static-only"],
        "weekly-development eligible sources": [item for item in results if item.category == "weekly-development eligible"],
    }
    print(f"Sources checked: {len(results)}")
    for label, rows in buckets.items():
        print(f"{label}: {len(rows)}")
    print("")
    for item in results:
        print(
            "source | "
            f"{item.source_id} | {item.source_name} | status={item.status_code or 'error'} | "
            f"length={item.content_length} | links={item.total_links} | useful_links={item.useful_links} | "
            f"turkish_ok={item.turkish_ok} | redirected={item.redirected} | blocked={item.suspected_blocked} | "
            f"eligible={item.eligible_weekly} | category={item.category} | "
            f"coverage={item.coverage_scope or '-'} | priority={item.coverage_priority or '-'} | "
            f"mvp_active={item.mvp_active or '-'} | validation={item.source_validation_status or '-'} | "
            f"collector={item.collector_capability or item.collection_method or '-'}"
        )
        if item.redirected:
            print(f"  final_url: {item.final_url}")
        if item.error_message:
            print(f"  error: {item.error_message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate source_registry.csv URLs and recent-development eligibility.")
    parser.add_argument("--institution", default=None, help='Institution name/id filter, e.g. "QNB Finansbank".')
    args = parser.parse_args()

    registry = pd.read_csv(REGISTRY_PATH, encoding="utf-8-sig")
    scoped = filter_registry(registry, args.institution)
    results = [validate_row(row) for _, row in scoped.iterrows()]
    print_results(results)


if __name__ == "__main__":
    main()
