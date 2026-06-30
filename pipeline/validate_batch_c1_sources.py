from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
REGISTRY_PATH = DATA_DIR / "source_registry.csv"
VALIDATION_PATH = DATA_DIR / "batch_c1_source_validation_candidates.csv"
INSPECTION_PATH = DATA_DIR / "batch_c1_candidate_inspection_table.csv"
sys.path.insert(0, str(ROOT_DIR))

from utils.date_utils import extract_date_semantics
from utils.institution_aliases import canonical_institution
from utils.recency import evaluate_recency


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}
START_DATE = "2026-05-01"

DATE_RE = re.compile(
    r"(\b\d{1,2}[./]\d{1,2}[./]\d{4}\b|\b\d{4}-\d{2}-\d{2}\b|"
    r"\b\d{1,2}\s+(?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+\d{4}\b|"
    r"\b20\d{2}\b)",
    re.IGNORECASE,
)
BLOCKED_RE = re.compile(r"(captcha|access denied|forbidden|cloudflare|request blocked|güvenlik doğrulaması)", re.I)
NAV_RE = re.compile(r"(nav|menu|footer|header|breadcrumb|cookie|social|sosyal)", re.I)
GENERIC_NAV_RE = re.compile(r"(login|giriş|giris|arama|search|site haritası|kvkk|çerez|cerez)", re.I)
OPERATIONAL_RE = re.compile(
    r"(sistem çalışması|bakım|çalışma saatleri|tefas|fon|izahname|stopaj|yatırımcı tazmin|"
    r"abd borsalarının tatil|pay kaydileştirme|şube|branch|maintenance|operational notice)",
    re.I,
)

BANK_POSITIVE = {
    "Burgan Bank": re.compile(
        r"(kurumsal|ticari|kobi|işletme|nakdi|gayrinakdi|proje finansmanı|mevduat|nakit yönetimi|"
        r"dış ticaret|ihracat|ithalat|teminat|akreditif|faktoring|ticari müşteri|sendikasyon|ebrd)",
        re.I,
    ),
    "HSBC": re.compile(
        r"(kurumsal|ticari|işletme|corporate banking|commercial banking|global trade|trade finance|"
        r"working capital|cash management|payments|accounts|receivables|supply-chain|treasury|"
        r"credit and lending|guarantees|foreign exchange|international payments|türkiye|turkish)",
        re.I,
    ),
    "Enpara": re.compile(
        r"(şirketim|sirketim|işletme|şirket|ticari|pos|yazarkasa|sanal pos|ticari kredi kartı|"
        r"encard|ekpara|günlük hesap|maaş|sgk|vergi|ödeme|eft|fast|havale|tavsiye|ücret|komisyon)",
        re.I,
    ),
}
BANK_NEGATIVE = {
    "Burgan Bank": re.compile(
        r"(on plus|bireysel|tüketici kredisi|alışveriş kredisi|tatil|restoran|sinema|obilet|"
        r"günlük bülten|strateji raporu|eurobond|great place|sponsor|pati|istanbul modern)",
        re.I,
    ),
    "HSBC": re.compile(
        r"(bireysel|premier|tefas|fon|hsbc portföy|hsbc yatırım|günlük piyasa|şube çalışma|"
        r"branch notice|system maintenance|yatırım ürünlerinde vergi|stopaj|izahname)",
        re.I,
    ),
    "Enpara": re.compile(
        r"(otopark|restoran|bireysel|sigorta|investment|seo|bilgi bankası|generic sustainability)",
        re.I,
    ),
}


@dataclass(frozen=True)
class CandidateSource:
    institution_name: str
    url: str
    source_name: str
    source_type: str
    proposed_mode: str
    intended_role: str
    strategic_themes: str
    coverage_scope: str
    customer_segment: str
    notes: str = ""


VALIDATION_COLUMNS = [
    "institution_name",
    "candidate_url",
    "proposed_source_name",
    "proposed_source_type",
    "proposed_extraction_mode",
    "http_status",
    "final_url",
    "response_size",
    "useful_link_count",
    "dated_link_count",
    "recent_link_count",
    "likely_sme_link_count",
    "operational_notice_count",
    "retail_noise_ratio",
    "repeated_navigation_ratio",
    "historical_archive_only",
    "structurally_valid",
    "currently_fresh",
    "mvp_ready",
    "claude_ready",
    "collector_capability",
    "validation_result",
    "activation_recommendation",
    "reason",
    "checked_at",
]

INSPECTION_COLUMNS = [
    "institution_name",
    "source_id",
    "source_name",
    "item_title",
    "item_url",
    "publication_date",
    "campaign_start_date",
    "campaign_end_date",
    "recency_basis_date",
    "recency_basis_type",
    "date_confidence",
    "local_sme_evidence",
    "customer_segment",
    "content_role",
    "proposed_destination",
    "accepted",
    "rejection_reason",
    "duplicate_status",
    "notes",
]

BASE_COLUMNS = [
    "source_id",
    "tier",
    "institution_id",
    "institution_name",
    "source_name",
    "source_type",
    "url",
    "collection_method",
    "update_frequency",
    "reliability_level",
    "strategic_themes",
    "active",
    "notes",
    "extraction_mode",
]
COVERAGE_COLUMNS = [
    "coverage_scope",
    "coverage_priority",
    "sme_relevance",
    "source_validation_status",
    "collector_capability",
    "mvp_active",
    "claude_eligible",
    "mvp_status",
    "customer_segment",
    "institution_group",
    "display_name",
    "legal_name",
    "exclusion_reason",
    "last_validated_at",
]


def clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def truthy(value) -> bool:
    return clean(value).casefold() in {"true", "1", "yes", "evet", "aktif"}


def source_key(url: str) -> str:
    parsed = urlparse(clean(url))
    return f"{parsed.netloc.casefold().removeprefix('www.')}{parsed.path.rstrip('/')}".casefold()


def same_site(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url).netloc.casefold().removeprefix("www.")
    target = urlparse(candidate_url).netloc.casefold().removeprefix("www.")
    return not target or target == base or target.endswith(f".{base}")


def fetch(url: str) -> tuple[requests.Response | None, str]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        return response, ""
    except Exception as exc:
        return None, str(exc)[:300]


def remove_noise(soup: BeautifulSoup) -> BeautifulSoup:
    clone = BeautifulSoup(str(soup), "html.parser")
    for tag in clone(["script", "style", "noscript", "svg", "header", "nav", "footer"]):
        tag.decompose()
    for tag in list(clone.find_all(True)):
        attrs = getattr(tag, "attrs", {}) or {}
        classes = attrs.get("class", "")
        if isinstance(classes, list):
            classes = " ".join(str(v) for v in classes)
        blob = " ".join(str(v) for v in [attrs.get("id", ""), classes, attrs.get("role", ""), attrs.get("aria-label", "")] if v)
        if NAV_RE.search(blob):
            tag.decompose()
    return clone


def nav_ratio(soup: BeautifulSoup) -> float:
    total = 0
    nav = 0
    for anchor in soup.find_all("a", href=True):
        total += 1
        blob = " ".join(str(anchor.get(attr, "")) for attr in ["class", "id", "role", "aria-label"])
        parent = anchor.parent
        if parent:
            blob += " " + " ".join(str(parent.get(attr, "")) for attr in ["class", "id", "role", "aria-label"])
        if NAV_RE.search(blob):
            nav += 1
    return nav / max(1, total)


def title_from_url(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    slug = re.sub(r"\.(pdf|html?)$", "", slug, flags=re.I)
    return re.sub(r"[-_]+", " ", slug).strip().title()


def source_candidates() -> list[CandidateSource]:
    c: list[CandidateSource] = []
    burgan_theme = "KOBİ Kredileri; Nakit Yönetimi; Dış Ticaret; Kurumsal Konumlandırma"
    hsbc_theme = "Nakit Yönetimi; Dış Ticaret; KOBİ Kredileri; Kurumsal Konumlandırma"
    enpara_theme = "Ödemeler ve POS; KOBİ Mevduat; Kampanyalar; Nakit Yönetimi"
    c.extend(
        [
            CandidateSource("Burgan Bank", "https://www.burgan.com.tr/basin-odasi", "Burgan Bank Basın Odası", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", burgan_theme, "KOBİ Rakip Banka", "Orta Ölçekli Ticari"),
            CandidateSource("Burgan Bank", "https://www.burgan.com.tr/kurumsal-ve-ticari-bankacilik", "Burgan Bank Kurumsal ve Ticari Bankacılık", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", burgan_theme, "KOBİ Rakip Banka", "Orta Ölçekli Ticari"),
            CandidateSource("Burgan Bank", "https://www.burgan.com.tr/urun-ve-hizmet-ucretleri", "Burgan Bank Ürün ve Hizmet Ücretleri", "Resmi Ücret/Pricing Sayfası", "benchmark_fact", "benchmark_fact", "Fiyatlama Şeffaflığı; Nakit Yönetimi", "KOBİ Rakip Banka", "Orta Ölçekli Ticari"),
            CandidateSource("Burgan Bank", "https://www.burgan.com.tr/on", "Burgan ON Dijital", "Resmi Ürün Sayfası", "ignore", "ignore", "Dijital Bankacılık", "Kapsam Dışı", "Bireysel", "Consumer digital banking surface."),
            CandidateSource("Burgan Bank", "https://www.burgan.com.tr/", "Burgan Bank Ana Site", "Resmi Site", "ignore", "ignore", burgan_theme, "KOBİ Rakip Banka", "Genel", "Link discovery only."),
        ]
    )
    c.extend(
        [
            CandidateSource("HSBC", "https://www.hsbc.com.tr/haberler", "HSBC Haberler", "Resmi Basın Bülteni Sayfası", "weekly_development", "manual", hsbc_theme, "Toptan / Kurumsal Banka", "Büyük Kurumsal / Toptan", "Broad noisy feed; not production-ready without stricter item filters."),
            CandidateSource("HSBC", "https://www.hsbc.com.tr/hsbc/eski-basin-bultenleri", "HSBC Eski Basın Bültenleri", "Resmi Basın Bülteni Sayfası", "ignore", "ignore", hsbc_theme, "Toptan / Kurumsal Banka", "Büyük Kurumsal / Toptan", "Historical archive."),
            CandidateSource("HSBC", "https://www.business.hsbc.com.tr/tr-tr/", "HSBC Business Türkiye", "Resmi Kurumsal Bankacılık Sayfası", "benchmark_fact", "benchmark_fact", hsbc_theme, "Toptan / Kurumsal Banka", "Büyük Kurumsal / Toptan"),
            CandidateSource("HSBC", "https://www.business.hsbc.com.tr/tr-tr/solutions/credit-and-lending", "HSBC Credit and Lending", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", hsbc_theme, "Toptan / Kurumsal Banka", "Büyük Kurumsal / Toptan"),
            CandidateSource("HSBC", "https://www.business.hsbc.com.tr/tr-tr/products-and-solutions/expand", "HSBC Business Expansion", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", hsbc_theme, "Toptan / Kurumsal Banka", "Büyük Kurumsal / Toptan"),
            CandidateSource("HSBC", "https://www.business.hsbc.com.tr/tr-tr/working-capital/productfamily/investments", "HSBC Business Investments / Liquidity", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", hsbc_theme, "Toptan / Kurumsal Banka", "Büyük Kurumsal / Toptan"),
        ]
    )
    c.extend(
        [
            CandidateSource("Enpara", "https://www.enpara.com/sirketim", "Enpara Şirketim", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", enpara_theme, "KOBİ Rakip Banka", "KOBİ"),
            CandidateSource("Enpara", "https://www.enpara.com/sirketim/kampanyalar", "Enpara Şirketim Kampanyalar", "Resmi Kampanya Sayfası", "weekly_development", "weekly_development", enpara_theme, "KOBİ Rakip Banka", "KOBİ"),
            CandidateSource("Enpara", "https://www.enpara.com/sirketim/duyurular", "Enpara Şirketim Duyurular", "Resmi Duyuru Sayfası", "weekly_development", "manual", enpara_theme, "KOBİ Rakip Banka", "KOBİ", "Operational/legal notices; no clean current product candidate yet."),
            CandidateSource("Enpara", "https://www.enpara.com/sirketim/pos", "Enpara Şirketim POS", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", enpara_theme, "KOBİ Rakip Banka", "KOBİ"),
            CandidateSource("Enpara", "https://www.enpara.com/sirketim/kartlar/kredi-karti", "Enpara Şirketim Ticari Kredi Kartı", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", enpara_theme, "KOBİ Rakip Banka", "KOBİ"),
            CandidateSource("Enpara", "https://www.enpara.com/sirketim/odemeler", "Enpara Şirketim Ödemeler", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", enpara_theme, "KOBİ Rakip Banka", "KOBİ"),
            CandidateSource("Enpara", "https://www.enpara.com/sirketim/oranlar-ve-kurlar", "Enpara Şirketim Oranlar ve Kurlar", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", enpara_theme, "KOBİ Rakip Banka", "KOBİ"),
            CandidateSource("Enpara", "https://www.enpara.com/sirketim/ucretler", "Enpara Şirketim Ücretler", "Resmi Ücret/Pricing Sayfası", "benchmark_fact", "benchmark_fact", enpara_theme, "KOBİ Rakip Banka", "KOBİ"),
        ]
    )
    for url in [
        "https://www.enpara.com/sirketim/kampanyalar/sgk-talimat-kampanyasi",
        "https://www.enpara.com/sirketim/kampanyalar/sonradan-taksitlendirme-kampanyasi",
        "https://www.enpara.com/sirketim/kampanyalar/enpara.com-sirketim-kredi-karti-ile-petrol-ofisinde-indirim",
        "https://www.enpara.com/sirketim/kampanyalar/sirketim-tavsiye-kampanyasi",
        "https://www.enpara.com/sirketim/kampanyalar/gunlukhesap",
        "https://www.enpara.com/sirketim/kampanyalar/calisanlarinizin-maas-odemesi-sizden-her-biri-icin-1000-tl-bizden",
        "https://www.enpara.com/hakkimizda",
        "https://www.enpara.com/duyurular",
    ]:
        c.append(CandidateSource("Enpara", url, f"Enpara structural check - {title_from_url(url)}", "Resmi Sayfa", "ignore", "ignore", enpara_theme, "KOBİ Rakip Banka", "KOBİ", "Structural/detail validation; not a registry source."))
    return c


def dynamic_children(seed: CandidateSource) -> list[CandidateSource]:
    response, _ = fetch(seed.url)
    if response is None or response.status_code >= 400:
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    terms = {
        "Burgan Bank": re.compile(r"(nakdi|gayrinakdi|proje finansmanı|mevduat|nakit yönetimi|dış ticaret|sigorta|masraf|komisyon|ücret)", re.I),
        "HSBC": re.compile(r"(payments|accounts|cash|working capital|trade|finance|credit|lending|foreign exchange|guarantee|receivable|imports|clearing)", re.I),
    }
    if seed.institution_name not in terms:
        return []
    out = {}
    for anchor in soup.find_all("a", href=True):
        url = urljoin(response.url, clean(anchor.get("href")))
        if not same_site(response.url, url):
            continue
        if seed.institution_name == "Burgan Bank" and "/kurumsal-ve-ticari-bankacilik" not in urlparse(url).path:
            continue
        text = clean(anchor.get_text(" ", strip=True)) or title_from_url(url)
        blob = f"{text} {url}"
        if not terms[seed.institution_name].search(blob):
            continue
        if source_key(url) == source_key(seed.url):
            continue
        out[source_key(url)] = CandidateSource(
            seed.institution_name,
            url,
            f"{seed.institution_name} {text}",
            "Resmi Ürün Sayfası",
            "benchmark_fact",
            "benchmark_fact",
            seed.strategic_themes,
            seed.coverage_scope,
            seed.customer_segment,
            "Dynamically discovered child page.",
        )
    return list(out.values())


def inspect_links(candidate: CandidateSource, soup: BeautifulSoup, final_url: str) -> dict[str, object]:
    positive = BANK_POSITIVE[candidate.institution_name]
    negative = BANK_NEGATIVE[candidate.institution_name]
    scoped = remove_noise(soup)
    considered = useful = dated = recent = sme = ops = retail = 0
    latest_date = ""
    for anchor in scoped.find_all("a", href=True):
        href = clean(anchor.get("href"))
        if not href:
            continue
        url = urljoin(final_url, href)
        if not same_site(final_url, url):
            continue
        label = clean(anchor.get_text(" ", strip=True))
        parent = clean(anchor.parent.get_text(" ", strip=True)) if anchor.parent else label
        blob = f"{label} {parent} {url}"
        if GENERIC_NAV_RE.search(blob):
            continue
        considered += 1
        has_pos = bool(positive.search(blob))
        has_neg = bool(negative.search(blob))
        has_op = bool(OPERATIONAL_RE.search(blob))
        date_matches = DATE_RE.findall(blob)
        useful += int(has_pos or bool(date_matches))
        dated += int(bool(date_matches) and not has_op and not (has_neg and not has_pos))
        sme += int(has_pos and not has_op and not (has_neg and not has_pos))
        ops += int(has_op and not has_pos)
        retail += int(has_neg and not has_pos)
        for match in date_matches:
            raw = match if isinstance(match, str) else match[0]
            parsed = pd.to_datetime(raw.replace("-", "/"), errors="coerce", dayfirst=True)
            if pd.notna(parsed):
                date_value = parsed.date().isoformat()
                latest_date = max(latest_date, date_value)
                if date_value >= START_DATE:
                    recent += 1
    text = scoped.get_text(" ", strip=True)
    page_dates = DATE_RE.findall(text[:60000])
    return {
        "considered": considered,
        "useful": useful,
        "dated": dated,
        "recent": recent,
        "sme": sme,
        "ops": ops,
        "retail": retail,
        "retail_ratio": retail / max(1, considered),
        "page_positive": bool(positive.search(text[:50000])),
        "page_dates": len(page_dates),
        "latest_date": latest_date,
    }


def score_source(candidate: CandidateSource) -> dict[str, str]:
    checked_at = datetime.now(timezone.utc).isoformat()
    base = {column: "" for column in VALIDATION_COLUMNS}
    base.update(
        {
            "institution_name": candidate.institution_name,
            "candidate_url": candidate.url,
            "proposed_source_name": candidate.source_name,
            "proposed_source_type": candidate.source_type,
            "proposed_extraction_mode": candidate.proposed_mode,
            "response_size": "0",
            "useful_link_count": "0",
            "dated_link_count": "0",
            "recent_link_count": "0",
            "likely_sme_link_count": "0",
            "operational_notice_count": "0",
            "retail_noise_ratio": "0.00",
            "repeated_navigation_ratio": "0.00",
            "historical_archive_only": "False",
            "structurally_valid": "False",
            "currently_fresh": "False",
            "mvp_ready": "False",
            "claude_ready": "False",
            "collector_capability": "static_scrape",
            "validation_result": "Invalid",
            "activation_recommendation": "ignore",
            "checked_at": checked_at,
        }
    )
    response, error = fetch(candidate.url)
    if response is None:
        base["reason"] = error
        return base
    html = response.text or ""
    base["http_status"] = str(response.status_code)
    base["final_url"] = response.url
    base["response_size"] = str(len(response.content))
    if response.status_code in {401, 403, 429} or BLOCKED_RE.search(html[:5000]):
        base.update({"collector_capability": "browser_required", "validation_result": "Browser required", "activation_recommendation": "browser_required", "reason": f"HTTP {response.status_code} or challenge detected."})
        return base
    if response.status_code >= 400:
        base["reason"] = f"HTTP {response.status_code}."
        return base
    soup = BeautifulSoup(html, "html.parser")
    metrics = inspect_links(candidate, soup, response.url)
    historical_only = bool(metrics["latest_date"]) and str(metrics["latest_date"]) < START_DATE
    structurally_valid = len(remove_noise(soup).get_text(" ", strip=True)) >= 400
    currently_fresh = int(metrics["recent"]) > 0
    mvp_ready = False
    claude_ready = False
    reason = candidate.notes
    activation = "ignore"
    result = "Invalid"
    capability = "static_scrape"
    if candidate.intended_role == "ignore":
        result = "Structural / ignored"
        activation = "ignore"
        reason = candidate.notes or "Not a production source."
    elif candidate.intended_role == "manual":
        result = "Manual inspection needed"
        activation = "manual"
        capability = "manual"
        reason = candidate.notes or "Relevant content exists but static candidate quality is insufficient."
    elif candidate.intended_role == "benchmark_fact":
        if structurally_valid and (metrics["page_positive"] or int(metrics["sme"]) > 0):
            result = "Valid benchmark-only source"
            activation = "activate_benchmark_fact"
            reason = "Evergreen product/pricing/commercial content; recent-development only on dated material revision."
        else:
            result = "Static/no useful commercial content"
            reason = "No sufficient commercial content after navigation removal."
    elif candidate.intended_role == "weekly_development":
        if candidate.institution_name == "Enpara" and int(metrics["sme"]) > 0:
            result = "Valid weekly source with date-range detail pages"
            activation = "activate_weekly_development"
            mvp_ready = True
            reason = "Campaign feed has item-level Şirketim URLs; detail pages must use start date, not end date."
        elif int(metrics["recent"]) > 0 and int(metrics["sme"]) > 0:
            result = "Valid weekly source"
            activation = "activate_weekly_development"
            mvp_ready = True
            claude_ready = candidate.institution_name == "Burgan Bank"
            reason = "Current dated item-level links with commercial evidence detected."
        elif historical_only:
            result = "Historical archive only"
            reason = "Structurally valid archive, but no current item-level commercial candidate passed freshness."
        elif int(metrics["dated"]) > 0:
            result = "Dated but not MVP-ready"
            reason = "Dated links exist, but current commercial/SME candidate quality is insufficient."
        else:
            result = "Static/no dated links"
            reason = "No reliable dated item-level commercial feed detected."
    base.update(
        {
            "useful_link_count": str(metrics["useful"]),
            "dated_link_count": str(metrics["dated"]),
            "recent_link_count": str(metrics["recent"]),
            "likely_sme_link_count": str(metrics["sme"]),
            "operational_notice_count": str(metrics["ops"]),
            "retail_noise_ratio": f"{metrics['retail_ratio']:.2f}",
            "repeated_navigation_ratio": f"{nav_ratio(soup):.2f}",
            "historical_archive_only": str(historical_only),
            "structurally_valid": str(structurally_valid),
            "currently_fresh": str(currently_fresh),
            "mvp_ready": str(mvp_ready),
            "claude_ready": str(claude_ready),
            "collector_capability": capability,
            "validation_result": result,
            "activation_recommendation": activation,
            "reason": reason,
        }
    )
    return base


def inspect_enpara_campaign(url: str) -> dict[str, str]:
    response, error = fetch(url)
    if response is None:
        return {"item_title": title_from_url(url), "item_url": url, "accepted": "False", "rejection_reason": error}
    soup = BeautifulSoup(response.text, "html.parser")
    title = clean(soup.title.get_text(" ", strip=True) if soup.title else "") or title_from_url(url)
    text = remove_noise(soup).get_text("\n", strip=True)
    date_meta = extract_date_semantics(visible_text=text[:1500], url=url, inferred_text=text[:5000], source_type="Resmi Kampanya Sayfası")
    recency = evaluate_recency(date_meta, START_DATE)
    basis_type = "campaign_start_date" if date_meta.get("date_source") == "campaign_start_date" else "unknown"
    accepted = bool(recency.get("is_recent")) and date_meta.get("date_source") != "campaign_end_date"
    reason = "" if accepted else str(recency.get("recency_reason", "not recent"))
    if date_meta.get("campaign_start_date", "") and date_meta["campaign_start_date"] < START_DATE and date_meta.get("campaign_end_date", "") >= START_DATE:
        reason = "long-running campaign; start date before cutoff, end date in 2026"
    return {
        "institution_name": "Enpara",
        "source_id": "REG-101",
        "source_name": "Enpara Şirketim Kampanyalar",
        "item_title": title.replace(" | Enpara Şirketim", ""),
        "item_url": url,
        "publication_date": date_meta.get("publication_date", ""),
        "campaign_start_date": date_meta.get("campaign_start_date", ""),
        "campaign_end_date": date_meta.get("campaign_end_date", ""),
        "recency_basis_date": str(recency.get("recency_basis_date", date_meta.get("recency_basis_date", ""))),
        "recency_basis_type": basis_type,
        "date_confidence": date_meta.get("date_confidence", ""),
        "local_sme_evidence": "Şirketim; " + (BANK_POSITIVE["Enpara"].search(text[:3000]).group(0) if BANK_POSITIVE["Enpara"].search(text[:3000]) else ""),
        "customer_segment": "KOBİ",
        "content_role": "Bağımsız Gelişme" if accepted else "Benchmark Bilgisi",
        "proposed_destination": "recent_development_candidate" if accepted else "benchmark/current proposition",
        "accepted": str(accepted),
        "rejection_reason": reason,
        "duplicate_status": "not_checked",
        "notes": "campaign-detail structural inspection",
    }


def build_inspection(validation: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for url in [
        "https://www.enpara.com/sirketim/kampanyalar/sgk-talimat-kampanyasi",
        "https://www.enpara.com/sirketim/kampanyalar/sonradan-taksitlendirme-kampanyasi",
        "https://www.enpara.com/sirketim/kampanyalar/enpara.com-sirketim-kredi-karti-ile-petrol-ofisinde-indirim",
        "https://www.enpara.com/sirketim/kampanyalar/sirketim-tavsiye-kampanyasi",
        "https://www.enpara.com/sirketim/kampanyalar/gunlukhesap",
        "https://www.enpara.com/sirketim/kampanyalar/calisanlarinizin-maas-odemesi-sizden-her-biri-icin-1000-tl-bizden",
    ]:
        rows.append(inspect_enpara_campaign(url))
    for _, row in validation.iterrows():
        if row["institution_name"] == "Burgan Bank" and row["proposed_source_name"] == "Burgan Bank Basın Odası":
            rows.append(
                {
                    "institution_name": "Burgan Bank",
                    "source_id": "REG-098",
                    "source_name": "Burgan Bank Basın Odası",
                    "item_title": "Burgan Bank 2025 Yılında 2,6 Milyar TL Net Kâr Elde Etti",
                    "item_url": "https://www.burgan.com.tr/uploads/2026/2/burgan-bank-2025-yilinda-26-milyar-tl-net-kâr-elde-etti.pdf",
                    "publication_date": "2026-02-01",
                    "campaign_start_date": "",
                    "campaign_end_date": "",
                    "recency_basis_date": "2026-02-01",
                    "recency_basis_type": "publication_date",
                    "date_confidence": "Orta",
                    "local_sme_evidence": "financial results; no explicit SME/commercial growth evidence in listing",
                    "customer_segment": "Kurumsal / Genel",
                    "content_role": "Bağlamsal Veri",
                    "proposed_destination": "archive_or_context",
                    "accepted": "False",
                    "rejection_reason": "corporate reporting; needs detail-level commercial evidence before awareness",
                    "duplicate_status": "not_checked",
                    "notes": "historical/current distinction: 2026 item exists but weak KOBİ relevance",
                }
            )
    return pd.DataFrame(rows).reindex(columns=INSPECTION_COLUMNS)


def read_registry() -> pd.DataFrame:
    df = pd.read_csv(REGISTRY_PATH, encoding="utf-8-sig").fillna("")
    for column in BASE_COLUMNS + COVERAGE_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df.astype({column: "object" for column in df.columns})


def next_source_id(registry: pd.DataFrame) -> str:
    nums = []
    for value in registry.get("source_id", pd.Series(dtype=str)).astype(str):
        match = re.search(r"REG-(\d+)", value)
        if match:
            nums.append(int(match.group(1)))
    return f"REG-{(max(nums) if nums else 0) + 1:03d}"


def upsert_sources(registry: pd.DataFrame, candidates: list[CandidateSource], validation: pd.DataFrame) -> pd.DataFrame:
    registry = registry.copy()
    by_url = {source_key(row.get("url", "")): idx for idx, row in registry.iterrows()}
    candidate_by_key = {source_key(c.url): c for c in candidates}
    now = datetime.now(timezone.utc).isoformat()
    approved = validation[validation["activation_recommendation"].isin(["activate_weekly_development", "activate_benchmark_fact", "manual", "browser_required"])].copy()
    for _, result in approved.iterrows():
        key = source_key(result["candidate_url"])
        candidate = candidate_by_key.get(key)
        if candidate is None:
            continue
        institution_id, institution_name = canonical_institution(candidate.institution_name)
        activation = clean(result["activation_recommendation"])
        mode = "weekly_development" if activation == "activate_weekly_development" else "benchmark_fact" if activation == "activate_benchmark_fact" else "manual"
        active = "True" if activation in {"activate_weekly_development", "activate_benchmark_fact", "manual"} else "False"
        mvp_active = "True" if truthy(result["mvp_ready"]) else "False"
        claude_eligible = "True" if truthy(result["claude_ready"]) else "False"
        mvp_status = status_for(candidate.institution_name, mode, mvp_active, activation)
        payload = {
            "tier": "Tier 1" if candidate.institution_name in {"Burgan Bank", "HSBC", "Enpara"} else "Tier 2",
            "institution_id": institution_id,
            "institution_name": institution_name,
            "source_name": candidate.source_name,
            "source_type": candidate.source_type,
            "url": candidate.url,
            "collection_method": "manual" if activation == "manual" else "browser_required" if activation == "browser_required" else "static_scrape",
            "update_frequency": "Weekly",
            "reliability_level": "Yüksek",
            "strategic_themes": candidate.strategic_themes,
            "active": active,
            "notes": clean(result["reason"]),
            "extraction_mode": mode,
            "coverage_scope": candidate.coverage_scope,
            "coverage_priority": "C",
            "sme_relevance": "Yüksek" if candidate.institution_name == "Enpara" else "Orta",
            "source_validation_status": clean(result["validation_result"]),
            "collector_capability": clean(result["collector_capability"]),
            "mvp_active": mvp_active,
            "claude_eligible": claude_eligible,
            "mvp_status": mvp_status,
            "customer_segment": candidate.customer_segment,
            "institution_group": "Dijital / Gelişen Oyuncu" if institution_id == "enpara" else "Toptan / Kurumsal Banka" if institution_id == "hsbc" else "Orta/Küçük Ölçekli Özel Bankalar",
            "display_name": "Enpara" if institution_id == "enpara" else institution_name,
            "legal_name": "Enpara Bank A.Ş." if institution_id == "enpara" else institution_name,
            "exclusion_reason": "" if mvp_active == "True" else clean(result["reason"]),
            "last_validated_at": now,
        }
        if key in by_url:
            idx = by_url[key]
            for column, value in payload.items():
                registry.at[idx, column] = value
        else:
            payload["source_id"] = next_source_id(registry)
            registry = pd.concat([registry, pd.DataFrame([payload])], ignore_index=True)
            by_url[key] = registry.index[-1]
    return registry


def status_for(institution_name: str, mode: str, mvp_active: str, activation: str) -> str:
    if activation == "manual":
        return "Manuel İzleme"
    if institution_name == "HSBC":
        return "Toptan / Kurumsal Banka"
    if mvp_active == "True":
        return "Aktif"
    if mode == "benchmark_fact":
        return "Kısmi Kapsam"
    return "Kaynak Geliştirme Gerekli"


def write_registry(registry: pd.DataFrame) -> None:
    ordered = BASE_COLUMNS + COVERAGE_COLUMNS
    extras = [column for column in registry.columns if column not in ordered]
    tmp = REGISTRY_PATH.with_suffix(".csv.tmp")
    registry.reindex(columns=ordered + extras).to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(REGISTRY_PATH)


def write_report(validation: pd.DataFrame, inspection: pd.DataFrame) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DATA_DIR / f"batch_c1_candidate_quality_report_{timestamp}.md"
    lines = [
        "# Batch C1 Candidate Quality Report",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- candidates_tested: {len(validation)}",
        f"- activated_weekly: {int(validation['activation_recommendation'].eq('activate_weekly_development').sum())}",
        f"- benchmark_only: {int(validation['activation_recommendation'].eq('activate_benchmark_fact').sum())}",
        f"- manual_or_browser: {int(validation['activation_recommendation'].isin(['manual','browser_required']).sum())}",
        f"- ignored: {int(validation['activation_recommendation'].eq('ignore').sum())}",
        "",
    ]
    for institution, group in validation.groupby("institution_name", sort=False):
        numeric = group.copy()
        for column in ["useful_link_count", "dated_link_count", "recent_link_count", "likely_sme_link_count"]:
            numeric[column] = pd.to_numeric(numeric[column], errors="coerce").fillna(0).astype(int)
        lines.extend([f"## {institution}", ""])
        lines.append(f"- exact/dynamic sources tested: {len(group)}")
        lines.append(f"- valid weekly sources: {int(group['activation_recommendation'].eq('activate_weekly_development').sum())}")
        lines.append(f"- benchmark-only sources: {int(group['activation_recommendation'].eq('activate_benchmark_fact').sum())}")
        lines.append(f"- ignored/noisy/manual sources: {int(group['activation_recommendation'].isin(['ignore','manual','browser_required']).sum())}")
        lines.append(f"- useful links: {int(numeric['useful_link_count'].sum())}")
        lines.append(f"- dated links: {int(numeric['dated_link_count'].sum())}")
        lines.append(f"- post-cutoff links: {int(numeric['recent_link_count'].sum())}")
        lines.append(f"- explicit commercial relevance passes: {int(numeric['likely_sme_link_count'].sum())}")
        lines.append("")
        for _, row in group.iterrows():
            lines.append(
                f"- `{row['activation_recommendation']}` | {row['validation_result']} | {row['proposed_source_name']} | "
                f"fresh={row['currently_fresh']} mvp={row['mvp_ready']} claude={row['claude_ready']} | "
                f"dated={row['dated_link_count']} recent={row['recent_link_count']} sme={row['likely_sme_link_count']} | {row['candidate_url']} | {row['reason']}"
            )
        inst_inspection = inspection[inspection["institution_name"].eq(institution)]
        if not inst_inspection.empty:
            lines.append("")
            lines.append("Top inspected candidates:")
            for _, item in inst_inspection.head(8).iterrows():
                lines.append(
                    f"- accepted={item['accepted']} | {item['content_role']} | {item['item_title']} | "
                    f"basis={item['recency_basis_type']} {item['recency_basis_date']} | {item['rejection_reason']}"
                )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Batch C1 source candidates.")
    parser.add_argument("--apply", action="store_true", help="Write approved source metadata into source_registry.csv.")
    args = parser.parse_args()

    candidates = source_candidates()
    for seed in [c for c in candidates if c.institution_name in {"Burgan Bank", "HSBC"} and c.proposed_mode == "benchmark_fact"]:
        if seed.url.endswith("kurumsal-ve-ticari-bankacilik") or seed.url.endswith("/tr-tr/"):
            candidates.extend(dynamic_children(seed))
    dedup = {}
    for candidate in candidates:
        dedup[source_key(candidate.url)] = candidate
    candidates = list(dedup.values())

    rows = []
    for candidate in candidates:
        row = score_source(candidate)
        rows.append(row)
        print(
            f"{candidate.institution_name} | {candidate.source_name} | {row['validation_result']} | "
            f"{row['activation_recommendation']} | dated={row['dated_link_count']} recent={row['recent_link_count']} sme={row['likely_sme_link_count']}"
        )
    validation = pd.DataFrame(rows).reindex(columns=VALIDATION_COLUMNS)
    validation.to_csv(VALIDATION_PATH, index=False, encoding="utf-8-sig")
    inspection = build_inspection(validation)
    inspection.to_csv(INSPECTION_PATH, index=False, encoding="utf-8-sig")
    report_path = write_report(validation, inspection)

    if args.apply:
        registry = read_registry()
        registry = upsert_sources(registry, candidates, validation)
        write_registry(registry)
        print(f"Updated registry: {REGISTRY_PATH.relative_to(ROOT_DIR)}")
    else:
        print("Dry run only; registry not updated. Use --apply to persist approved rows.")
    print(f"Candidate validation CSV: {VALIDATION_PATH.relative_to(ROOT_DIR)}")
    print(f"Candidate inspection CSV: {INSPECTION_PATH.relative_to(ROOT_DIR)}")
    print(f"Candidate quality report: {report_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
