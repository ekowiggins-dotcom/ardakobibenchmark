from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils.browser_collector import (
    ACCESS_DENIED_RE,
    HEADERS,
    BrowserCollector,
    BrowserPage,
    canonical_from_html,
    canonicalize_mastercard_url,
    clean,
    clean_html_text,
    date_from_html,
    detect_mastercard_page_type,
    is_item_level_mastercard_url,
    is_official_mastercard_domain,
    is_post_cutoff,
    mastercard_url_key,
    parse_mastercard_date,
    title_from_html,
)
from pipeline.validate_mastercard_sources import classify_mastercard_item
from utils.mastercard_blocked_mode import high_precision_historical_taxonomy


START_DATE = "2026-05-01"
NOISE_RE = re.compile(
    r"(priceless|sports|football|sponsorship|music|festival|celebrity|tourism|travel|destination|culinary|"
    r"executive appointment|chief financial officer|employer|workplace|csr|donation|art|entertainment|lifestyle)",
    re.I,
)
SHORT_FACT_RE = re.compile(
    r"(launch|launched|introduc|partner|partnership|pilot|settlement|stablecoin|agent pay|cross-border|commercial card|"
    r"business credit card|small business|token|credential|payment|checkout|merchant|acquiring)",
    re.I,
)


@dataclass(frozen=True)
class PressIndexItem:
    title: str
    item_url: str
    visible_date: str
    month_section: str
    source_index: str
    card_position: int


@dataclass(frozen=True)
class PressArticle:
    source_url: str
    final_url: str
    canonical_url: str
    title: str
    subtitle: str
    publication_date: str
    date_raw_text: str
    date_source: str
    date_confidence: str
    location: str
    article_body: str
    body_chars: int
    named_partners: str
    named_products: str
    named_banks: str
    source_region: str
    structured_metadata_found: bool
    page_type: str
    access_status: str
    error_message: str = ""


def fetch_static(url: str) -> BrowserPage:
    try:
        response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        html = response.text
        body = clean_html_text(html)
        title = title_from_html(html, "")
        page_type = detect_mastercard_page_type(response.url, html, body, title)
        return BrowserPage(
            url=url,
            final_url=response.url,
            title=title,
            html=html,
            body_text=body,
            page_type=page_type,
            engine="static_requests",
            error="" if response.ok else f"HTTP {response.status_code}",
        )
    except Exception as exc:
        return BrowserPage(url=url, final_url=url, title="", html="", body_text="", page_type="empty_shell", engine="static_requests", error=str(exc)[:300])


def fetch_page(url: str, mode: str = "auto", collector: BrowserCollector | None = None) -> BrowserPage:
    if mode == "browser":
        if collector is None:
            with BrowserCollector() as owned:
                return owned.get_page(url)
        return collector.get_page(url)
    static_page = fetch_static(url)
    if mode == "static":
        return static_page
    if static_page.page_type in {"access_denied", "empty_shell"} and collector is not None:
        return collector.get_page(url)
    return static_page


def classify_source_access(page: BrowserPage, item_links_found: int, dated_links_found: int, post_cutoff_links_found: int) -> dict[str, str]:
    official = is_official_mastercard_domain(page.final_url or page.url)
    accessible = page.page_type != "access_denied" and bool(page.html or page.body_text) and ACCESS_DENIED_RE.search(page.body_text or page.html or "") is None
    structurally_valid = accessible and (item_links_found > 0 or page.page_type == "article_page")
    if post_cutoff_links_found:
        freshness = "current"
    elif dated_links_found:
        freshness = "stale_or_pre_cutoff"
    elif accessible:
        freshness = "unknown"
    else:
        freshness = "unknown"
    return {
        "official_source_valid": str(official),
        "collector_accessible": str(accessible),
        "extraction_structurally_valid": str(structurally_valid),
        "currently_fresh": str(bool(post_cutoff_links_found)),
        "claude_ready": "False",
        "current_or_stale": freshness,
    }


def extract_mastercard_press_index(html: str, source_index: str) -> list[PressIndexItem]:
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[PressIndexItem] = []
    for position, node in enumerate(soup.select(".accordion-item__separator"), start=1):
        date_node = node.select_one(".accordion-item__separator-eyebrow")
        title_node = node.select_one(".accordion-item__separator-heading a[href]")
        if not title_node:
            continue
        title = clean(title_node.get_text(" ", strip=True))
        href = title_node.get("href", "")
        item_url = canonicalize_mastercard_url(urljoin(source_index, href))
        visible_date_raw = clean(date_node.get_text(" ", strip=True)) if date_node else ""
        normalized_date, _, _, _ = parse_mastercard_date(visible_date_raw)
        month_section = ""
        if normalized_date:
            month_section = normalized_date[:7]
        elif visible_date_raw:
            month_section = visible_date_raw
        if not title or not is_official_mastercard_domain(item_url):
            continue
        items.append(
            PressIndexItem(
                title=title,
                item_url=item_url,
                visible_date=normalized_date,
                month_section=month_section,
                source_index=source_index,
                card_position=position,
            )
        )
    return items


def extract_jsonld(html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    records = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.get_text(" ", strip=True) or "{}")
        except Exception:
            continue
        if isinstance(data, list):
            records.extend([item for item in data if isinstance(item, dict)])
        elif isinstance(data, dict):
            records.append(data)
    return records


def subtitle_from_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for selector in ["h2", ".dek", ".subtitle", "meta[property='og:description']", "meta[name='description']"]:
        node = soup.select_one(selector)
        if not node:
            continue
        value = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
        if clean(value):
            return clean(value)
    return ""


def location_from_text(text: str) -> str:
    match = re.search(r"\b(Purchase, NY|New York|London|Miami|Dubai|Toronto|Brussels|Amsterdam|Seattle|Washington)\b", text or "", re.I)
    return match.group(0) if match else ""


def named_entities(title: str, body: str) -> tuple[str, str, str]:
    blob = f"{title} {body}"
    partners = []
    for pattern in [
        r"Agent Pay for Machines",
        r"Amazon Business",
        r"Amazon",
        r"MoonPay",
        r"OnePay",
        r"Synchrony",
        r"PayPal",
        r"Deutsche Bank",
        r"Network International Jordan",
        r"TIPS",
        r"Corpay",
    ]:
        if re.search(pattern, blob, re.I):
            partners.append(pattern.replace("\\", ""))
    products = []
    for pattern in [
        r"Agent Pay",
        r"Agent Pay for Machines",
        r"stablecoin",
        r"Mastercard Move",
        r"One Credential",
        r"Click to Pay",
        r"Merchant Cloud",
        r"commercial card",
        r"business credit card",
        r"virtual card",
        r"TIPS",
    ]:
        if re.search(pattern, blob, re.I):
            products.append(pattern.replace("\\", ""))
    banks = []
    for pattern in [r"Deutsche Bank", r"CIBC", r"BMO", r"Santander", r"Garanti BBVA", r"Akbank"]:
        if re.search(pattern, blob, re.I):
            banks.append(pattern.replace("\\", ""))
    return "; ".join(sorted(set(partners))), "; ".join(sorted(set(products))), "; ".join(sorted(set(banks)))


def extract_mastercard_press_article(url: str, mode: str = "auto", listing_title: str = "", listing_date: str = "", collector: BrowserCollector | None = None) -> PressArticle:
    page = fetch_page(url, mode=mode, collector=collector)
    body = clean_html_text(page.html) or clean(page.body_text)
    title = title_from_html(page.html, listing_title or page.title)
    subtitle = subtitle_from_html(page.html)
    canonical_url = canonical_from_html(page.html, page.final_url)
    publication_date, raw, source, confidence = date_from_html(page.html, body)
    if not publication_date and listing_date and page.page_type == "article_page":
        publication_date, raw, source, confidence = listing_date, listing_date, "listing_date_confirmed_by_article_structure", "Orta"
    partners, products, banks = named_entities(title, body)
    return PressArticle(
        source_url=url,
        final_url=page.final_url,
        canonical_url=canonical_url,
        title=title,
        subtitle=subtitle,
        publication_date=publication_date,
        date_raw_text=raw,
        date_source=source,
        date_confidence=confidence,
        location=location_from_text(body[:1000]),
        article_body=body,
        body_chars=len(body),
        named_partners=partners,
        named_products=products,
        named_banks=banks,
        source_region="US/Global" if "/us/en/" in page.final_url or "newsroom.mastercard.com" in page.final_url else "",
        structured_metadata_found=bool(extract_jsonld(page.html)),
        page_type=page.page_type,
        access_status="accessible" if page.page_type != "access_denied" and bool(body) else "access_denied" if page.page_type == "access_denied" else "unavailable",
        error_message=page.error,
    )


def article_quality_gate(article: PressArticle, start_date: str = START_DATE) -> tuple[bool, str]:
    if not is_official_mastercard_domain(article.final_url) or not is_official_mastercard_domain(article.canonical_url):
        return False, "not_official_mastercard_domain"
    if article.access_status != "accessible" or article.page_type == "access_denied":
        return False, "access_denied"
    if not is_item_level_mastercard_url(article.canonical_url):
        return False, "not_item_level_url"
    if article.page_type != "article_page":
        return False, f"page_type_{article.page_type}"
    if not article.title:
        return False, "missing_article_title"
    if not article.publication_date:
        return False, "missing_publication_date"
    if not is_post_cutoff(article.publication_date, start_date):
        return False, "pre_cutoff"
    if NOISE_RE.search(f"{article.title} {article.article_body[:1000]}"):
        return False, "brand_lifestyle_or_corporate_noise"
    if article.body_chars < 500 and not SHORT_FACT_RE.search(f"{article.title} {article.article_body}"):
        return False, "body_too_short_without_substantive_facts"
    cls = classify_mastercard_item(article.title, article.canonical_url, article.article_body, article.publication_date)
    if cls.get("network_signal_type") == "Kapsam Dışı":
        return False, "no_mastercard_strategic_relevance_signal"
    return True, ""


def item_row_from_article(article: PressArticle, discovered_from: str, listing_title: str = "", listing_date: str = "", start_date: str = START_DATE) -> dict[str, str]:
    passed, reason = article_quality_gate(article, start_date)
    cls = classify_mastercard_item(article.title or listing_title, article.canonical_url, article.article_body, article.publication_date)
    if not passed:
        cls = {
            **cls,
            "strategic_priority_score": 0 if reason in {"access_denied", "not_item_level_url", "missing_publication_date", "pre_cutoff"} else cls.get("strategic_priority_score", 0),
        }
    taxonomy = {
        "taxonomy_status": "Verified" if passed else "Not Applicable",
        "taxonomy_confidence": "Yüksek" if passed else "Düşük",
        "taxonomy_method": "detail_rule" if passed else "none",
    }
    if not passed:
        taxonomy = high_precision_historical_taxonomy(
            article.title or listing_title,
            article.canonical_url,
            article.article_body,
            article.named_products,
        )
        cls = {
            **cls,
            "network_signal_type": taxonomy["network_signal_type"],
            "network_layer": taxonomy["network_layer"],
            "deployment_scope": taxonomy["deployment_scope"],
        }
    return {
        "discovered_from": discovered_from,
        "listing_title": listing_title,
        "listing_date": listing_date,
        "item_url": article.source_url,
        "final_url": article.final_url,
        "canonical_url": article.canonical_url,
        "article_title": article.title,
        "publication_date": article.publication_date,
        "date_source": article.date_source,
        "date_confidence": article.date_confidence,
        "body_chars": str(article.body_chars),
        "named_partners": article.named_partners,
        "named_products": article.named_products,
        "network_signal_type": str(cls.get("network_signal_type", "")),
        "network_layer": str(cls.get("network_layer", "")),
        "deployment_scope": str(cls.get("deployment_scope", "")),
        "content_role": str(cls.get("content_role", "")) if passed else ("Tarihsel Bağlam" if reason == "pre_cutoff" else "Kapsam Dışı"),
        "strategic_priority_score": str(cls.get("strategic_priority_score", "0") if passed else "0"),
        "item_level_verified": str(passed or (article.page_type == "article_page" and is_item_level_mastercard_url(article.canonical_url))),
        "publication_date_verified": str(bool(article.publication_date and article.date_source != "dateModified")),
        "body_verified": str(article.body_chars >= 500 or bool(SHORT_FACT_RE.search(f"{article.title} {article.article_body}"))),
        "recent_item_eligible": str(passed),
        "claude_eligible": "False",
        "duplicate_status": "canonical_unique",
        "rejection_reason": reason,
        "taxonomy_status": taxonomy["taxonomy_status"],
        "taxonomy_confidence": taxonomy["taxonomy_confidence"],
        "taxonomy_method": taxonomy["taxonomy_method"],
        "dataset_role": "current_candidate" if passed else "historical_resolution",
        "production_recent_eligible": str(passed),
    }


def dedupe_item_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    dedup: dict[str, dict[str, str]] = {}
    discovered: dict[str, set[str]] = {}
    for row in rows:
        key = mastercard_url_key(row.get("canonical_url") or row.get("final_url") or row.get("item_url", ""))
        discovered.setdefault(key, set()).add(row.get("discovered_from", ""))
        existing = dedup.get(key)
        if existing is None:
            dedup[key] = dict(row)
            continue
        if row.get("recent_item_eligible") == "True" and existing.get("recent_item_eligible") != "True":
            dedup[key] = dict(row)
        elif int(row.get("body_chars", "0") or 0) > int(existing.get("body_chars", "0") or 0):
            dedup[key] = dict(row)
    out = []
    for key, row in dedup.items():
        sources = sorted(value for value in discovered.get(key, set()) if value)
        if len(sources) > 1:
            row["duplicate_status"] = "canonical_collapsed_legacy_modern"
            row["discovered_from"] = "; ".join(sources)
        out.append(row)
    return sorted(out, key=lambda row: (row.get("publication_date", ""), row.get("article_title", "")), reverse=True)
