from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

try:
    import trafilatura
except ImportError:  # Optional dependency.
    trafilatura = None


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RAW_HTML_DIR = DATA_DIR / "raw_documents" / "raw_html"
CLEANED_TEXT_DIR = DATA_DIR / "raw_documents" / "cleaned_text"
REGISTRY_PATH = DATA_DIR / "source_registry.csv"
METADATA_PATH = DATA_DIR / "raw_documents_metadata.csv"
SSL_VERIFY_FALLBACK_HOSTS = {"www.bddk.org.tr"}

METADATA_COLUMNS = [
    "document_id",
    "source_id",
    "tier",
    "institution_id",
    "institution_name",
    "source_name",
    "url",
    "title",
    "fetched_at",
    "content_hash",
    "cleaned_text_path",
    "raw_html_path",
    "status_code",
    "status",
    "change_status",
    "error_message",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def read_metadata() -> pd.DataFrame:
    if METADATA_PATH.exists():
        metadata = pd.read_csv(METADATA_PATH, encoding="utf-8-sig")
        for column in METADATA_COLUMNS:
            if column not in metadata.columns:
                metadata[column] = ""
        return metadata.reindex(columns=METADATA_COLUMNS)
    return pd.DataFrame(columns=METADATA_COLUMNS)


def is_active(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def normalized_method(value) -> str:
    return str(value).strip().lower()


def ssl_fallback_allowed(url: str) -> bool:
    try:
        from urllib.parse import urlparse

        return urlparse(url).netloc.casefold() in SSL_VERIFY_FALLBACK_HOSTS
    except Exception:
        return False


def clean_with_bs4(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "svg", "header", "nav", "footer"]):
        tag.decompose()

    def extract_best_text(candidate_soup: BeautifulSoup) -> str:
        candidates = []
        for selector in [
            "main",
            "article",
            "[role='main']",
            ".main-content",
            ".content",
            ".page-content",
            ".container",
            "#content",
            "#main",
        ]:
            candidates.extend(candidate_soup.select(selector))

        if not candidates:
            candidates = [candidate_soup.body or candidate_soup]

        best = max(candidates, key=lambda node: len(node.get_text(" ", strip=True)))
        text = best.get_text("\n", strip=True)
        lines = []
        seen = set()
        for line in text.splitlines():
            clean_line = re.sub(r"\s+", " ", line).strip()
            if not clean_line:
                continue
            if clean_line in seen:
                continue
            seen.add(clean_line)
            lines.append(clean_line)
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()

    structural_text = extract_best_text(soup)
    denoised_soup = BeautifulSoup(str(soup), "html.parser")

    noisy_patterns = re.compile(
        r"(cookie|çerez|cerez|gdpr|kvkk|modal|popup|overlay|"
        r"breadcrumb|breadcrumbs|navigation|navbar|menu|menü|"
        r"footer|header|search|arama|social|sosyal|language|dil)",
        re.IGNORECASE,
    )
    for tag in list(denoised_soup.find_all(True)):
        if not getattr(tag, "name", None) or getattr(tag, "attrs", None) is None:
            continue
        tag_id = tag.attrs.get("id", "")
        tag_class = tag.attrs.get("class", "")
        tag_role = tag.attrs.get("role", "")
        tag_label = tag.attrs.get("aria-label", "")
        attrs = " ".join(
            str(value)
            for value in [
                tag_id,
                " ".join(tag_class) if isinstance(tag_class, list) else tag_class,
                tag_role,
                tag_label,
            ]
            if value
        )
        if noisy_patterns.search(attrs):
            tag.decompose()

    denoised_text = extract_best_text(denoised_soup)
    if len(denoised_text) >= 1000 or len(denoised_text) >= len(structural_text) * 0.35:
        cleaned = denoised_text
    else:
        cleaned = structural_text

    if title and not cleaned.startswith(title):
        cleaned = f"{title}\n{cleaned}"
    return title, cleaned


def extract_clean_text(html: str) -> tuple[str, str]:
    title, bs4_text = clean_with_bs4(html)
    if trafilatura is not None:
        extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
        if extracted and len(extracted.strip()) > 100:
            return title, extracted.strip()
    return title, bs4_text


def document_id_for(source_id: str, fetched_at: datetime) -> str:
    stamp = fetched_at.strftime("%Y%m%d%H%M%S")
    return f"DOC-{source_id}-{stamp}"


def collect_row(row: pd.Series) -> dict[str, str]:
    fetched_at = now_utc()
    document_id = document_id_for(row["source_id"], fetched_at)
    raw_path = RAW_HTML_DIR / f"{document_id}.html"
    cleaned_path = CLEANED_TEXT_DIR / f"{document_id}.txt"

    base = {
        "document_id": document_id,
        "source_id": row["source_id"],
        "tier": row["tier"],
        "institution_id": row["institution_id"],
        "institution_name": row["institution_name"],
        "source_name": row["source_name"],
        "url": row["url"],
        "title": "",
        "fetched_at": fetched_at.isoformat(),
        "content_hash": "",
        "cleaned_text_path": str(cleaned_path.relative_to(ROOT_DIR)),
        "raw_html_path": str(raw_path.relative_to(ROOT_DIR)),
        "status_code": "",
        "status": "error",
        "change_status": "",
        "error_message": "",
    }

    logging.info("Fetching %s | %s | %s", row["source_id"], row["source_name"], row["url"])
    response = None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        last_exc = None
        for attempt in range(1, 4):
            try:
                response = requests.get(row["url"], timeout=20, headers=headers)
                break
            except requests.exceptions.SSLError as exc:
                last_exc = exc
                if ssl_fallback_allowed(str(row["url"])):
                    logging.warning(
                        "SSL verification failed for %s; retrying with source-specific fallback.",
                        row["source_id"],
                    )
                    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
                    response = requests.get(row["url"], timeout=20, headers=headers, verify=False)
                    break
                logging.warning("Fetch attempt %s failed for %s: %s", attempt, row["source_id"], exc)
                if attempt < 3:
                    time.sleep(1.5 * attempt)
            except requests.RequestException as exc:
                last_exc = exc
                logging.warning("Fetch attempt %s failed for %s: %s", attempt, row["source_id"], exc)
                if attempt < 3:
                    time.sleep(1.5 * attempt)
        if response is None and last_exc is not None:
            raise last_exc
        base["status_code"] = response.status_code
        response.raise_for_status()
        html = response.text
        title, cleaned_text = extract_clean_text(html)
        content_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()

        raw_path.write_text(html, encoding="utf-8", errors="ignore")
        cleaned_path.write_text(cleaned_text, encoding="utf-8")

        base.update(
            {
                "title": title,
                "content_hash": content_hash,
                "status": "fetched",
                "error_message": "",
            }
        )
        logging.info("Collected %s from %s", row["source_id"], row["url"])
    except Exception as exc:  # Websites can block or change behavior.
        if response is not None:
            base["status_code"] = response.status_code
        base["error_message"] = str(exc)[:500]
        logging.warning("Failed %s: %s", row["source_id"], exc)

    return base


def build_eligible_sources(registry: pd.DataFrame) -> pd.DataFrame:
    registry = registry.copy()
    registry["_active_flag"] = registry["active"].apply(is_active)
    registry["_method_normalized"] = registry["collection_method"].apply(normalized_method)
    return registry[
        registry["_active_flag"] & registry["_method_normalized"].eq("static_scrape")
    ].drop(columns=["_active_flag", "_method_normalized"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect approved static source pages.")
    parser.add_argument("--institution", default=None, help="Fetch only sources for this institution name or id.")
    parser.add_argument("--source-id", default=None, help="Fetch only a specific source_id.")
    parser.add_argument("--limit", type=int, default=None, help="Fetch only the first N eligible sources.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print eligible sources without fetching or writing metadata.",
    )
    args = parser.parse_args()

    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    CLEANED_TEXT_DIR.mkdir(parents=True, exist_ok=True)

    registry = pd.read_csv(REGISTRY_PATH, encoding="utf-8-sig")
    total_sources = len(registry)
    active_sources = registry["active"].apply(is_active).sum()
    static_sources = registry["collection_method"].apply(normalized_method).eq("static_scrape").sum()
    eligible = build_eligible_sources(registry)

    logging.info("Total sources loaded: %s", total_sources)
    logging.info("Active sources: %s", active_sources)
    logging.info("collection_method == static_scrape olan kaynak sayısı: %s", static_sources)
    logging.info("Eligible active static_scrape sources: %s", len(eligible))

    if args.institution:
        token = args.institution.strip().casefold()
        eligible = eligible[
            eligible["institution_name"].astype(str).str.casefold().eq(token)
            | eligible["institution_id"].astype(str).str.casefold().eq(token)
        ]
        logging.info("--institution %s uygulanıyor. Kontrol edilecek kaynak sayısı: %s", args.institution, len(eligible))

    if args.source_id:
        eligible = eligible[eligible["source_id"].astype(str).eq(args.source_id)]
        logging.info("--source-id %s uygulanıyor. Kontrol edilecek kaynak sayısı: %s", args.source_id, len(eligible))

    if args.limit is not None:
        eligible = eligible.head(args.limit)
        logging.info("--limit %s uygulanıyor. Kontrol edilecek kaynak sayısı: %s", args.limit, len(eligible))

    if args.dry_run:
        logging.info("Dry run mode: no pages will be fetched and metadata will not be written.")
        for _, row in eligible.iterrows():
            logging.info("Would fetch %s | %s | %s", row["source_id"], row["source_name"], row["url"])
        return

    existing = read_metadata()
    new_rows = [collect_row(row) for _, row in eligible.iterrows()]
    updated = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    updated = updated.reindex(columns=METADATA_COLUMNS)
    updated.to_csv(METADATA_PATH, index=False, encoding="utf-8-sig")
    logging.info("Wrote %s metadata rows", len(updated))
    logging.info("Successfully fetched this run: %s", sum(row["status"] == "fetched" for row in new_rows))
    logging.info("Failed this run: %s", sum(row["status"] == "error" for row in new_rows))


if __name__ == "__main__":
    main()
