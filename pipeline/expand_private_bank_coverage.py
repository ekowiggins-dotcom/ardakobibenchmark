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
sys.path.insert(0, str(ROOT_DIR))

from utils.institution_aliases import canonical_institution, institution_group


COVERAGE_COLUMNS = [
    "coverage_scope",
    "coverage_priority",
    "sme_relevance",
    "source_validation_status",
    "collector_capability",
    "mvp_active",
    "exclusion_reason",
    "last_validated_at",
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

WEEKLY_SOURCE_TYPES = {
    "Official Press Release Page",
    "Official Campaign Page",
    "Regulator",
    "Industry Association",
    "News Site",
    "Fintech News",
    "Business News",
    "Resmi Basın Bülteni Sayfası",
    "Resmi Kampanya Sayfası",
    "Sektör Birliği",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

DATE_RE = re.compile(
    r"(\b20\d{2}\b|\b\d{1,2}[./-]\d{1,2}[./-]20\d{2}\b|\b\d{1,2}\s+"
    r"(Ocak|Şubat|Subat|Mart|Nisan|Mayıs|Mayis|Haziran|Temmuz|Ağustos|Agustos|Eylül|Eylul|Ekim|Kasım|Kasim|Aralık|Aralik)"
    r"\s+20\d{2}\b)",
    re.I,
)
USEFUL_RE = re.compile(
    r"(kobi|kobı|ticari|işletme|isletme|üye işyeri|uye isyeri|pos|sanal pos|ödeme|odeme|tahsilat|"
    r"kredi|kart|nakit yönetimi|nakit yonetimi|kampanya|duyuru|haber|basın|basin|bülten|bulten|api|"
    r"girişimci|girisimci|finansman|merchant|commercial|sme|small business)",
    re.I,
)
RETAIL_NOISE_RE = re.compile(r"(emekli|maaş|maas|bireysel|alışveriş|alisveris|tatil|sinema|market)", re.I)
BLOCKED_RE = re.compile(r"(captcha|access denied|forbidden|cloudflare|request blocked|güvenlik doğrulaması)", re.I)

VALID_WEEKLY = "Valid weekly source"
VALID_BENCHMARK = "Valid benchmark-only source"
BROWSER_REQUIRED = "Browser required"
MANUAL_SOURCE = "Manual source"
RETAIL_NOISE = "Retail-noise source"
STATIC_NO_DATED = "Static/no dated links"
INVALID = "Invalid"
NOT_CHECKED = "Not checked"


@dataclass(frozen=True)
class SourceCandidate:
    institution_name: str
    source_name: str
    source_type: str
    url: str
    extraction_mode: str
    coverage_priority: str
    sme_relevance: str
    strategic_themes: str
    tier: str = "Tier 1"
    collection_method: str = "static_scrape"
    reliability_level: str = "Yüksek"
    coverage_scope: str = "KOBİ Rakip Banka"
    active: str = "False"
    notes: str = ""
    exclusion_reason: str = ""


@dataclass
class Validation:
    status: str
    collector_capability: str
    active: str
    mvp_active: str
    extraction_mode: str
    exclusion_reason: str
    status_code: str = ""
    content_length: int = 0
    total_links: int = 0
    useful_links: int = 0
    dated_links: int = 0
    final_url: str = ""
    error: str = ""


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


def next_source_id(registry: pd.DataFrame) -> str:
    existing = []
    for value in registry.get("source_id", pd.Series(dtype=str)).astype(str):
        match = re.search(r"REG-(\d+)", value)
        if match:
            existing.append(int(match.group(1)))
    return f"REG-{(max(existing) if existing else 0) + 1:03d}"


def read_registry() -> pd.DataFrame:
    df = pd.read_csv(REGISTRY_PATH, encoding="utf-8-sig").fillna("")
    for column in BASE_COLUMNS + COVERAGE_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df.astype({column: "object" for column in df.columns})
    return df


def write_registry(df: pd.DataFrame) -> None:
    ordered = BASE_COLUMNS + COVERAGE_COLUMNS
    extras = [column for column in df.columns if column not in ordered]
    df = df.reindex(columns=ordered + extras)
    df.to_csv(REGISTRY_PATH, index=False, encoding="utf-8-sig")


def default_metadata(row: pd.Series) -> dict[str, str]:
    institution_id, institution_name = canonical_institution(clean(row.get("institution_name")) or clean(row.get("institution_id")))
    source_type = clean(row.get("source_type"))
    collection_method = clean(row.get("collection_method"))
    extraction_mode = clean(row.get("extraction_mode"))
    scope = "KOBİ Rakip Banka"
    priority = "Existing"
    relevance = "Yüksek"
    exclusion = ""
    mvp_active = "False"
    capability = collection_method or "static_scrape"
    status = clean(row.get("source_validation_status")) or NOT_CHECKED

    raw_institution_id = clean(row.get("institution_id")).casefold()
    raw_name = clean(row.get("institution_name")).casefold()
    if raw_institution_id in {"news", "regülatör", "regulator", "industry_association"} or source_type in {
        "Regülatör",
        "Sektör Birliği",
        "Haber Sitesi",
        "Fintech Haberi",
        "İş/Ekonomi Haberi",
    }:
        scope = "Regülasyon / Haber"
        priority = "Existing"
        relevance = "Orta"
        mvp_active = "False"
    elif institution_id == "akbank":
        scope = "Kapsam Dışı"
        priority = "Internal"
        relevance = "Yüksek"
        exclusion = "Akbank internal benchmark target; not a competitor source for MVP expansion."
    elif (
        institution_id in {"vakifbank", "ziraat", "ziraat_bankasi", "bankkart_pos", "halkbank", "kuveyt_turk"}
        or raw_institution_id in {"ziraat", "ziraat_bankasi", "bankkart_pos", "halkbank", "vakifbank", "kuveyt_turk"}
        or any(token in raw_name for token in ["ziraat", "bankkart", "halkbank", "vakifbank", "vakıfbank", "kuveyt"])
    ):
        scope = "Kapsam Dışı"
        priority = "Excluded"
        relevance = "Orta"
        exclusion = "Public or participation bank excluded from current private-bank competitor scope."
    elif institution_id in {"visa", "mastercard"}:
        scope = "Global Ödeme Ağı"
        priority = "Current"
        relevance = "Yüksek"
    elif institution_id in {"bkm", "troy"}:
        scope = "Sektör / Altyapı"
        priority = "Current"
        relevance = "Yüksek"
    elif institution_id in {"iyzico", "paytr", "param", "sipay", "stripe", "adyen", "revolut_business", "wise_business"}:
        scope = "Fintech / Benchmark"
        priority = "Existing"
        relevance = "Orta"
    elif clean(row.get("institution_name")) in {"Rekabet Kurumu", "TCMB", "BDDK", "KAP", "Türkiye Bankalar Birligi", "TODEB"}:
        scope = "Regülasyon / Sektör"
        priority = "Existing"
        relevance = "Orta"

    if (
        truthy(row.get("active"))
        and collection_method.casefold() == "static_scrape"
        and extraction_mode in {"weekly_development", "both"}
        and source_type in WEEKLY_SOURCE_TYPES
        and scope in {"KOBİ Rakip Banka", "Global Ödeme Ağı", "Sektör / Altyapı"}
        and not exclusion
    ):
        mvp_active = "True"
        status = status if status != NOT_CHECKED else "Legacy active weekly source"
    elif collection_method.casefold() == "manual":
        capability = "manual"
        status = status if status != NOT_CHECKED else MANUAL_SOURCE
    return {
        "institution_id": institution_id or clean(row.get("institution_id")),
        "institution_name": institution_name or clean(row.get("institution_name")),
        "coverage_scope": scope,
        "coverage_priority": priority,
        "sme_relevance": relevance,
        "source_validation_status": status,
        "collector_capability": clean(row.get("collector_capability")) or capability,
        "mvp_active": mvp_active if scope != "KOBİ Rakip Banka" else (clean(row.get("mvp_active")) or mvp_active),
        "exclusion_reason": exclusion or clean(row.get("exclusion_reason")),
    }


def candidate_sources() -> list[SourceCandidate]:
    high = "KOBİ Kredileri; Ödemeler ve POS; KOBİ Mevduat; Kampanyalar; Nakit Yönetimi"
    pay = "Ödemeler ve POS; Ticari Kartlar; KOBİ; Tahsilat; Kampanyalar"
    press = "İş Birlikleri; Kampanyalar; KOBİ Kredileri; Ödemeler ve POS"
    return [
        SourceCandidate("Alternatif Bank", "Alternatif Bank Basın Odası", "Resmi Basın Bülteni Sayfası", "https://www.alternatifbank.com.tr/hakkimizda/basin-odasi", "weekly_development", "A", "Orta", press),
        SourceCandidate("Alternatif Bank", "Alternatif Bank Kampanyalar", "Resmi Kampanya Sayfası", "https://www.alternatifbank.com.tr/kampanyalar", "weekly_development", "A", "Orta", high),
        SourceCandidate("DenizBank", "DenizBank Medya Merkezi / Basında DenizBank", "Resmi Basın Bülteni Sayfası", "https://www.denizbank.com/hakkimizda/medya-merkezi/basinda-denizbank", "weekly_development", "A", "Yüksek", press),
        SourceCandidate("DenizBank", "DenizBank Kampanyalar", "Resmi Kampanya Sayfası", "https://www.denizbank.com/kampanya", "weekly_development", "A", "Yüksek", high),
        SourceCandidate("DenizBank", "DenizBank POS Ürünleri", "Resmi POS Sayfası", "https://www.denizbank.com/isim-icin/kobi-bankaciligi/uye-isyeri-ve-pos-islemleri/pos-urunleri", "benchmark_fact", "A", "Yüksek", pay),
        SourceCandidate("ING", "ING Basın Bültenleri 2026", "Resmi Basın Bülteni Sayfası", "https://www.ing.com.tr/tr/ing/basin-odasi/basin-bultenleri/2026", "weekly_development", "A", "Orta", press),
        SourceCandidate("ING", "ING Üye İşyeri", "Resmi POS Sayfası", "https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri", "benchmark_fact", "A", "Orta", pay),
        SourceCandidate("ING", "ING POS Ürünleri", "Resmi POS Sayfası", "https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/pos-urunleri", "benchmark_fact", "A", "Orta", pay),
        SourceCandidate("TEB", "TEB Basın Açıklamaları", "Resmi Basın Bülteni Sayfası", "https://www.teb.com.tr/teb-hakkinda/basin-aciklamalari/", "weekly_development", "A", "Yüksek", press),
        SourceCandidate("TEB", "CEPTETEB İşte Kampanyaları", "Resmi Kampanya Sayfası", "https://www.cepteteb.com.tr/kampanyalar/cepteteb-iste-kampanyalari", "weekly_development", "A", "Yüksek", high),
        SourceCandidate("TEB", "TEB POS", "Resmi POS Sayfası", "https://www.teb.com.tr/tebpos/", "benchmark_fact", "A", "Yüksek", pay),
        SourceCandidate("Şekerbank", "Şekerbank Esnaf KOBİ Kampanyalar", "Resmi Kampanya Sayfası", "https://www.sekerbank.com.tr/esnaf-kobi/kampanyalar", "weekly_development", "B", "Orta", high),
        SourceCandidate("Şekerbank", "Şekerbank POS Kampanyaları", "Resmi Kampanya Sayfası", "https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/pos-kampanyalari", "weekly_development", "B", "Orta", pay),
        SourceCandidate("Şekerbank", "Şekerbank Ticari Kartlar", "Resmi POS Sayfası", "https://www.sekerbank.com.tr/ticari-kartlar", "benchmark_fact", "B", "Orta", pay),
        SourceCandidate("Fibabanka", "Fibabanka Kampanyalar", "Resmi Kampanya Sayfası", "https://www.fibabanka.com.tr/kampanyalar", "weekly_development", "B", "Orta", high),
        SourceCandidate("Fibabanka", "Fibabanka Business Kredi Kartı", "Resmi KOBİ Sayfası", "https://www.fibabanka.com.tr/kucuk-isletme-ve-tarim/business-kredi-karti", "benchmark_fact", "B", "Orta", "Ticari Kartlar; KOBİ Kredileri; Kampanyalar"),
        SourceCandidate("Anadolubank", "Anadolubank Kampanyalar", "Resmi Kampanya Sayfası", "https://www.anadolubank.com.tr/kampanyalar", "weekly_development", "B", "Orta", high),
        SourceCandidate("Anadolubank", "Anadolubank POS", "Resmi POS Sayfası", "https://www.anadolubank.com.tr/isiniz-icin/pos", "benchmark_fact", "B", "Orta", pay),
        SourceCandidate("Odeabank", "Odeabank Basın Bültenleri", "Resmi Basın Bülteni Sayfası", "https://www.odeabank.com.tr/hakkimizda/basin-bultenleri", "weekly_development", "B", "Orta", press),
        SourceCandidate("Odeabank", "Odeabank Ticari", "Resmi KOBİ Sayfası", "https://www.odeabank.com.tr/ticari", "benchmark_fact", "B", "Orta", high),
        SourceCandidate("Burgan Bank", "Burgan Bank Basın Odası", "Resmi Basın Bülteni Sayfası", "https://www.burgan.com.tr/basin-odasi", "weekly_development", "C", "Düşük", press),
        SourceCandidate("HSBC", "HSBC Türkiye", "Resmi KOBİ Sayfası", "https://www.hsbc.com.tr/", "benchmark_fact", "C", "Düşük", high, active="False", exclusion_reason="No clear SME weekly-development source validated yet."),
        SourceCandidate("Enpara", "Enpara Şirketim", "Resmi KOBİ Sayfası", "https://www.enpara.com/sirketim", "benchmark_fact", "C", "Orta", high),
        SourceCandidate("Enpara", "Enpara Şirketim Kampanyalar", "Resmi Kampanya Sayfası", "https://www.enpara.com/sirketim/kampanyalar", "weekly_development", "C", "Orta", high),
        SourceCandidate("T-Bank", "T-Bank Ana Sayfa", "Resmi KOBİ Sayfası", "https://www.tbank.com.tr/", "benchmark_fact", "C", "Düşük", high, active="False", exclusion_reason="Direct weekly-development source not confirmed."),
        SourceCandidate("Turkish Bank", "Turkish Bank Ana Sayfa", "Resmi KOBİ Sayfası", "https://www.turkishbank.com/", "benchmark_fact", "C", "Düşük", high, active="False", exclusion_reason="Direct weekly-development source not confirmed."),
        SourceCandidate("Türk Ticaret Bankası", "Türk Ticaret Bankası Ana Sayfa", "Resmi KOBİ Sayfası", "https://www.turkticaretbankasi.com.tr/", "benchmark_fact", "C", "Düşük", high, active="False", exclusion_reason="Direct weekly-development source not confirmed."),
        SourceCandidate("Colendi Bank", "Colendi Bank Basında Biz", "Resmi Basın Bülteni Sayfası", "https://www.colendibank.com/basinda-biz/", "weekly_development", "Validate-only", "Belirsiz", press, active="False", exclusion_reason="Validate only; SME/commercial relevance not proven."),
        SourceCandidate("FUPS Bank", "FUPS Bank", "Resmi KOBİ Sayfası", "https://www.fupsbank.com/", "benchmark_fact", "Validate-only", "Belirsiz", high, active="False", exclusion_reason="Validate only; product scope appears retail/digital wallet."),
        SourceCandidate("ICBC Turkey", "ICBC Turkey", "Resmi KOBİ Sayfası", "https://www.icbc.com.tr/", "benchmark_fact", "Validate-only", "Belirsiz", high, active="False", exclusion_reason="Validate only; SME weekly source not proven."),
        SourceCandidate("Arap Türk Bankası", "Arap Türk Bankası", "Resmi KOBİ Sayfası", "https://www.atbank.com.tr/", "benchmark_fact", "Validate-only", "Belirsiz", high, active="False", exclusion_reason="Validate only; SME weekly source not proven."),
        SourceCandidate("Bank of China Turkey", "Bank of China Turkey", "Resmi KOBİ Sayfası", "https://www.bankofchina.com/tr/tr/", "benchmark_fact", "Validate-only", "Belirsiz", high, active="False", exclusion_reason="Validate only; SME weekly source not proven."),
    ]


def manual_wholesale_sources() -> list[SourceCandidate]:
    rows = []
    for name, url in [
        ("Citibank", "https://www.citibank.com.tr/"),
        ("Deutsche Bank", "https://country.db.com/turkey/"),
        ("JPMorgan Chase Bank", "https://www.jpmorgan.com/TR/en/about-us"),
        ("MUFG Bank Turkey", "https://www.mufg.com.tr/"),
        ("Intesa Sanpaolo", "https://www.intesasanpaolo.com.tr/"),
        ("Rabobank", "https://www.rabobank.com.tr/"),
        ("Société Générale", "https://www.societegenerale.com.tr/"),
        ("Bank Mellat", "https://www.mellatbank.com.tr/"),
    ]:
        rows.append(
            SourceCandidate(
                name,
                f"{name} manual registry placeholder",
                "Resmi KOBİ Sayfası",
                url,
                "benchmark_fact",
                "Manual-only",
                "Düşük",
                "Kurumsal Bankacılık; Benchmark",
                collection_method="manual",
                reliability_level="Orta",
                coverage_scope="Wholesale / Manual",
                active="False",
                notes="Registry-only/manual placeholder; not in MVP automated recent-development flow.",
                exclusion_reason="Wholesale/institutional bank; no broad SME weekly monitoring in current MVP.",
            )
        )
    return rows


def validate_candidate(row: pd.Series) -> Validation:
    method = clean(row.get("collection_method")).casefold()
    mode = clean(row.get("extraction_mode")).casefold()
    source_type = clean(row.get("source_type"))
    url = clean(row.get("url"))
    manual_reason = clean(row.get("exclusion_reason"))

    if clean(row.get("collector_capability")).casefold() == "browser_required":
        return Validation(BROWSER_REQUIRED, "browser_required", "False", "False", mode, manual_reason or "Static request requires browser/JS-aware collection.")
    if method == "manual":
        return Validation(MANUAL_SOURCE, "manual", "False", "False", mode, manual_reason or "Manual-only source.")

    try:
        response = requests.get(url, headers=HEADERS, timeout=18, allow_redirects=True)
        html = response.text or ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        blocked = response.status_code in {401, 403, 429} or bool(BLOCKED_RE.search(html[:6000]))
        total_links = useful_links = dated_links = 0
        for anchor in soup.find_all("a"):
            href = clean(anchor.get("href"))
            label = clean(anchor.get_text(" ", strip=True))
            if not href:
                continue
            absolute = urljoin(response.url, href)
            if not same_site(response.url, absolute):
                continue
            total_links += 1
            blob = f"{label} {absolute}"
            useful = bool(USEFUL_RE.search(blob))
            dated = bool(DATE_RE.search(blob))
            useful_links += int(useful)
            dated_links += int(dated and useful)

        content_length = len(text)
        final_url = response.url
        if blocked:
            return Validation(BROWSER_REQUIRED, "browser_required", "False", "False", mode, "Static request blocked or browser challenge detected.", str(response.status_code), len(response.content), total_links, useful_links, dated_links, final_url)
        if response.status_code >= 400:
            return Validation(INVALID, "unsupported", "False", "False", mode, f"HTTP {response.status_code}.", str(response.status_code), len(response.content), total_links, useful_links, dated_links, final_url)
        if content_length < 500 and total_links < 5:
            return Validation(BROWSER_REQUIRED, "browser_required", "False", "False", mode, "Page is too small or JS-rendered for static extraction.", str(response.status_code), len(response.content), total_links, useful_links, dated_links, final_url)

        weekly_candidate = mode in {"weekly_development", "both"} and source_type in WEEKLY_SOURCE_TYPES
        retail_heavy = bool(RETAIL_NOISE_RE.search(text[:12000])) and useful_links <= 2
        if weekly_candidate and dated_links > 0:
            return Validation(VALID_WEEKLY, "static_scrape", "True", "True", mode, "", str(response.status_code), len(response.content), total_links, useful_links, dated_links, final_url)
        if weekly_candidate and useful_links >= 3 and DATE_RE.search(text[:20000]):
            return Validation(VALID_WEEKLY, "static_scrape", "True", "True", mode, "", str(response.status_code), len(response.content), total_links, useful_links, dated_links, final_url)
        if weekly_candidate and retail_heavy:
            return Validation(RETAIL_NOISE, "static_scrape", "False", "False", mode, "Retail-heavy source; keep out of MVP unless SME filters improve.", str(response.status_code), len(response.content), total_links, useful_links, dated_links, final_url)
        if weekly_candidate:
            return Validation(STATIC_NO_DATED, "static_scrape", "False", "False", mode, "No dated detail links detected for recent-development flow.", str(response.status_code), len(response.content), total_links, useful_links, dated_links, final_url)
        if mode == "benchmark_fact" and USEFUL_RE.search(text[:20000]):
            return Validation(VALID_BENCHMARK, "static_scrape", "True", "False", "benchmark_fact", "", str(response.status_code), len(response.content), total_links, useful_links, dated_links, final_url)
        return Validation(STATIC_NO_DATED, "static_scrape", "False", "False", mode, "No SME/commercial weekly signal found.", str(response.status_code), len(response.content), total_links, useful_links, dated_links, final_url)
    except Exception as exc:
        return Validation(INVALID, "unsupported", "False", "False", mode, str(exc)[:240])


def upsert_candidates(registry: pd.DataFrame, rows: list[SourceCandidate]) -> pd.DataFrame:
    registry = registry.copy()
    existing_by_url = {source_key(row.get("url")): idx for idx, row in registry.iterrows()}
    for candidate in rows:
        institution_id, institution_name = canonical_institution(candidate.institution_name)
        payload = {
            "source_id": "",
            "tier": candidate.tier,
            "institution_id": institution_id,
            "institution_name": institution_name,
            "source_name": candidate.source_name,
            "source_type": candidate.source_type,
            "url": candidate.url,
            "collection_method": candidate.collection_method,
            "update_frequency": "Weekly",
            "reliability_level": candidate.reliability_level,
            "strategic_themes": candidate.strategic_themes,
            "active": candidate.active,
            "notes": candidate.notes,
            "extraction_mode": candidate.extraction_mode,
            "coverage_scope": candidate.coverage_scope,
            "coverage_priority": candidate.coverage_priority,
            "sme_relevance": candidate.sme_relevance,
            "source_validation_status": NOT_CHECKED,
            "collector_capability": candidate.collection_method,
            "mvp_active": "False",
            "exclusion_reason": candidate.exclusion_reason,
            "last_validated_at": "",
        }
        key = source_key(candidate.url)
        if key in existing_by_url:
            idx = existing_by_url[key]
            for column, value in payload.items():
                if column == "source_id":
                    continue
                if not clean(registry.at[idx, column]):
                    registry.at[idx, column] = value
            continue
        payload["source_id"] = next_source_id(registry)
        registry = pd.concat([registry, pd.DataFrame([payload])], ignore_index=True)
        existing_by_url[key] = registry.index[-1]
    return registry


def apply_defaults(registry: pd.DataFrame) -> pd.DataFrame:
    registry = registry.copy()
    for idx, row in registry.iterrows():
        defaults = default_metadata(row)
        force_scope = defaults.get("coverage_scope") not in {"", "KOBİ Rakip Banka"}
        for column, value in defaults.items():
            current = clean(registry.at[idx, column]) if column in registry.columns else ""
            if not current or (force_scope and column in {"coverage_scope", "coverage_priority", "sme_relevance", "exclusion_reason", "mvp_active"}):
                registry.at[idx, column] = value
    return registry


def validate_registry(registry: pd.DataFrame, only_priorities: set[str] | None = None) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    registry = registry.copy()
    validations: list[dict[str, str]] = []
    now = datetime.now(timezone.utc).isoformat()
    scope_mask = registry["coverage_scope"].astype(str).isin(["KOBİ Rakip Banka", "Wholesale / Manual"])
    if only_priorities:
        scope_mask &= registry["coverage_priority"].astype(str).isin(only_priorities)
    for idx, row in registry[scope_mask].iterrows():
        validation = validate_candidate(row)
        priority = clean(row.get("coverage_priority"))
        if priority in {"Validate-only", "Manual-only"}:
            validation.active = "False"
            validation.mvp_active = "False"
            if validation.status == VALID_WEEKLY and not validation.exclusion_reason:
                validation.exclusion_reason = "Validation-only source; not activated for MVP until SME relevance is accepted."
        registry.at[idx, "source_validation_status"] = validation.status
        registry.at[idx, "collector_capability"] = validation.collector_capability
        registry.at[idx, "mvp_active"] = validation.mvp_active
        registry.at[idx, "active"] = validation.active
        registry.at[idx, "extraction_mode"] = validation.extraction_mode
        if validation.collector_capability == "browser_required":
            registry.at[idx, "collection_method"] = "manual"
        elif validation.collector_capability == "manual":
            registry.at[idx, "collection_method"] = "manual"
        elif validation.collector_capability == "static_scrape":
            registry.at[idx, "collection_method"] = "static_scrape"
        if validation.exclusion_reason:
            registry.at[idx, "exclusion_reason"] = validation.exclusion_reason
        registry.at[idx, "last_validated_at"] = now
        validations.append(
            {
                "source_id": clean(row.get("source_id")),
                "institution_name": clean(row.get("institution_name")),
                "source_name": clean(row.get("source_name")),
                "url": clean(row.get("url")),
                "status": validation.status,
                "collector_capability": validation.collector_capability,
                "mvp_active": validation.mvp_active,
                "status_code": validation.status_code,
                "content_length": str(validation.content_length),
                "total_links": str(validation.total_links),
                "useful_links": str(validation.useful_links),
                "dated_links": str(validation.dated_links),
                "final_url": validation.final_url,
                "error": validation.error or validation.exclusion_reason,
            }
        )
        print(
            f"{row.get('source_id')} | {row.get('institution_name')} | {row.get('source_name')} | "
            f"{validation.status} | useful={validation.useful_links} dated={validation.dated_links} | mvp={validation.mvp_active}"
        )
    return registry, validations


def coverage_matrix(registry: pd.DataFrame) -> pd.DataFrame:
    scoped = registry[registry["coverage_scope"].astype(str).isin(["KOBİ Rakip Banka", "Wholesale / Manual"])].copy()
    if scoped.empty:
        return pd.DataFrame()
    grouped = []
    for institution, group in scoped.groupby("institution_name", dropna=False):
        weekly = group[group["source_validation_status"].isin([VALID_WEEKLY, "Legacy active weekly source"])]
        benchmark = group[group["source_validation_status"].eq(VALID_BENCHMARK)]
        browser = group[group["source_validation_status"].eq(BROWSER_REQUIRED)]
        manual = group[group["collector_capability"].eq("manual")]
        mvp = group[group["mvp_active"].apply(truthy)]
        status = "No proper weekly source"
        if len(mvp):
            status = "MVP active"
        elif len(weekly):
            status = "Weekly validated but inactive"
        elif len(benchmark):
            status = "Benchmark only"
        elif len(browser):
            status = "Browser required"
        elif len(manual):
            status = "Manual only"
        grouped.append(
            {
                "institution_name": institution,
                "institution_id": clean(group["institution_id"].iloc[0]),
                "institution_group": institution_group(institution),
                "coverage_priority": clean(group["coverage_priority"].iloc[0]),
                "coverage_scope": clean(group["coverage_scope"].iloc[0]),
                "sme_relevance": clean(group["sme_relevance"].iloc[0]),
                "sources_total": len(group),
                "valid_weekly_sources": len(weekly),
                "valid_benchmark_sources": len(benchmark),
                "browser_required_sources": len(browser),
                "manual_sources": len(manual),
                "mvp_active_sources": len(mvp),
                "coverage_status": status,
                "worked_source_pages": "; ".join(weekly["url"].astype(str).head(5)),
                "needs_refinement": "; ".join(group[group["source_validation_status"].isin([BROWSER_REQUIRED, STATIC_NO_DATED, RETAIL_NOISE, INVALID])]["source_name"].astype(str).head(5)),
            }
        )
    return pd.DataFrame(grouped).sort_values(["coverage_priority", "institution_name"])


def write_reports(registry: pd.DataFrame, validations: list[dict[str, str]]) -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    matrix = coverage_matrix(registry)
    matrix_path = DATA_DIR / "private_bank_coverage_matrix.csv"
    matrix.to_csv(matrix_path, index=False, encoding="utf-8-sig")

    report_path = DATA_DIR / f"private_bank_coverage_report_{timestamp}.md"
    validation_df = pd.DataFrame(validations)
    lines = [
        "# Private Bank Coverage Expansion Report",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- registry_rows: {len(registry)}",
        f"- validated_sources_this_run: {len(validation_df)}",
        f"- mvp_active_private_bank_sources: {int(registry['mvp_active'].apply(truthy).sum())}",
        "",
        "## Coverage Matrix",
        "",
    ]
    if matrix.empty:
        lines.append("No scoped institutions found.")
    else:
        for _, row in matrix.iterrows():
            lines.append(
                "- {institution} | {priority} | {status} | weekly={weekly} | benchmark={benchmark} | browser={browser} | mvp={mvp}".format(
                    institution=row["institution_name"],
                    priority=row["coverage_priority"],
                    status=row["coverage_status"],
                    weekly=row["valid_weekly_sources"],
                    benchmark=row["valid_benchmark_sources"],
                    browser=row["browser_required_sources"],
                    mvp=row["mvp_active_sources"],
                )
            )
    lines.extend(["", "## Validation Details", ""])
    if validation_df.empty:
        lines.append("- No validation run performed.")
    else:
        for _, row in validation_df.iterrows():
            lines.append(
                "- {source_id} | {institution_name} | {source_name} | {status} | HTTP {status_code} | useful={useful_links} | dated={dated_links} | {url}".format(
                    **{key: clean(value) for key, value in row.items()}
                )
            )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return matrix_path, report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand and validate private-bank coverage metadata.")
    parser.add_argument("--apply", action="store_true", help="Write source_registry.csv updates.")
    parser.add_argument("--validate", action="store_true", help="Fetch candidate pages and update validation status.")
    parser.add_argument(
        "--priority",
        default="",
        help="Optional comma-separated coverage priorities to validate, e.g. A,B,C,Validate-only,Manual-only.",
    )
    args = parser.parse_args()

    registry = read_registry()
    registry = apply_defaults(registry)
    registry = upsert_candidates(registry, candidate_sources() + manual_wholesale_sources())
    only_priorities = {item.strip() for item in args.priority.split(",") if item.strip()} or None

    validations: list[dict[str, str]] = []
    if args.validate:
        registry, validations = validate_registry(registry, only_priorities=only_priorities)

    matrix_path, report_path = write_reports(registry, validations)
    if args.apply:
        write_registry(registry)
        print(f"Updated registry: {REGISTRY_PATH.relative_to(ROOT_DIR)}")
    else:
        print("Dry run only; registry not written. Use --apply to persist.")
    print(f"Coverage matrix: {matrix_path.relative_to(ROOT_DIR)}")
    print(f"Coverage report: {report_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
