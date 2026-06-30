from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


START_DATE = "2026-05-01"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

DATE_RE = re.compile(
    r"(?P<month_first>\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}\b)|"
    r"(?P<day_first>\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}\b)|"
    r"(?P<iso>\b20\d{2}-\d{2}-\d{2}\b)|"
    r"(?P<month_only>\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}\b)",
    re.I,
)
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

ACCESS_DENIED_RE = re.compile(r"(access denied|permission to access|forbidden|reference #|errors\.edgesuite)", re.I)
NOISE_RE = re.compile(
    r"(priceless|sports|football|sponsorship|music|festival|celebrity|tourism|destination|culinary|"
    r"employer|workplace|csr|donation|art|entertainment|lifestyle)",
    re.I,
)
STRATEGIC_RE = re.compile(
    r"(akbank|commercial|card|virtual card|merchant cloud|merchant|acquiring|acceptance|click to pay|gateway|"
    r"token|credential|authentication|identity|fraud|cyber|security|agent pay|agentic|ai agent|"
    r"b2b|supplier|payable|receivable|sme|small business|open finance|data|analytics|cross-border|stablecoin|multi-rail)",
    re.I,
)
SHORT_ANNOUNCEMENT_FACT_RE = re.compile(
    r"(launch|launched|introduc|deploy|partner|partnership|pilot|live|rollout|click to pay|merchant cloud|agent pay|token|credential)",
    re.I,
)
NAV_RE = re.compile(r"(nav|menu|footer|header|breadcrumb|cookie|social|sosyal|mega|offcanvas|skip)", re.I)


@dataclass
class BrowserPage:
    url: str
    final_url: str
    title: str
    html: str
    body_text: str
    page_type: str
    engine: str
    error: str = ""


@dataclass
class ArticleGateResult:
    passed: bool
    rejection_reason: str
    publication_date: str
    date_raw_text: str
    date_source: str
    date_confidence: str
    body_chars: int
    title: str
    canonical_url: str


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonicalize_mastercard_url(url: str) -> str:
    parsed = urlparse(clean(url))
    keep = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        key_l = key.lower()
        if key_l.startswith(("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")):
            continue
        keep.append((key, value))
    path = re.sub(r"/+$", "/", parsed.path)
    return urlunparse((parsed.scheme.lower() or "https", parsed.netloc.lower(), path, "", urlencode(keep), ""))


def mastercard_url_key(url: str) -> str:
    parsed = urlparse(canonicalize_mastercard_url(url))
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.netloc.casefold().removeprefix('www.')}{parsed.path.rstrip('/')}{query}".casefold()


def is_official_mastercard_domain(url: str) -> bool:
    host = urlparse(clean(url)).netloc.casefold().removeprefix("www.")
    return host == "mastercard.com" or host.endswith(".mastercard.com") or host == "mastercard.com.tr" or host.endswith(".mastercard.com.tr") or host == "mastercardservices.com" or host.endswith(".mastercardservices.com")


def is_search_page_url(url: str) -> bool:
    parsed = urlparse(clean(url))
    query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    return "q" in query_keys or "/search" in parsed.path.casefold()


def is_listing_root_url(url: str) -> bool:
    parsed = urlparse(canonicalize_mastercard_url(url))
    path = parsed.path.rstrip("/").casefold()
    listing_roots = {
        "/news",
        "/news/press",
        "/news/perspectives",
        "/us/en/news-and-trends/press.html",
        "/news/eemea/en/newsroom",
        "/news/eemea/en/newsroom/press-releases",
        "/news/eemea/en/newsroom/news-briefs",
        "/news/eemea/en/perspectives",
    }
    return path in listing_roots


def is_generic_product_root_url(url: str) -> bool:
    parsed = urlparse(canonicalize_mastercard_url(url))
    path = parsed.path.casefold()
    if is_search_page_url(url):
        return False
    if re.search(r"/global/en/business/(overview|payment-solutions/[^/]+)\.html$", path):
        return True
    if re.search(r"^/en/(capabilities|solutions|industries|advisors)(/[^/]+)?/?$", path):
        return True
    return False


def is_item_level_mastercard_url(url: str) -> bool:
    if not is_official_mastercard_domain(url):
        return False
    if is_search_page_url(url) or is_listing_root_url(url) or is_generic_product_root_url(url):
        return False
    parsed = urlparse(canonicalize_mastercard_url(url))
    path = parsed.path.casefold().rstrip("/")
    if path in {"", "/", "/tr-tr.html"}:
        return False
    if re.search(r"/news/.+/(press-releases|news-briefs)/.+/.{20,}$", path):
        return True
    if re.search(r"/news/(press|perspectives)/.+/.{20,}$", path):
        return True
    if re.search(r"/us/en/news-and-trends/press/20\d{2}/.+/.{20,}\.html$", path):
        return True
    if re.search(r"/news/press/20\d{2}/.+/.{20,}$", path):
        return True
    if re.search(r"/(insights|case-studies|webinar|resources)/.+/.{20,}$", path) and not is_generic_product_root_url(url):
        return True
    return False


def parse_mastercard_date(*texts: str) -> tuple[str, str, str, str]:
    for text in texts:
        match = DATE_RE.search(clean(text))
        if not match:
            continue
        raw = match.group(0)
        try:
            if match.group("iso"):
                return raw, raw, "publication_date", "Yüksek"
            parts = raw.replace(",", "").split()
            if match.group("month_first"):
                month = MONTHS[parts[0].casefold()]
                day = int(parts[1])
                year = int(parts[2])
                return f"{year:04d}-{month:02d}-{day:02d}", raw, "publication_date", "Yüksek"
            if match.group("day_first"):
                day = int(parts[0])
                month = MONTHS[parts[1].casefold()]
                year = int(parts[2])
                return f"{year:04d}-{month:02d}-{day:02d}", raw, "publication_date", "Yüksek"
            if match.group("month_only"):
                return "", raw, "month_only_context", "Orta"
        except Exception:
            continue
    return "", "", "", ""


def is_post_cutoff(date_value: str, cutoff: str = START_DATE) -> bool:
    return bool(re.match(r"^20\d{2}-\d{2}-\d{2}$", clean(date_value))) and clean(date_value) >= cutoff


def clean_html_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "nav", "footer"]):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        attrs = getattr(tag, "attrs", {}) or {}
        classes = attrs.get("class", "")
        if isinstance(classes, list):
            classes = " ".join(str(value) for value in classes)
        blob = " ".join(str(value) for value in [attrs.get("id", ""), classes, attrs.get("role", ""), attrs.get("aria-label", "")] if value)
        if NAV_RE.search(blob):
            tag.decompose()
    lines = []
    seen = set()
    for raw in soup.get_text("\n", strip=True).splitlines():
        line = clean(raw)
        if len(line) < 3 or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return "\n".join(lines).strip()


def title_from_html(html: str, fallback: str = "") -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for selector in ["h1", "meta[property='og:title']", "meta[name='twitter:title']"]:
        node = soup.select_one(selector)
        if not node:
            continue
        value = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
        value = clean(value)
        if value:
            return value
    if soup.title:
        return clean(soup.title.get_text(" ", strip=True))
    return clean(fallback)


def canonical_from_html(html: str, final_url: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    node = soup.select_one("link[rel='canonical']")
    if node and node.get("href"):
        return canonicalize_mastercard_url(urljoin(final_url, node["href"]))
    for selector in ["meta[property='og:url']", "meta[name='twitter:url']"]:
        meta = soup.select_one(selector)
        if meta and meta.get("content"):
            return canonicalize_mastercard_url(urljoin(final_url, meta["content"]))
    return canonicalize_mastercard_url(final_url)


def date_from_html(html: str, body_text: str) -> tuple[str, str, str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.get_text(" ", strip=True) or "{}")
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        for item in stack:
            if not isinstance(item, dict):
                continue
            for key in ["datePublished", "dateCreated"]:
                if item.get(key):
                    normalized, raw, _, confidence = parse_mastercard_date(str(item[key]))
                    if normalized:
                        return normalized, raw or str(item[key]), f"json_ld_{key}", confidence
    for selector, source in [
        ("meta[property='article:published_time']", "meta_article_published_time"),
        ("meta[name='date']", "meta_date"),
        ("meta[name='publishdate']", "meta_publishdate"),
        ("time[datetime]", "visible_time_datetime"),
        ("time", "visible_time"),
    ]:
        node = soup.select_one(selector)
        if not node:
            continue
        value = node.get("content") or node.get("datetime") or node.get_text(" ", strip=True)
        normalized, raw, _, confidence = parse_mastercard_date(str(value))
        if normalized:
            return normalized, raw or str(value), source, confidence
    normalized, raw, source, confidence = parse_mastercard_date(body_text[:1200])
    return normalized, raw, source or "", confidence


def detect_mastercard_page_type(url: str, html: str = "", body_text: str = "", title: str = "") -> str:
    blob = " ".join([clean(title), clean(body_text[:500]), clean(html[:500])])
    if ACCESS_DENIED_RE.search(blob):
        return "access_denied"
    if is_search_page_url(url):
        return "search_page"
    if is_listing_root_url(url):
        return "listing_page"
    if is_generic_product_root_url(url):
        return "product_page"
    if is_item_level_mastercard_url(url):
        local_title = title_from_html(html, title)
        date_value, _, _, _ = date_from_html(html, body_text)
        if local_title and (date_value or len(body_text) >= 500):
            return "article_page"
        return "unknown"
    if re.search(r"/(news|resources|industries|advisors|capabilities)(/)?$", urlparse(url).path, re.I):
        return "category_page"
    if not body_text:
        return "empty_shell"
    return "unknown"


class BrowserCollector:
    def __init__(self, wait_seconds: float = 4.0, engine: str = "selenium_chrome") -> None:
        self.wait_seconds = wait_seconds
        self.engine = engine
        self.driver = None

    def __enter__(self) -> "BrowserCollector":
        self._start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _start(self) -> None:
        if self.driver is not None:
            return
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--window-size=1440,1400")
            options.add_argument("--disable-dev-shm-usage")
            self.driver = webdriver.Chrome(options=options)
            self.engine = "selenium_chrome"
        except Exception as exc:
            self.driver = None
            self.engine = f"requests_fallback:{type(exc).__name__}"

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def get_page(self, url: str) -> BrowserPage:
        if self.driver is None:
            return self._get_with_requests(url)
        try:
            self.driver.get(url)
            time.sleep(self.wait_seconds)
            final_url = self.driver.current_url
            title = self.driver.title
            html = self.driver.page_source or ""
            body_text = ""
            try:
                body_text = self.driver.find_element("tag name", "body").text
            except Exception:
                body_text = clean_html_text(html)
            page_type = detect_mastercard_page_type(final_url, html, body_text, title)
            return BrowserPage(url=url, final_url=final_url, title=title, html=html, body_text=body_text, page_type=page_type, engine=self.engine)
        except Exception as exc:
            fallback = self._get_with_requests(url)
            fallback.engine = f"{self.engine}_failed_requests_fallback"
            fallback.error = str(exc)[:300]
            return fallback

    def _get_with_requests(self, url: str) -> BrowserPage:
        try:
            response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
            html = response.text
            body = clean_html_text(html)
            title = title_from_html(html, "")
            page_type = detect_mastercard_page_type(response.url, html, body, title)
            return BrowserPage(url=url, final_url=response.url, title=title, html=html, body_text=body, page_type=page_type, engine=self.engine)
        except Exception as exc:
            return BrowserPage(url=url, final_url=url, title="", html="", body_text="", page_type="empty_shell", engine=self.engine, error=str(exc)[:300])


def extract_article_links_from_page(page: BrowserPage) -> list[dict[str, str]]:
    soup = BeautifulSoup(page.html or "", "html.parser")
    links = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        url = canonicalize_mastercard_url(urljoin(page.final_url, anchor["href"]))
        if url in seen or not is_official_mastercard_domain(url):
            continue
        seen.add(url)
        title = clean(anchor.get_text(" ", strip=True))
        if not title:
            title = clean(urlparse(url).path.rstrip("/").split("/")[-1].replace("-", " "))
        parent_text = clean(anchor.parent.get_text(" ", strip=True) if anchor.parent else "")
        if not is_item_level_mastercard_url(url):
            continue
        links.append(
            {
                "candidate_title": title,
                "candidate_url": url,
                "excerpt": parent_text[:500],
            }
        )
    return links


def title_match_score(expected_title: str, candidate_title: str, expected_keywords: list[str] | None = None) -> float:
    expected = clean(expected_title).casefold()
    candidate = clean(candidate_title).casefold()
    if not expected or not candidate:
        return 0.0
    similarity = SequenceMatcher(None, expected, candidate).ratio()
    keywords = [kw.casefold() for kw in (expected_keywords or []) if clean(kw)]
    keyword_score = 0.0
    if keywords:
        keyword_score = sum(1 for kw in keywords if kw in candidate) / len(keywords)
    return round((similarity * 0.65) + (keyword_score * 0.35), 3)


def passes_mastercard_article_gate(page: BrowserPage, expected_keywords: list[str] | None = None) -> ArticleGateResult:
    canonical_url = canonical_from_html(page.html, page.final_url)
    local_title = title_from_html(page.html, page.title)
    body = clean_html_text(page.html) or clean(page.body_text)
    body_chars = len(body)
    publication_date, date_raw_text, date_source, date_confidence = date_from_html(page.html, body)
    if not is_official_mastercard_domain(page.final_url):
        return ArticleGateResult(False, "not_official_mastercard_domain", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    if page.page_type == "access_denied":
        return ArticleGateResult(False, "access_denied", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    if not is_item_level_mastercard_url(canonical_url):
        return ArticleGateResult(False, "not_item_level_url", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    if page.page_type != "article_page":
        return ArticleGateResult(False, f"page_type_{page.page_type}", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    if not local_title:
        return ArticleGateResult(False, "missing_article_title", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    if not publication_date:
        return ArticleGateResult(False, "missing_publication_date", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    if not is_post_cutoff(publication_date):
        return ArticleGateResult(False, "pre_cutoff_or_partial_date", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    if NOISE_RE.search(f"{local_title} {body[:1000]}"):
        return ArticleGateResult(False, "brand_lifestyle_or_consumer_noise", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    keywords = expected_keywords or []
    if keywords and not any(kw.casefold() in f"{local_title} {body}".casefold() for kw in keywords):
        return ArticleGateResult(False, "expected_keywords_missing", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    if body_chars < 500 and not SHORT_ANNOUNCEMENT_FACT_RE.search(f"{local_title} {body}"):
        return ArticleGateResult(False, "body_too_short_without_substantive_launch_facts", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    if not STRATEGIC_RE.search(f"{local_title} {body[:1500]}"):
        return ArticleGateResult(False, "no_mastercard_strategic_relevance_signal", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)
    return ArticleGateResult(True, "", publication_date, date_raw_text, date_source, date_confidence, body_chars, local_title, canonical_url)


def resolve_mastercard_seed_to_articles(
    collector: BrowserCollector,
    seed_url: str,
    expected_title: str,
    expected_keywords: list[str],
    source_family: str,
    max_candidates: int = 5,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    seed_page = collector.get_page(seed_url)
    links = extract_article_links_from_page(seed_page) if seed_page.page_type not in {"access_denied", "empty_shell"} else []
    resolution_base = {
        "source_family": source_family,
        "expected_title": expected_title,
        "seed_url": seed_url,
        "seed_page_type": seed_page.page_type,
        "links_discovered": str(len(links)),
        "checked_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }
    if seed_page.page_type == "product_page":
        return {
            **resolution_base,
            "candidate_title": expected_title,
            "candidate_url": seed_page.final_url,
            "title_match_score": "1.000",
            "candidate_page_type": "product_page",
            "final_canonical_url": canonical_from_html(seed_page.html, seed_page.final_url),
            "publication_date": "",
            "date_source": "",
            "date_confidence": "",
            "body_chars": str(len(clean_html_text(seed_page.html) or seed_page.body_text)),
            "resolution_status": "Product Benchmark",
            "recent_item_eligible": "False",
            "rejection_reason": "product_page_benchmark_only",
        }, []
    if seed_page.page_type == "access_denied":
        return {
            **resolution_base,
            "candidate_title": "",
            "candidate_url": "",
            "title_match_score": "0.000",
            "candidate_page_type": "access_denied",
            "final_canonical_url": canonicalize_mastercard_url(seed_page.final_url),
            "publication_date": "",
            "date_source": "",
            "date_confidence": "",
            "body_chars": str(len(seed_page.body_text)),
            "resolution_status": "Unresolved",
            "recent_item_eligible": "False",
            "rejection_reason": "seed_page_access_denied",
        }, []
    if is_item_level_mastercard_url(seed_page.final_url):
        gate = passes_mastercard_article_gate(seed_page, expected_keywords)
        return {
            **resolution_base,
            "candidate_title": gate.title or expected_title,
            "candidate_url": seed_page.final_url,
            "title_match_score": f"{title_match_score(expected_title, gate.title, expected_keywords):.3f}",
            "candidate_page_type": seed_page.page_type,
            "final_canonical_url": gate.canonical_url,
            "publication_date": gate.publication_date,
            "date_source": gate.date_source,
            "date_confidence": gate.date_confidence,
            "body_chars": str(gate.body_chars),
            "resolution_status": "Resolved" if gate.passed else "Rejected",
            "recent_item_eligible": str(gate.passed),
            "rejection_reason": gate.rejection_reason,
        }, [{"page": seed_page, "gate": gate}] if gate.passed else []

    scored = []
    for link in links:
        score = title_match_score(expected_title, link["candidate_title"], expected_keywords)
        if score >= 0.45 or any(kw.casefold() in f"{link['candidate_title']} {link.get('excerpt', '')}".casefold() for kw in expected_keywords):
            scored.append((score, link))
    scored.sort(key=lambda item: item[0], reverse=True)
    verified = []
    first_resolution = None
    for score, link in scored[:max_candidates]:
        candidate_page = collector.get_page(link["candidate_url"])
        gate = passes_mastercard_article_gate(candidate_page, expected_keywords)
        row = {
            **resolution_base,
            "candidate_title": link["candidate_title"],
            "candidate_url": link["candidate_url"],
            "title_match_score": f"{score:.3f}",
            "candidate_page_type": candidate_page.page_type,
            "final_canonical_url": gate.canonical_url,
            "publication_date": gate.publication_date,
            "date_source": gate.date_source,
            "date_confidence": gate.date_confidence,
            "body_chars": str(gate.body_chars),
            "resolution_status": "Resolved" if gate.passed else "Rejected",
            "recent_item_eligible": str(gate.passed),
            "rejection_reason": gate.rejection_reason,
        }
        if first_resolution is None:
            first_resolution = row
        if gate.passed:
            verified.append({"page": candidate_page, "gate": gate, "match_score": score})
    if first_resolution is not None:
        return first_resolution, verified
    return {
        **resolution_base,
        "candidate_title": "",
        "candidate_url": "",
        "title_match_score": "0.000",
        "candidate_page_type": seed_page.page_type,
        "final_canonical_url": canonical_from_html(seed_page.html, seed_page.final_url),
        "publication_date": "",
        "date_source": "",
        "date_confidence": "",
        "body_chars": str(len(clean_html_text(seed_page.html) or seed_page.body_text)),
        "resolution_status": "Unresolved",
        "recent_item_eligible": "False",
        "rejection_reason": "no_strong_article_match_found",
    }, []
