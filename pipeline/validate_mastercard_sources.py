from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
DATA_DIR = ROOT_DIR / "data"
REGISTRY_PATH = DATA_DIR / "source_registry.csv"
VALIDATION_PATH = DATA_DIR / "mastercard_source_validation_candidates.csv"
INSPECTION_PATH = DATA_DIR / "mastercard_candidate_inspection_table.csv"
DISCOVERY_LOG_DIR = DATA_DIR / "mastercard_discovery_logs"

from utils.browser_collector import is_generic_product_root_url, is_search_page_url

START_DATE = "2026-05-01"
MASTERCARD_ID = "mastercard"
MASTERCARD_NAME = "Mastercard"
INSTITUTION_TYPE = "Global Ödeme Ağı"
COVERAGE_SCOPE = "Kritik Stratejik Ödeme Ağı ve Teknoloji Ortağı"
INSTITUTION_GROUP = "Global Ödeme Ağları"
STRATEGIC_PARTNER_PRIORITY = "Kritik"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

SOURCE_VALIDATION_COLUMNS = [
    "institution_name",
    "candidate_url",
    "source_name",
    "source_family",
    "proposed_extraction_mode",
    "official_source_valid",
    "collector_accessible",
    "extraction_structurally_valid",
    "http_status",
    "final_url",
    "response_size",
    "collector_capability",
    "item_level_link_count",
    "dated_link_count",
    "post_cutoff_link_count",
    "akbank_link_count",
    "turkiye_link_count",
    "competitor_bank_link_count",
    "commercial_payment_link_count",
    "merchant_link_count",
    "sme_link_count",
    "tokenization_security_link_count",
    "agentic_ai_link_count",
    "retail_noise_ratio",
    "structurally_valid",
    "currently_fresh",
    "benchmark_ready",
    "mvp_ready",
    "claude_ready",
    "validation_result",
    "activation_recommendation",
    "reason",
    "checked_at",
]

INSPECTION_COLUMNS = [
    "source_id",
    "source_family",
    "item_title",
    "item_url",
    "publication_date",
    "launch_date",
    "recency_basis_date",
    "recency_basis_type",
    "date_confidence",
    "network_signal_type",
    "network_layer",
    "deployment_scope",
    "named_bank_or_partner",
    "direct_akbank_signal",
    "turkiye_relevance",
    "akbank_relevance",
    "transferability",
    "time_horizon",
    "content_role",
    "proposed_destination",
    "strategic_priority_score",
    "accepted",
    "rejection_reason",
    "duplicate_status",
    "notes",
]

REGISTRY_EXTRA_COLUMNS = ["institution_type", "strategic_partner_priority"]

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

AKBANK_RE = re.compile(r"\b(akbank|akbanklı|akbankli|axess|wings|akbank kart|akbank pos|akbank api|akbank lab|akbank business)\b", re.I)
TURKISH_COMPETITOR_RE = re.compile(
    r"\b(garanti\s*bbva|iş bankası|is bankasi|yapı kredi|yapi kredi|qnb|denizbank|ing|teb|"
    r"şekerbank|sekerbank|fibabanka|enpara|türkiye finans|turkiye finans|kuveyt türk|kuveyt turk|"
    r"albaraka türk|albaraka turk|vakıf katılım|vakif katilim|ziraat katılım|ziraat katilim|"
    r"papara|iyzico|paytr|param|sipay|paynet)\b",
    re.I,
)
TURKIYE_RE = re.compile(r"(türkiye|turkiye|turkey|istanbul|ankara|izmir|bkm|troy|tcmb|bddk)", re.I)
COMMERCIAL_RE = re.compile(
    r"(commercial card|corporate card|business card|purchasing card|fleet card|expense|travel and expense|"
    r"virtual card|b2b|supplier payment|accounts payable|accounts receivable|receivables manager|working capital|"
    r"commercial payments|ticari kart|kurumsal kart|sanal kart)",
    re.I,
)
MERCHANT_RE = re.compile(
    r"(merchant cloud|merchant|acquiring|acceptance|payment acceptance|gateway|checkout|click to pay|pos|"
    r"e-commerce|omnichannel|payment orchestration|psp|isv|üye işyeri|uye isyeri)",
    re.I,
)
SME_RE = re.compile(r"(small business|sme|smb|kob[iı]|esnaf|microbusiness|entrepreneur|girişimci|girisimci)", re.I)
TOKEN_SECURITY_RE = re.compile(
    r"(token|network credential|credential|passkey|biometric|identity check|authentication|fraud|cyber|security|"
    r"risk monitoring|account takeover|card-on-file|digital identity|kimlik|güvenlik|guvenlik)",
    re.I,
)
AGENTIC_RE = re.compile(r"(agent pay|agentic|ai agent|artificial intelligence|verifiable intent|agent suite|machine-driven|ai commerce)", re.I)
OPEN_DATA_RE = re.compile(r"(open finance|open banking|data|analytics|insights|personalization|decision intelligence)", re.I)
CROSS_BORDER_RE = re.compile(r"(cross-border|multi-rail|stablecoin|digital assets|blockchain|settlement|remittance)", re.I)
NOISE_RE = re.compile(
    r"(priceless|sports|football|sponsorship|music|festival|celebrity|tourism|destination|culinary|"
    r"employer|workplace|csr|donation|sustainability storytelling|art|entertainment|lifestyle)",
    re.I,
)
NAV_TITLE_RE = re.compile(r"^(skip to main content|customer stories|blog & reports|economics institute|webinars|resources|contact us|sign in|login|learn more)$", re.I)
AWARD_RE = re.compile(r"(award|ödül|odul|recognized|ranked|wins|honor)", re.I)
RESEARCH_RE = re.compile(r"(research|report|study|survey|index|white paper|insight)", re.I)
PRODUCT_ROOT_RE = re.compile(r"(/business/|/payment-solutions/|/capabilities/|/solutions/|/documentation/)", re.I)
ITEM_PATH_RE = re.compile(r"(/newsroom/|/press-releases/|/news-briefs/|/insights/|/case-studies/|/webinar/|/resources/)", re.I)


@dataclass(frozen=True)
class CandidateSource:
    source_family: str
    source_name: str
    url: str
    proposed_extraction_mode: str
    source_type: str
    strategic_themes: str
    notes: str = ""
    preserve_source_id: str = ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def source_key(url: str) -> str:
    parsed = urlparse(canonicalize_mastercard_url(url))
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.netloc.casefold().removeprefix('www.')}{parsed.path.rstrip('/')}{query}".casefold()


def canonicalize_mastercard_url(url: str) -> str:
    parsed = urlparse(clean(url))
    keep = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        if key.lower().startswith(("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")):
            continue
        keep.append((key, value))
    path = re.sub(r"/+$", "/", parsed.path)
    return urlunparse((parsed.scheme.lower() or "https", parsed.netloc.lower(), path, "", urlencode(keep), ""))


def stable_candidate_key(title: str, url: str) -> str:
    raw = f"{clean(title).casefold()}|{source_key(url)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def parse_mastercard_date(*texts: str) -> tuple[str, str, str]:
    for text in texts:
        match = DATE_RE.search(clean(text))
        if not match:
            continue
        raw = match.group(0)
        try:
            if match.group("iso"):
                return raw, "publication_date", "Yüksek"
            parts = raw.replace(",", "").split()
            if match.group("month_first"):
                month = MONTHS[parts[0].casefold()]
                day = int(parts[1])
                year = int(parts[2])
                return f"{year:04d}-{month:02d}-{day:02d}", "publication_date", "Yüksek"
            if match.group("day_first"):
                day = int(parts[0])
                month = MONTHS[parts[1].casefold()]
                year = int(parts[2])
                return f"{year:04d}-{month:02d}-{day:02d}", "publication_date", "Yüksek"
            if match.group("month_only"):
                return raw, "month_only_context", "Orta"
        except Exception:
            continue
    return "", "", ""


def is_post_cutoff(date_value: str, cutoff: str = START_DATE) -> bool:
    if not re.match(r"^20\d{2}-\d{2}-\d{2}$", clean(date_value)):
        return False
    return clean(date_value) >= cutoff


def fetch(url: str) -> tuple[requests.Response | None, str]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        return response, ""
    except Exception as exc:
        return None, str(exc)[:300]


def useful_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "nav", "footer"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def extract_links(html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    links = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        url = canonicalize_mastercard_url(urljoin(base_url, anchor["href"]))
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if "mastercard" not in parsed.netloc:
            continue
        if url in seen:
            continue
        seen.add(url)
        title = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip()
        if not title:
            slug = parsed.path.rstrip("/").split("/")[-1]
            title = re.sub(r"[-_]+", " ", slug).strip().title()
        if len(title) < 8:
            continue
        if NAV_TITLE_RE.match(title):
            continue
        date_value, _, _ = parse_mastercard_date(title, url)
        links.append({"title": title, "url": url, "date": date_value})
    return links


def mastercard_sources() -> list[CandidateSource]:
    themes = "Global İyi Uygulama; Ödemeler ve POS; Ticari Kartlar; Gömülü Finans; Ağ Standartları"
    return [
        CandidateSource("EEMEA Newsroom", "Mastercard EEMEA Newsroom", "https://www.mastercard.com/news/eemea/en/newsroom/", "browser_required", "Resmi Basın Bülteni Sayfası", themes, preserve_source_id="REG-071"),
        CandidateSource("EEMEA Newsroom", "Mastercard EEMEA Press Releases", "https://www.mastercard.com/news/eemea/en/newsroom/press-releases/", "browser_required", "Resmi Basın Bülteni Sayfası", themes, preserve_source_id="REG-036"),
        CandidateSource("EEMEA Newsroom", "Mastercard EEMEA News Briefs", "https://www.mastercard.com/news/eemea/en/newsroom/news-briefs/", "browser_required", "Resmi Basın Bülteni Sayfası", themes, preserve_source_id="REG-072"),
        CandidateSource("EEMEA Newsroom", "Mastercard EEMEA Perspectives", "https://www.mastercard.com/news/eemea/en/perspectives/", "browser_required", "Resmi Basın Bülteni Sayfası", themes, preserve_source_id="REG-073"),
        CandidateSource("SME and Small Business Solutions", "Mastercard Türkiye SME digitalization article", "https://www.mastercard.com/news/eemea/en/newsroom/press-releases/en/2025-1/august/the-path-to-smart-smes-lies-in-encouraging-digital-investments/", "benchmark_fact", "Resmi Basın Bülteni Sayfası", themes, "Pre-cutoff article retained as context; not a current weekly-development source.", preserve_source_id="REG-035"),
        CandidateSource("Global Newsroom", "Mastercard Global Newsroom", "https://www.mastercard.com/news/", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
        CandidateSource("Global Newsroom", "Mastercard Global Press", "https://www.mastercard.com/news/press/", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
        CandidateSource("Türkiye", "Mastercard Türkiye Official Site", "https://www.mastercard.com.tr/tr-tr.html", "manual", "Resmi Site", themes, "Türkiye official shell; source-quality depends on rendered Turkish pages."),
        CandidateSource("Commercial Payments", "Mastercard Business Overview", "https://www.mastercard.com/global/en/business/overview.html", "benchmark_fact", "Resmi Ürün Sayfası", themes),
        CandidateSource("Commercial Cards", "Mastercard Commercial Cards", "https://www.mastercard.com/global/en/business/payment-solutions/commercial-cards.html", "benchmark_fact", "Resmi Ürün Sayfası", themes),
        CandidateSource("SME and Small Business Solutions", "Mastercard Small Business Solutions", "https://www.mastercard.com/global/en/business/payment-solutions/small-business.html", "benchmark_fact", "Resmi Ürün Sayfası", themes),
        CandidateSource("Virtual Cards", "Mastercard Virtual Cards", "https://www.mastercard.com/global/en/business/payment-solutions/virtual-cards.html", "benchmark_fact", "Resmi Ürün Sayfası", themes),
        CandidateSource("Accounts Payable Solutions", "Mastercard Accounts Payable", "https://www.mastercard.com/global/en/business/payment-solutions/accounts-payable.html", "benchmark_fact", "Resmi Ürün Sayfası", themes),
        CandidateSource("Accounts Receivable Solutions", "Mastercard Accounts Receivable", "https://www.mastercard.com/global/en/business/payment-solutions/accounts-receivable.html", "benchmark_fact", "Resmi Ürün Sayfası", themes),
        CandidateSource("Cross-Border Services", "Mastercard Cross-Border Services", "https://www.mastercard.com/global/en/business/payment-solutions/cross-border-services.html", "benchmark_fact", "Resmi Ürün Sayfası", themes),
        CandidateSource("Merchant Cloud", "Mastercard Merchant Cloud Official News", "https://www.mastercard.com/news/eemea/en/newsroom/press-releases/en/2026/may/network-international-jordan-launches-click-to-pay-through-mastercard-merchant-cloud-expanding-access-to-secure-digital-payments/", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
        CandidateSource("Merchant Acquiring and Acceptance", "Mastercard Click to Pay / Merchant Acceptance", "https://www.mastercard.com/news/eemea/en/newsroom/press-releases/en/2026/may/network-international-jordan-launches-click-to-pay-through-mastercard-merchant-cloud-expanding-access-to-secure-digital-payments/", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
        CandidateSource("B2B Payments", "Mastercard Commercial Payments News", "https://www.mastercard.com/news/press/?q=commercial%20payments", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
        CandidateSource("Mastercard Receivables Manager", "Mastercard Receivables Manager Search Surface", "https://www.mastercard.com/news/press/?q=receivables%20manager", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
        CandidateSource("Embedded Finance", "Mastercard Embedded Finance Search Surface", "https://www.mastercard.com/news/press/?q=embedded%20finance", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
        CandidateSource("Agent Pay", "Mastercard Agent Pay Official News", "https://www.mastercard.com/news/press/?q=Agent%20Pay", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
        CandidateSource("Agentic Commerce", "Mastercard Agentic Commerce Advisory", "https://www.mastercardservices.com/en/advisors/commerce-reimagined-agentic-edge", "benchmark_fact", "Resmi Araştırma / İçgörü Sayfası", themes),
        CandidateSource("Tokenization and Network Credentials", "Mastercard Tokenization / Network Credentials", "https://www.mastercard.com/news/press/?q=tokenization%20network%20credentials", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
        CandidateSource("Identity Check and Authentication", "Mastercard Identity Check / Authentication", "https://www.mastercard.com/news/press/?q=identity%20check%20authentication", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
        CandidateSource("Cybersecurity and Fraud", "Mastercard Cybersecurity Services", "https://www.mastercardservices.com/en/resources/webinar/mastering-cyber-resilience-strategies-acquirers-and-processors-face-emerging", "benchmark_fact", "Resmi Araştırma / İçgörü Sayfası", themes),
        CandidateSource("Open Finance", "Mastercard Open Finance Advisory", "https://www.mastercardservices.com/en/advisors/payments-consulting/insights/open-finance-framework-arab-region-more-question-scope", "benchmark_fact", "Resmi Araştırma / İçgörü Sayfası", themes),
        CandidateSource("Data and Analytics", "Mastercard Data and Analytics for Financial Institutions", "https://www.mastercardservices.com/en/resources/webinar/enhancing-customer-journey-data-driven-personalization-financial-institutions", "benchmark_fact", "Resmi Araştırma / İçgörü Sayfası", themes),
        CandidateSource("Digital Assets and Multi-Rail Payments", "Mastercard Digital Assets / Multi-Rail News", "https://www.mastercard.com/news/press/?q=stablecoin%20multi-rail%20digital%20assets", "browser_required", "Resmi Basın Bülteni Sayfası", themes),
    ]


def source_id_for(candidate: CandidateSource, existing_by_key: dict[str, str], next_id: int) -> tuple[str, int]:
    if candidate.preserve_source_id:
        return candidate.preserve_source_id, next_id
    existing = existing_by_key.get(source_key(candidate.url))
    if existing:
        return existing, next_id
    return f"REG-{next_id:03d}", next_id + 1


def classify_mastercard_item(title: str, url: str, text: str = "", publication_date: str = "") -> dict[str, object]:
    blob = " ".join([clean(title), clean(url), clean(text)])
    has_akbank = bool(AKBANK_RE.search(blob))
    competitor_match = TURKISH_COMPETITOR_RE.search(blob)
    has_competitor = bool(competitor_match) and not has_akbank
    has_turkiye = bool(TURKIYE_RE.search(blob) or has_akbank or competitor_match)
    has_commercial = bool(COMMERCIAL_RE.search(blob))
    has_merchant = bool(MERCHANT_RE.search(blob))
    has_sme = bool(SME_RE.search(blob))
    has_token_security = bool(TOKEN_SECURITY_RE.search(blob))
    has_agentic = bool(AGENTIC_RE.search(blob))
    has_open_data = bool(OPEN_DATA_RE.search(blob))
    has_cross_border = bool(CROSS_BORDER_RE.search(blob))
    is_noise = bool(NOISE_RE.search(blob)) and not any([has_akbank, has_competitor, has_commercial, has_merchant, has_token_security, has_agentic])
    is_award = bool(AWARD_RE.search(blob))
    is_research = bool(RESEARCH_RE.search(blob))
    is_product_root = bool(PRODUCT_ROOT_RE.search(url)) and not is_post_cutoff(publication_date)
    publication_date = clean(publication_date)
    post_cutoff = is_post_cutoff(publication_date)

    if has_akbank:
        signal = "Doğrudan Akbank Sinyali"
        deployment = "Akbank"
        akbank_relevance = "Kritik" if post_cutoff else "Yüksek"
        transferability = "Doğrudan Uygulanabilir"
    elif has_competitor and has_turkiye:
        signal = "Türkiye Rakip Banka Uygulaması"
        deployment = "Türkiye"
        akbank_relevance = "Yüksek"
        transferability = "Türkiye’ye Uyarlanabilir"
    elif has_turkiye:
        signal = "Türkiye Ödeme Ekosistemi Sinyali"
        deployment = "Türkiye"
        akbank_relevance = "Yüksek" if any([has_merchant, has_token_security, has_agentic, has_commercial]) else "Orta"
        transferability = "Türkiye’ye Uyarlanabilir"
    elif re.search(r"(eemea|middle east|africa|europe|jordan|uae|saudi|egypt)", blob, re.I):
        signal = "EEMEA Uygulaması"
        deployment = "EEMEA"
        akbank_relevance = "Orta"
        transferability = "Türkiye’ye Uyarlanabilir"
    elif any([has_commercial, has_merchant, has_token_security, has_agentic, has_open_data, has_cross_border, has_sme]):
        signal = "Aktarılabilir Mastercard Kabiliyeti" if not has_agentic else "Global Ödeme Teknolojisi Yönü"
        deployment = "Global"
        akbank_relevance = "Orta"
        transferability = "İzlenmesi Gereken Kabiliyet"
    elif is_research:
        signal = "Bağlamsal Araştırma"
        deployment = "Global"
        akbank_relevance = "Düşük"
        transferability = "Uzun Vadeli Yön Sinyali"
    else:
        signal = "Kapsam Dışı"
        deployment = "Belirsiz"
        akbank_relevance = "Kapsam Dışı"
        transferability = "Uygulanabilir Değil"

    layer = "Diğer"
    if has_agentic:
        layer = "AI / Agentic Commerce"
    elif has_token_security:
        layer = "Tokenizasyon" if re.search(r"(token|credential|card-on-file)", blob, re.I) else "Fraud ve Siber Güvenlik"
    elif has_commercial:
        layer = "Ticari Kartlar" if re.search(r"(card|kart)", blob, re.I) else "B2B Ödemeler"
    elif re.search(r"(receivable|tahsilat)", blob, re.I):
        layer = "Alacak ve Tahsilat Yönetimi"
    elif re.search(r"(payable|supplier)", blob, re.I):
        layer = "Tedarikçi Ödemeleri"
    elif has_merchant:
        layer = "Merchant Acquiring"
    elif has_open_data:
        layer = "Veri ve Analitik"
    elif has_cross_border:
        layer = "Çoklu Raylı Ödeme"
    elif has_sme:
        layer = "SME Çözümleri"

    score = strategic_priority_score(
        direct_akbank=has_akbank,
        turkish_competitor=has_competitor and has_turkiye,
        issuing_or_card=bool(re.search(r"(issuing|issuer|card|credential|kart)", blob, re.I)),
        merchant=has_merchant,
        commercial_b2b=has_commercial,
        token_security=has_token_security,
        transferability=transferability,
        novelty=bool(re.search(r"(launch|first|new|pilot|introduced|unveiled|live|complete|deploy)", blob, re.I)),
        evidence_quality=bool(ITEM_PATH_RE.search(url) or post_cutoff),
        proximity=has_turkiye or deployment in {"Akbank", "EEMEA"},
    )

    if is_noise:
        accepted = False
        role = "Kapsam Dışı"
        destination = "Arşiv / Reddedilen Gürültü"
        rejection = "brand_lifestyle_or_consumer_noise"
    elif is_product_root:
        accepted = True
        role = "Benchmark Fact"
        destination = "Benchmark Fact"
        rejection = ""
    elif is_award and signal != "Kapsam Dışı":
        accepted = True
        role = "Yönetici Bilgilendirme"
        destination = "Yönetici Bilgilendirme Notları"
        rejection = ""
    elif is_research and score < 14:
        accepted = True
        role = "Bağlamsal Veri"
        destination = "Bağlamsal Araştırma"
        rejection = ""
    elif score >= 9 and signal != "Kapsam Dışı":
        accepted = True
        role = "Bağımsız Gelişme" if post_cutoff else "Benchmark Fact"
        destination = "Stratejik / BD Gündemi" if score >= 14 and post_cutoff else "Global Ödeme ve Teknoloji Sinyalleri"
        rejection = ""
    else:
        accepted = False
        role = "Kapsam Dışı"
        destination = "Arşiv / Düşük Öncelik"
        rejection = "insufficient_payment_strategy_signal"

    if has_akbank and publication_date and not post_cutoff:
        role = "Bağlamsal Veri"
        destination = "Stratejik İlişki Bağlamı"
        accepted = True
        rejection = ""

    return {
        "network_signal_type": signal,
        "network_layer": layer,
        "deployment_scope": deployment,
        "named_bank_or_partner": clean(competitor_match.group(0)) if competitor_match else ("Akbank" if has_akbank else ""),
        "direct_akbank_signal": str(has_akbank),
        "turkiye_relevance": "True" if has_turkiye else "False",
        "akbank_relevance": akbank_relevance,
        "transferability": transferability,
        "time_horizon": "Bugün / 0–6 Ay" if post_cutoff and deployment in {"Akbank", "Türkiye"} else ("Orta Vadeli / 6–18 Ay" if score >= 9 else "Uzun Vadeli / 18+ Ay"),
        "content_role": role,
        "proposed_destination": destination,
        "strategic_priority_score": score,
        "accepted": str(accepted),
        "rejection_reason": rejection,
    }


def strategic_priority_score(
    direct_akbank: bool,
    turkish_competitor: bool,
    issuing_or_card: bool,
    merchant: bool,
    commercial_b2b: bool,
    token_security: bool,
    transferability: str,
    novelty: bool,
    evidence_quality: bool,
    proximity: bool,
) -> int:
    score = 0
    score += 5 if direct_akbank else 0
    score += 4 if turkish_competitor else 0
    score += 4 if issuing_or_card else 0
    score += 4 if merchant else 0
    score += 4 if commercial_b2b else 0
    score += 3 if token_security else 0
    score += {"Doğrudan Uygulanabilir": 3, "Türkiye’ye Uyarlanabilir": 3, "İzlenmesi Gereken Kabiliyet": 2, "Uzun Vadeli Yön Sinyali": 1}.get(transferability, 0)
    score += 2 if novelty else 0
    score += 2 if evidence_quality else 0
    score += 2 if proximity else 0
    return score


def validation_row(candidate: CandidateSource, source_id: str, checked_at: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    response, error = fetch(candidate.url)
    status = str(response.status_code) if response is not None else ""
    final_url = canonicalize_mastercard_url(response.url if response is not None else candidate.url)
    body = response.text if response is not None else ""
    response_size = str(len(response.content)) if response is not None else "0"
    text = useful_text(body)
    blocked = response is not None and response.status_code in {401, 403}
    if blocked:
        collector = "browser_required"
    elif response is None:
        collector = "unsupported"
    elif response.status_code >= 400:
        collector = "manual"
    else:
        collector = "static_scrape"

    links = extract_links(body, final_url) if response is not None and response.ok else []
    item_links = [link for link in links if ITEM_PATH_RE.search(link["url"]) or DATE_RE.search(link["title"])]
    dated_links = [link for link in item_links if parse_mastercard_date(link["title"], link["url"])[0]]
    post_cutoff_links = [link for link in dated_links if is_post_cutoff(parse_mastercard_date(link["title"], link["url"])[0])]
    retail_noise_ratio = 0.0
    if item_links:
        retail_noise_ratio = sum(1 for link in item_links if NOISE_RE.search(f"{link['title']} {link['url']}")) / len(item_links)

    official_source_valid = "mastercard" in urlparse(final_url).netloc.casefold()
    collector_accessible = bool(response is not None and response.ok and not blocked)
    extraction_structurally_valid = bool(collector_accessible and (len(item_links) > 0 or candidate.proposed_extraction_mode == "benchmark_fact") and len(text) > 250)
    structurally_valid = extraction_structurally_valid
    currently_fresh = bool(post_cutoff_links)
    benchmark_ready = candidate.proposed_extraction_mode == "benchmark_fact" and extraction_structurally_valid and not blocked
    mvp_ready = candidate.proposed_extraction_mode == "weekly_development" and currently_fresh and collector == "static_scrape" and extraction_structurally_valid
    if blocked:
        validation_result = "browser_required"
        activation = "keep_active_but_mvp_false"
        reason = "Official Mastercard source blocks standards-based static requests; browser collector required before MVP/Claude."
    elif response is None:
        validation_result = "fetch_error"
        activation = "manual"
        reason = error
    elif response.status_code >= 400:
        validation_result = "http_error"
        activation = "manual"
        reason = f"HTTP {response.status_code}; validate manually."
    elif benchmark_ready:
        validation_result = "benchmark_ready"
        activation = "activate_benchmark_fact_only"
        reason = "Static page reachable; product/capability surface should not create fake recent developments."
    elif mvp_ready:
        validation_result = "weekly_ready"
        activation = "activate_weekly_development"
        reason = "Static source exposes dated post-cutoff item-level links."
    else:
        validation_result = "needs_review"
        activation = "manual_or_benchmark_only"
        reason = "Reachable but no reliable dated post-cutoff item-level links."

    blob_links = "\n".join(f"{link['title']} {link['url']}" for link in item_links) + "\n" + text[:2000]
    row = {
        "institution_name": MASTERCARD_NAME,
        "candidate_url": candidate.url,
        "source_name": candidate.source_name,
        "source_family": candidate.source_family,
        "proposed_extraction_mode": candidate.proposed_extraction_mode,
        "official_source_valid": str(official_source_valid),
        "collector_accessible": str(collector_accessible),
        "extraction_structurally_valid": str(extraction_structurally_valid),
        "http_status": status,
        "final_url": final_url,
        "response_size": response_size,
        "collector_capability": collector,
        "item_level_link_count": str(len(item_links)),
        "dated_link_count": str(len(dated_links)),
        "post_cutoff_link_count": str(len(post_cutoff_links)),
        "akbank_link_count": str(len(AKBANK_RE.findall(blob_links))),
        "turkiye_link_count": str(len(TURKIYE_RE.findall(blob_links))),
        "competitor_bank_link_count": str(len(TURKISH_COMPETITOR_RE.findall(blob_links))),
        "commercial_payment_link_count": str(len(COMMERCIAL_RE.findall(blob_links))),
        "merchant_link_count": str(len(MERCHANT_RE.findall(blob_links))),
        "sme_link_count": str(len(SME_RE.findall(blob_links))),
        "tokenization_security_link_count": str(len(TOKEN_SECURITY_RE.findall(blob_links))),
        "agentic_ai_link_count": str(len(AGENTIC_RE.findall(blob_links))),
        "retail_noise_ratio": f"{retail_noise_ratio:.2f}",
        "structurally_valid": str(structurally_valid),
        "currently_fresh": str(currently_fresh),
        "benchmark_ready": str(benchmark_ready),
        "mvp_ready": str(mvp_ready),
        "claude_ready": "False",
        "validation_result": validation_result,
        "activation_recommendation": activation,
        "reason": reason,
        "checked_at": checked_at,
    }

    inspection = []
    for link in item_links[:80]:
        date_value, date_type, confidence = parse_mastercard_date(link["title"], link["url"])
        cls = classify_mastercard_item(link["title"], link["url"], "", date_value)
        inspection.append(
            {
                "source_id": source_id,
                "source_family": candidate.source_family,
                "item_title": link["title"],
                "item_url": link["url"],
                "publication_date": date_value if date_type == "publication_date" else "",
                "launch_date": "",
                "recency_basis_date": date_value,
                "recency_basis_type": date_type,
                "date_confidence": confidence,
                **{key: str(value) for key, value in cls.items()},
                "duplicate_status": "dry_run_only",
                "notes": "Extracted during Mastercard source validation; no recent item written.",
            }
        )
    return row, inspection


SEED_INSPECTION_ITEMS = [
    {
        "source_family": "Agent Pay",
        "title": "Mastercard launches Agent Pay as agentic AI reshapes digital commerce",
        "url": "https://www.mastercard.com/news/press/?q=Agent%20Pay",
        "date": "2026-06-01",
        "notes": "Official search/news surface is browser-required; title used as dry-run seed until rendered extraction exists.",
    },
    {
        "source_family": "Merchant Cloud",
        "title": "Network International Jordan launches Click to Pay through Mastercard Merchant Cloud",
        "url": "https://www.mastercard.com/news/eemea/en/newsroom/press-releases/en/2026/may/network-international-jordan-launches-click-to-pay-through-mastercard-merchant-cloud-expanding-access-to-secure-digital-payments/",
        "date": "2026-05-01",
        "notes": "EEMEA transferable merchant acceptance signal; official page requires browser collection.",
    },
    {
        "source_family": "Tokenization and Network Credentials",
        "title": "Mastercard expands network token and credential lifecycle capabilities for issuers and merchants",
        "url": "https://www.mastercard.com/news/press/?q=tokenization%20network%20credentials",
        "date": "2026-06-01",
        "notes": "Capability-class dry-run seed, not a production item.",
    },
    {
        "source_family": "Commercial Cards",
        "title": "Mastercard commercial cards and virtual cards support supplier payment automation",
        "url": "https://www.mastercard.com/global/en/business/payment-solutions/virtual-cards.html",
        "date": "",
        "notes": "Benchmark product root; should not become a fake development.",
    },
    {
        "source_family": "Global Newsroom",
        "title": "Mastercard Priceless music sponsorship campaign returns for summer",
        "url": "https://www.mastercard.com/news/press/?q=priceless%20music",
        "date": "2026-06-10",
        "notes": "Noise-control seed; should be rejected.",
    },
]


def seeded_inspection_rows(source_lookup: dict[str, str]) -> list[dict[str, str]]:
    rows = []
    for item in SEED_INSPECTION_ITEMS:
        date_value = item["date"]
        cls = classify_mastercard_item(item["title"], item["url"], "", date_value)
        if NOISE_RE.search(f"{item['title']} {item['url']}"):
            cls = {
                **cls,
                "content_role": "Kapsam Dışı",
                "proposed_destination": "Arşiv / Reddedilen Gürültü",
                "strategic_priority_score": 0,
                "accepted": "False",
                "rejection_reason": "brand_lifestyle_or_consumer_noise",
            }
        elif is_search_page_url(item["url"]):
            cls = {
                **cls,
                "content_role": "Keşif Seed'i",
                "proposed_destination": "Keşif / Çözümleme Bekliyor",
                "strategic_priority_score": 0,
                "accepted": "False",
                "rejection_reason": "seed_search_page_not_item_level",
            }
        elif is_generic_product_root_url(item["url"]):
            cls = {
                **cls,
                "content_role": "Benchmark Bilgisi",
                "proposed_destination": "Benchmark Fact",
                "accepted": "True",
                "rejection_reason": "",
            }
        elif item.get("notes", "").casefold().find("not a production item") >= 0 or item.get("notes", "").casefold().find("official page requires browser") >= 0:
            cls = {
                **cls,
                "content_role": "Keşif Seed'i",
                "proposed_destination": "Keşif / Article Doğrulama Bekliyor",
                "strategic_priority_score": 0,
                "accepted": "False",
                "rejection_reason": "article_body_date_not_browser_verified",
            }
        rows.append(
            {
                "source_id": source_lookup.get(item["source_family"], "REG-MASTERCARD-DRYRUN"),
                "source_family": item["source_family"],
                "item_title": item["title"],
                "item_url": canonicalize_mastercard_url(item["url"]),
                "publication_date": date_value,
                "launch_date": "",
                "recency_basis_date": date_value,
                "recency_basis_type": "publication_date" if date_value else "",
                "date_confidence": "Orta" if date_value else "",
                **{key: str(value) for key, value in cls.items()},
                "duplicate_status": "dry_run_seed",
                "notes": item["notes"],
            }
        )
    return rows


def dedupe_inspection_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    dedup: dict[str, dict[str, str]] = {}
    families: dict[str, set[str]] = {}
    for row in rows:
        key = source_key(row.get("item_url", "")) if row.get("item_url") else stable_candidate_key(row.get("item_title", ""), "")
        existing = dedup.get(key)
        families.setdefault(key, set()).add(row.get("source_family", ""))
        if existing is None:
            dedup[key] = dict(row)
            continue
        row_score = int(str(row.get("strategic_priority_score", "0") or 0))
        existing_score = int(str(existing.get("strategic_priority_score", "0") or 0))
        if row.get("accepted") == "True" and existing.get("accepted") != "True":
            dedup[key] = dict(row)
        elif row_score > existing_score:
            dedup[key] = dict(row)
    output = []
    for key, row in dedup.items():
        tags = sorted(value for value in families.get(key, set()) if value)
        if len(tags) > 1:
            row["source_family"] = "; ".join(tags)
            row["duplicate_status"] = "canonical_collapsed_multi_family"
            row["notes"] = f"{row.get('notes', '')} Source-family tags: {', '.join(tags)}.".strip()
        output.append(row)
    return sorted(output, key=lambda item: (item.get("source_family", ""), item.get("item_title", "")))


def read_registry() -> pd.DataFrame:
    registry = pd.read_csv(REGISTRY_PATH, dtype=str).fillna("")
    for column in REGISTRY_EXTRA_COLUMNS:
        if column not in registry.columns:
            registry[column] = ""
    return registry


def upsert_registry(registry: pd.DataFrame, sources: list[CandidateSource], validation_rows: list[dict[str, str]], source_ids: dict[str, str]) -> pd.DataFrame:
    validation_by_url = {source_key(row["candidate_url"]): row for row in validation_rows}
    output = registry.copy()
    for source in sources:
        key = source_key(source.url)
        source_id = source_ids[key]
        validation = validation_by_url.get(key, {})
        idx = output.index[output["source_id"].astype(str).eq(source_id)].tolist()
        collection_method = clean(validation.get("collector_capability", "manual"))
        if collection_method == "static_scrape":
            active = "True"
        elif collection_method == "browser_required":
            active = "True"
        else:
            active = "False"
        extraction_mode = source.proposed_extraction_mode
        if extraction_mode == "browser_required":
            extraction_mode = "weekly_development"
        mvp_active = "True" if validation.get("mvp_ready") == "True" else "False"
        row = {
            "source_id": source_id,
            "tier": "Tier 1",
            "institution_id": MASTERCARD_ID,
            "institution_name": MASTERCARD_NAME,
            "source_name": source.source_name,
            "source_type": source.source_type,
            "url": source.url,
            "collection_method": collection_method,
            "update_frequency": "Weekly",
            "reliability_level": "Yüksek",
            "strategic_themes": source.strategic_themes,
            "active": active,
            "notes": f"{source.notes} {validation.get('reason', '')}".strip(),
            "extraction_mode": extraction_mode,
            "coverage_scope": COVERAGE_SCOPE,
            "coverage_priority": "Kritik",
            "sme_relevance": "Yüksek",
            "source_validation_status": validation.get("validation_result", "not_checked"),
            "collector_capability": collection_method,
            "mvp_active": mvp_active,
            "claude_eligible": "False",
            "mvp_status": "Blocked: browser collector required" if collection_method == "browser_required" else ("Benchmark only" if extraction_mode == "benchmark_fact" else "Not ready"),
            "customer_segment": "Kart / Ödeme Altyapısı / Ticari Ödemeler",
            "institution_group": INSTITUTION_GROUP,
            "display_name": MASTERCARD_NAME,
            "legal_name": "Mastercard",
            "exclusion_reason": "" if active == "True" else validation.get("reason", ""),
            "last_validated_at": validation.get("checked_at", ""),
            "institution_type": INSTITUTION_TYPE,
            "strategic_partner_priority": STRATEGIC_PARTNER_PRIORITY,
        }
        if idx:
            for column, value in row.items():
                if column not in output.columns:
                    output[column] = ""
                output.loc[idx[0], column] = value
        else:
            output = pd.concat([output, pd.DataFrame([row])], ignore_index=True)
    mastercard_mask = output["institution_id"].astype(str).eq(MASTERCARD_ID)
    output.loc[mastercard_mask, "institution_type"] = INSTITUTION_TYPE
    output.loc[mastercard_mask, "strategic_partner_priority"] = STRATEGIC_PARTNER_PRIORITY
    output.loc[mastercard_mask, "coverage_scope"] = COVERAGE_SCOPE
    output.loc[mastercard_mask, "institution_group"] = INSTITUTION_GROUP
    output.loc[mastercard_mask, "claude_eligible"] = "False"
    return output


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def cluster_preview(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    clusters = {
        "Mastercard Agentic Commerce Stack": [],
        "Mastercard Tokenization and Digital Credentials": [],
        "Mastercard Fraud, Identity and Authentication": [],
        "Merchant Cloud and Acquiring Infrastructure": [],
        "B2B Virtual Cards and Payment Automation": [],
        "Mastercard SME Enablement": [],
        "Türkiye Bank Deployments": [],
        "Cross-Border and Multi-Rail Payments": [],
        "Open Finance and Data": [],
    }
    for row in rows:
        if row.get("accepted") != "True":
            continue
        title = row["item_title"]
        layer = row.get("network_layer", "")
        signal = row.get("network_signal_type", "")
        if "Agentic" in layer:
            clusters["Mastercard Agentic Commerce Stack"].append(title)
        if "Tokenizasyon" in layer or "Kimlik" in layer:
            clusters["Mastercard Tokenization and Digital Credentials"].append(title)
        if "Fraud" in layer or "Güvenlik" in layer:
            clusters["Mastercard Fraud, Identity and Authentication"].append(title)
        if "Merchant" in layer or "Kabul" in layer:
            clusters["Merchant Cloud and Acquiring Infrastructure"].append(title)
        if "Ticari Kartlar" in layer or "B2B" in layer or "Sanal" in layer:
            clusters["B2B Virtual Cards and Payment Automation"].append(title)
        if "SME" in layer:
            clusters["Mastercard SME Enablement"].append(title)
        if "Türkiye" in signal:
            clusters["Türkiye Bank Deployments"].append(title)
        if "Çoklu" in layer or "Sınır" in layer:
            clusters["Cross-Border and Multi-Rail Payments"].append(title)
        if "Veri" in layer or "Açık Finans" in layer:
            clusters["Open Finance and Data"].append(title)
    return {key: values for key, values in clusters.items() if values}


def write_report(validation_rows: list[dict[str, str]], inspection_rows: list[dict[str, str]], checked_at: str) -> Path:
    stamp = checked_at.replace(":", "").replace("-", "")[:15]
    report_path = DATA_DIR / f"mastercard_candidate_quality_report_{stamp}.md"
    total_links = sum(int(row.get("item_level_link_count", "0") or 0) for row in validation_rows)
    post_cutoff = sum(1 for row in inspection_rows if is_post_cutoff(row.get("recency_basis_date", "")))
    accepted = [row for row in inspection_rows if row.get("accepted") == "True"]
    rejected = [row for row in inspection_rows if row.get("accepted") != "True"]
    browser_required = [row for row in validation_rows if row.get("collector_capability") == "browser_required"]
    benchmark = [row for row in validation_rows if row.get("benchmark_ready") == "True"]
    clusters = cluster_preview(inspection_rows)
    lines = [
        "# Mastercard Candidate Quality Report",
        "",
        f"Checked at: `{checked_at}`",
        "",
        "## Source Access",
        f"- Working static sources: {sum(1 for row in validation_rows if row.get('collector_capability') == 'static_scrape')}",
        f"- Browser-required sources: {len(browser_required)}",
        f"- 403 sources: {sum(1 for row in validation_rows if row.get('http_status') == '403')}",
        f"- Manual sources: {sum(1 for row in validation_rows if row.get('collector_capability') == 'manual')}",
        f"- Invalid/unsupported sources: {sum(1 for row in validation_rows if row.get('collector_capability') == 'unsupported')}",
        "- Canonical redirects captured in `final_url`.",
        "",
        "## Coverage",
    ]
    for family in sorted({row["source_family"] for row in validation_rows}):
        families = [row for row in validation_rows if row["source_family"] == family]
        capability = ", ".join(sorted({row["collector_capability"] for row in families}))
        lines.append(f"- {family}: {capability}")
    lines.extend(
        [
            "",
            "## Candidate Results",
            f"- Total links: {total_links}",
            f"- Item-level candidates: {len(inspection_rows)}",
            f"- Post-cutoff dry-run/inspection candidates: {post_cutoff}",
            f"- Direct Akbank signals: {sum(1 for row in inspection_rows if row.get('direct_akbank_signal') == 'True')}",
            f"- Turkish competitor deployments: {sum(1 for row in inspection_rows if row.get('network_signal_type') == 'Türkiye Rakip Banka Uygulaması')}",
            f"- Türkiye ecosystem signals: {sum(1 for row in inspection_rows if row.get('network_signal_type') == 'Türkiye Ödeme Ekosistemi Sinyali')}",
            f"- EEMEA deployments: {sum(1 for row in inspection_rows if row.get('network_signal_type') == 'EEMEA Uygulaması')}",
            f"- Global capability/platform launches: {sum(1 for row in inspection_rows if row.get('network_signal_type') in {'Aktarılabilir Mastercard Kabiliyeti', 'Global Ödeme Teknolojisi Yönü'})}",
            f"- Awards / management awareness: {sum(1 for row in inspection_rows if row.get('content_role') == 'Yönetici Bilgilendirme')}",
            f"- Research/context: {sum(1 for row in inspection_rows if row.get('content_role') == 'Bağlamsal Veri')}",
            f"- Rejected PR/noise: {len(rejected)}",
            "- Duplicates: dry-run only; no production item written.",
            "",
            "## Strategic Assessment",
        ]
    )
    for row in sorted(accepted, key=lambda item: int(item.get("strategic_priority_score", "0") or 0), reverse=True)[:10]:
        lines.append(f"- {row['item_title']} | score {row['strategic_priority_score']} | {row['network_signal_type']} | {row['proposed_destination']}")
    lines.extend(
        [
            "",
            "Immediate Akbank implications: Mastercard item-level official pages require a browser collector before reliable publication-date and detail extraction. Commercial-card, merchant acceptance, tokenization and agentic-commerce seeds are strategically relevant but should not enter Claude until rendered extraction is proven.",
            "",
            "## Claude Readiness",
        ]
    )
    for row in accepted:
        eligible = "no"
        reason = "Browser/static extraction not yet proven for official Mastercard item; `claude_eligible` remains False."
        if row.get("content_role") == "Benchmark Fact":
            reason = "Benchmark/product-root context, not a current recent-development item."
        lines.append(f"- {row['item_title']}: eligible {eligible}; {reason}; lane `{row['proposed_destination']}`; cluster preview pending.")
    lines.extend(["", "## Cluster Preview"])
    if clusters:
        for cluster, items in clusters.items():
            lines.append(f"- {cluster}: {len(items)} item(s); lead: {items[0]}")
    else:
        lines.append("- No clusters from current extracted rows; browser collection needed for item-level clusters.")
    lines.extend(
        [
            "",
            "## Pilot Recommendation",
            "- Do not run Claude yet.",
            "- Next technical step: add a browser-based Mastercard collector for official newsroom/item pages.",
            "- Tiny pilot after browser extraction: maximum 3 items, prioritizing Agent Pay, Merchant Cloud/acquiring, and tokenization/security.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def run_validation(apply: bool) -> dict[str, object]:
    checked_at = now_iso()
    registry = read_registry()
    existing_by_key = {
        source_key(row["url"]): row["source_id"]
        for _, row in registry[registry["institution_id"].astype(str).eq(MASTERCARD_ID)].iterrows()
    }
    next_id = max(int(str(value).split("-")[1]) for value in registry["source_id"] if str(value).startswith("REG-")) + 1
    sources = mastercard_sources()
    source_ids = {}
    source_lookup = {}
    for source in sources:
        sid, next_id = source_id_for(source, existing_by_key, next_id)
        source_ids[source_key(source.url)] = sid
        source_lookup.setdefault(source.source_family, sid)
    validation_rows = []
    inspection_rows = []
    for source in sources:
        row, rows = validation_row(source, source_ids[source_key(source.url)], checked_at)
        validation_rows.append(row)
        inspection_rows.extend(rows)
    inspection_rows.extend(seeded_inspection_rows(source_lookup))
    inspection_rows = dedupe_inspection_rows(inspection_rows)

    for row in inspection_rows:
        for column in INSPECTION_COLUMNS:
            row.setdefault(column, "")
    write_csv(VALIDATION_PATH, validation_rows, SOURCE_VALIDATION_COLUMNS)
    write_csv(INSPECTION_PATH, inspection_rows, INSPECTION_COLUMNS)
    DISCOVERY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    for family in sorted({row["source_family"] for row in validation_rows}):
        family_rows = [row for row in inspection_rows if row["source_family"] == family]
        log_path = DISCOVERY_LOG_DIR / f"{re.sub(r'[^a-z0-9]+', '_', family.casefold()).strip('_') or 'mastercard'}.log"
        log_lines = [f"DRY RUN ONLY - {family}", f"items={len(family_rows)}"]
        log_lines.extend(f"- {row['item_title']} | {row['item_url']} | accepted={row['accepted']} | score={row['strategic_priority_score']}" for row in family_rows)
        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    full_log = DISCOVERY_LOG_DIR / "full_mastercard.log"
    full_log.write_text("\n".join([f"DRY RUN ONLY - Mastercard full set", f"items={len(inspection_rows)}"] + [f"- {row['source_family']} | {row['item_title']} | accepted={row['accepted']} | score={row['strategic_priority_score']}" for row in inspection_rows]) + "\n", encoding="utf-8")
    report_path = write_report(validation_rows, inspection_rows, checked_at)
    if apply:
        updated = upsert_registry(registry, sources, validation_rows, source_ids)
        updated.to_csv(REGISTRY_PATH, index=False, encoding="utf-8-sig")
    return {
        "validation_rows": validation_rows,
        "inspection_rows": inspection_rows,
        "report_path": report_path,
        "applied": apply,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Mastercard official source readiness without writing recent items.")
    parser.add_argument("--apply", action="store_true", help="Update only Mastercard rows in source_registry.csv.")
    args = parser.parse_args()
    result = run_validation(args.apply)
    validation_rows = result["validation_rows"]
    inspection_rows = result["inspection_rows"]
    print("Mastercard validation complete")
    print(f"sources_tested={len(validation_rows)}")
    print(f"browser_required={sum(1 for row in validation_rows if row.get('collector_capability') == 'browser_required')}")
    print(f"benchmark_ready={sum(1 for row in validation_rows if row.get('benchmark_ready') == 'True')}")
    print(f"inspection_candidates={len(inspection_rows)}")
    print(f"accepted_candidates={sum(1 for row in inspection_rows if row.get('accepted') == 'True')}")
    print(f"rejected_candidates={sum(1 for row in inspection_rows if row.get('accepted') != 'True')}")
    print(f"registry_updated={result['applied']}")
    print(f"validation_csv={VALIDATION_PATH.relative_to(ROOT_DIR)}")
    print(f"inspection_csv={INSPECTION_PATH.relative_to(ROOT_DIR)}")
    print(f"quality_report={Path(result['report_path']).relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
