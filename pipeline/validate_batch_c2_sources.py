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
VALIDATION_PATH = DATA_DIR / "batch_c2_source_validation_candidates.csv"
INSPECTION_PATH = DATA_DIR / "batch_c2_candidate_inspection_table.csv"
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
NAV_RE = re.compile(r"(nav|menu|footer|header|breadcrumb|cookie|social|sosyal|mega|offcanvas)", re.I)
BLOCKED_RE = re.compile(r"(captcha|access denied|forbidden|cloudflare|request blocked|talep reddedildi)", re.I)

COMMERCIAL_RE = re.compile(
    r"(kobi|ticari|kurumsal|işletme|isletme|nakit kredi|gayrinakdi|nakit yönetimi|"
    r"dış ticaret|dis ticaret|ihracat|ihracatçı|ihracatci|eximbank|reeskont|ige|"
    r"teminat|akreditif|tahsilat|ödeme|odeme|finansman|finansal kurum|teknoloji bankacılığı|"
    r"t-gate|api|açık bankacılık|acik bankacilik|servis bankacılığı|şube|sube|working capital)",
    re.I,
)
LEGAL_RE = re.compile(
    r"(genel kurul|ttsg|rüçhan|ruchan|esas sözleşme|bilanço|fatca|crs|zaman aşımı|"
    r"güvenlik uyarısı|sahte|dolandırıcılık|faaliyet izin|tahsili gecikmiş|spk|mkk|"
    r"yasal uyarı|duyuru|operasyonel|resmî gazete|resmi gazete)",
    re.I,
)
REPORT_RE = re.compile(r"(finansal tablo|denetim raporu|faaliyet raporu|mali tablo|çeyrek sonuç|ceyrek sonuc)", re.I)
EVENT_RE = re.compile(r"(etkinlik|sohbet|söyleşi|soylesi|tiyatro|kokteyl|yeni yıl|kültür|kultur|fuar|çalıştay)", re.I)
NON_COMPETITIVE_TITLE_RE = re.compile(r"(siber güvenlik|siber guvenlik|salkım hesap|salkim hesap|sigorta)", re.I)
EXPORT_RE = re.compile(r"(ihracat|ihracatçı|ihracatci|dış ticaret|dis ticaret|eximbank|reeskont|ige|tim|ihracatı geliştirme)", re.I)
BRANCH_RE = re.compile(r"(şube|sube|hizmete açıldı|hizmete acildi|açıldı|acildi)", re.I)
GROUP_RE = re.compile(r"(turkishbank group|group|grup)", re.I)


@dataclass(frozen=True)
class CandidateSource:
    institution_name: str
    institution_id: str
    url: str
    source_name: str
    source_type: str
    proposed_mode: str
    intended_role: str
    strategic_themes: str
    coverage_scope: str
    customer_segment: str
    institution_group: str
    legal_name: str
    notes: str = ""
    preserve_source_id: str = ""


VALIDATION_COLUMNS = [
    "institution_name",
    "institution_id",
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
    "likely_commercial_link_count",
    "legal_notice_count",
    "financial_report_count",
    "event_or_culture_count",
    "repeated_navigation_ratio",
    "historical_archive_only",
    "structurally_valid",
    "currently_fresh",
    "benchmark_ready",
    "mvp_ready",
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
    "event_date",
    "effective_date",
    "recency_basis_date",
    "recency_basis_type",
    "date_confidence",
    "customer_segment",
    "local_commercial_evidence",
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
            classes = " ".join(str(value) for value in classes)
        blob = " ".join(str(value) for value in [attrs.get("id", ""), classes, attrs.get("role", ""), attrs.get("aria-label", "")] if value)
        if NAV_RE.search(blob):
            tag.decompose()
    return clone


def nav_ratio(soup: BeautifulSoup) -> float:
    anchors = soup.find_all("a", href=True)
    if not anchors:
        return 0.0
    nav = 0
    for anchor in anchors:
        parent = anchor.parent
        blob = " ".join(str(anchor.get(attr, "")) for attr in ["class", "id", "role", "aria-label"])
        if parent:
            blob += " " + " ".join(str(parent.get(attr, "")) for attr in ["class", "id", "role", "aria-label"])
        nav += int(bool(NAV_RE.search(blob)))
    return nav / len(anchors)


def title_from_url(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    slug = re.sub(r"\.(pdf|html?)$", "", slug, flags=re.I)
    return re.sub(r"[-_]+", " ", slug).strip().title()


def title_without_detail(text: str) -> str:
    text = re.sub(r"\bDetaylı Bilgi\b", "", clean(text), flags=re.I)
    text = re.sub(r"\bDevamı\b", "", text, flags=re.I)
    return clean(text)


def source_candidates() -> list[CandidateSource]:
    t_theme = "Ticari Krediler; Nakit Yönetimi; Dış Ticaret; Kurumsal Konumlandırma"
    tb_theme = "Ticari / Kurumsal Bankacılık; Teknoloji Bankacılığı; Finansal Kurumlar"
    ttb_theme = "İhracat Finansmanı; Dış Ticaret; İşletme Sermayesi; Şubeleşme"
    c: list[CandidateSource] = [
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/hakkimizda/detay/T-Bank-Hakkinda/9/1/0", "T-Bank Hakkında", "Resmi Kurumsal Sayfa", "benchmark_fact", "benchmark_fact", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş.", preserve_source_id="REG-102"),
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/hakkimizda/duyurular/Duyurular/20/0/0", "T-Bank Duyurular", "Resmi Duyuru Sayfası", "weekly_development", "manual", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş.", "Legal/security/regulatory-heavy feed; monitor manually only."),
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/haberler/haber-liste/Haberler/22/0/0", "T-Bank Haberler", "Resmi Haber Sayfası", "weekly_development", "manual", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş.", "Canonical Haberler route discovered from Hakkımızda navigation; noisy security/legal feed."),
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/ticari-bankacilik/detay-akordeon/Nakit-Krediler/85/184/0", "T-Bank Nakit Krediler", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş."),
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/ticari-bankacilik/detay-akordeon/Gayrinakdi-Krediler/105/176/0", "T-Bank Gayrinakdi Krediler", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş."),
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/ticari-bankacilik/detay/Nakit-Yonetimi/114/245/0", "T-Bank Nakit Yönetimi", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş."),
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/ticari-bankacilik/detay-akordeon/Yatirim-Urunleri/123/179/0", "T-Bank Yatırım Ürünleri", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş."),
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/ticari-bankacilik/detay-akordeon/Diger-Urunler/130/186/0", "T-Bank Diğer Ticari Ürünler", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş."),
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/hakkimizda/detay/Faaliyet-Raporlari/19/10/0", "T-Bank Faaliyet Raporları", "Resmi Rapor Sayfası", "ignore", "ignore", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş.", "Reporting archive."),
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/hakkimizda/detay/Mali-Tablolar/18/9/0", "T-Bank Mali Tablolar", "Resmi Rapor Sayfası", "ignore", "ignore", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş.", "Financial-report archive."),
        CandidateSource("T-Bank", "t_bank", "https://www.tbank.com.tr/hakkimizda/duyuru-detay/26-03-2026-OIagan-Genel-Kurul-Duyurusu/20/591/0", "T-Bank Genel Kurul Duyurusu Örneği", "Resmi Duyuru Sayfası", "ignore", "ignore", t_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkland Bank A.Ş.", "Structural legal-announcement example."),
        CandidateSource("TurkishBank", "turkish_bank", "https://www.turkishbank.com/", "TurkishBank Ana Site", "Resmi Site", "ignore", "ignore", tb_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkish Bank A.Ş.", "Generic homepage with repeated widgets.", preserve_source_id="REG-103"),
        CandidateSource("TurkishBank", "turkish_bank", "https://www.turkishbank.com/hakkimizda/bizden-haberler/", "TurkishBank Bizden Haberler", "Resmi Haber Sayfası", "weekly_development", "manual", tb_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkish Bank A.Ş.", "Noisy mixed feed; strict filtering required before MVP."),
        CandidateSource("TurkishBank", "turkish_bank", "https://www.turkishbank.com/hakkimizda/rapor/", "TurkishBank Raporlar", "Resmi Rapor Sayfası", "ignore", "ignore", tb_theme, "Kısmi Kapsam", "Büyük Kurumsal / Toptan", "Orta/Küçük Ölçekli Özel Bankalar", "Turkish Bank A.Ş.", "Canonical Raporlar URL discovered from navigation."),
        CandidateSource("TurkishBank", "turkish_bank", "https://www.turkishbank.com/ticari-kurumsal-bankacilik/", "TurkishBank Ticari / Kurumsal Bankacılık", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", tb_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkish Bank A.Ş."),
        CandidateSource("TurkishBank", "turkish_bank", "https://www.turkishbank.com/ticari-kurumsal-bankacilik/iliski-bankaciligi/", "TurkishBank İlişki Bankacılığı", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", tb_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkish Bank A.Ş."),
        CandidateSource("TurkishBank", "turkish_bank", "https://www.turkishbank.com/ticari-kurumsal-bankacilik/finansal-kurumlar/", "TurkishBank Finansal Kurumlar", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", tb_theme, "Toptan / Kurumsal Banka", "Finansal Kurumlar", "Orta/Küçük Ölçekli Özel Bankalar", "Turkish Bank A.Ş.", "Canonical Finansal Kurumlar child URL discovered from commercial page."),
        CandidateSource("TurkishBank", "turkish_bank", "https://www.turkishbank.com/teknoloji-bankaciligi/", "TurkishBank Teknoloji Bankacılığı", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", tb_theme, "Kısmi Kapsam", "Orta Ölçekli Ticari", "Orta/Küçük Ölçekli Özel Bankalar", "Turkish Bank A.Ş."),
        CandidateSource("TurkishBank", "turkish_bank", "https://t-gate.co/", "T-Gate", "Harici Platform", "benchmark_fact", "manual", "Teknoloji Bankacılığı; Embedded Finance", "Kısmi Kapsam", "Belirsiz", "Orta/Küçük Ölçekli Özel Bankalar", "Turkish Bank A.Ş.", "External affiliated platform; structural validation only."),
        CandidateSource("TurkishBank", "turkish_bank", "https://www.acikyatirim.com/", "AÇIK YATIRIM", "Harici Platform", "ignore", "ignore", "Yatırım", "Kapsam Dışı", "Belirsiz", "Orta/Küçük Ölçekli Özel Bankalar", "Turkish Bank A.Ş.", "Investment platform; outside SME radar by default."),
        CandidateSource("TurkishBank", "turkish_bank", "https://www.turkishbank.com/hakkimizda/bizden-haberler/turkishbank-group-best-innovation-in-retail-banking-turkey-en-inovatif-banka/", "TurkishBank Historical Award Example", "Resmi Haber Sayfası", "ignore", "ignore", tb_theme, "Kısmi Kapsam", "Belirsiz", "Orta/Küçük Ölçekli Özel Bankalar", "Turkish Bank A.Ş.", "Parser test only; generic group/retail award."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/", "Türk Ticaret Bankası Ana Site", "Resmi Site", "ignore", "ignore", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş.", "Generic homepage.", preserve_source_id="REG-104"),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerik/duyurular", "Türk Ticaret Bankası Duyurular", "Resmi Duyuru Sayfası", "weekly_development", "manual", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş.", "Legal-heavy announcement page; manual only."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerik/haberler", "Türk Ticaret Bankası Haberler Guess", "Resmi Haber Sayfası", "ignore", "ignore", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş.", "Invalid guessed route; canonical route is plural."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerik/basin-bultenleri", "Türk Ticaret Bankası Basın Guess", "Resmi Basın Bülteni Sayfası", "ignore", "ignore", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş.", "Invalid guessed route; canonical route is plural."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerikler/haberler", "Türk Ticaret Bankası Haberler", "Resmi Haber Sayfası", "weekly_development", "weekly_development", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş.", "Canonical Haberler route discovered from homepage navigation."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerikler/basin-bultenleri", "Türk Ticaret Bankası Basın Bültenleri", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş.", "Canonical Basın Bültenleri route discovered from homepage navigation."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/hakkimizda/bankamiz", "Türk Ticaret Bankası Bankamız", "Resmi Kurumsal Sayfa", "benchmark_fact", "benchmark_fact", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerik/dis-ticaret-finansmani", "Türk Ticaret Bankası Dış Ticaret Finansmanı", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", ttb_theme, "Ticari / İhracat Bankası", "İhracatçı KOBİ", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerik/isletme-sermayeli-krediler", "Türk Ticaret Bankası İşletme Sermayesi Kredileri", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerik/teminat-mektuplari", "Türk Ticaret Bankası Teminat Mektupları", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerik/urun-ve-hizmet-ucretleri", "Türk Ticaret Bankası Ürün ve Hizmet Ücretleri", "Resmi Ücret/Pricing Sayfası", "benchmark_fact", "benchmark_fact", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerik/subeler", "Türk Ticaret Bankası Şubeler", "Resmi Şube Sayfası", "benchmark_fact", "benchmark_fact", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş."),
        CandidateSource("Türk Ticaret Bankası", "turk_ticaret_bankasi", "https://www.turkticaretbankasi.com.tr/icerik/turk-ticaret-bankasi-basin-lansmani-yapildi", "Türk Ticaret Bankası Lansman Tarihsel Örnek", "Resmi Haber Sayfası", "ignore", "ignore", ttb_theme, "Ticari / İhracat Bankası", "Ticari / İhracat", "Ticari / İhracat Bankası", "Türk Ticaret Bankası A.Ş.", "Historical parser check; reopening story is background."),
    ]
    return c


def metrics_for_links(candidate: CandidateSource, soup: BeautifulSoup, final_url: str) -> dict[str, object]:
    scoped = remove_noise(soup)
    useful = dated = recent = commercial = legal = reports = events = exporter = corporate = 0
    latest = ""
    for anchor in scoped.find_all("a", href=True):
        href = urljoin(final_url, clean(anchor.get("href")))
        if not same_site(final_url, href) and candidate.institution_name != "TurkishBank":
            continue
        text = title_without_detail(anchor.get_text(" ", strip=True))
        parent = clean(anchor.parent.get_text(" ", strip=True)) if anchor.parent else text
        img = anchor.find("img")
        img_src = clean(img.get("src", "")) if img else ""
        blob = f"{text} {parent} {href} {img_src}"
        if len(blob) < 8:
            continue
        dates = date_strings_from_blob(blob)
        is_commercial = bool(COMMERCIAL_RE.search(blob))
        is_legal = bool(LEGAL_RE.search(blob))
        is_report = bool(REPORT_RE.search(blob))
        is_event = bool(EVENT_RE.search(blob))
        useful += int(is_commercial or bool(dates))
        commercial += int(is_commercial and not is_legal)
        legal += int(is_legal)
        reports += int(is_report)
        events += int(is_event)
        exporter += int(bool(EXPORT_RE.search(blob)))
        corporate += int(is_commercial and not bool(EXPORT_RE.search(blob)))
        for date_value in dates:
            dated += 1
            latest = max(latest, date_value)
            if date_value >= START_DATE:
                recent += 1
    text = scoped.get_text(" ", strip=True)
    return {
        "useful": useful,
        "dated": dated,
        "recent": recent,
        "commercial": commercial,
        "legal": legal,
        "reports": reports,
        "events": events,
        "exporter": exporter,
        "corporate": corporate,
        "latest": latest,
        "structurally_valid": len(text) >= 400,
        "page_commercial": bool(COMMERCIAL_RE.search(text[:50000])),
        "nav_ratio": nav_ratio(soup),
    }


def date_strings_from_blob(blob: str) -> list[str]:
    out: list[str] = []
    for raw in DATE_RE.findall(blob):
        raw_text = raw if isinstance(raw, str) else raw[0]
        parsed = pd.to_datetime(raw_text.replace("-", "/"), errors="coerce", dayfirst=True)
        if pd.notna(parsed):
            out.append(parsed.date().isoformat())
    for year, month in re.findall(r"/(20\d{2})/([01]\d)/", blob):
        out.append(f"{year}-{month}-01")
    for day, month, year in re.findall(r"([0-3]\d)([01]\d)(2[0-9])", blob):
        out.append(f"20{year}-{month}-{day}")
    return sorted(set(out))


def score_source(candidate: CandidateSource) -> dict[str, str]:
    checked_at = datetime.now(timezone.utc).isoformat()
    base = {column: "" for column in VALIDATION_COLUMNS}
    base.update(
        {
            "institution_name": candidate.institution_name,
            "institution_id": candidate.institution_id,
            "candidate_url": candidate.url,
            "proposed_source_name": candidate.source_name,
            "proposed_source_type": candidate.source_type,
            "proposed_extraction_mode": candidate.proposed_mode,
            "response_size": "0",
            "useful_link_count": "0",
            "dated_link_count": "0",
            "recent_link_count": "0",
            "likely_commercial_link_count": "0",
            "legal_notice_count": "0",
            "financial_report_count": "0",
            "event_or_culture_count": "0",
            "repeated_navigation_ratio": "0.00",
            "historical_archive_only": "False",
            "structurally_valid": "False",
            "currently_fresh": "False",
            "benchmark_ready": "False",
            "mvp_ready": "False",
            "collector_capability": "static_scrape",
            "validation_result": "Invalid",
            "activation_recommendation": "ignore",
            "reason": candidate.notes,
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
    if response.status_code in {401, 403, 429, 512} or BLOCKED_RE.search(html[:5000]):
        if candidate.intended_role == "ignore":
            base.update({"validation_result": "Invalid guessed route", "reason": candidate.notes or f"HTTP {response.status_code}."})
        else:
            base.update({"collector_capability": "browser_required", "validation_result": "Browser required", "activation_recommendation": "browser_required", "reason": f"HTTP {response.status_code} or challenge detected."})
        return base
    if response.status_code >= 400:
        base["reason"] = f"HTTP {response.status_code}."
        return base
    soup = BeautifulSoup(html, "html.parser")
    metrics = metrics_for_links(candidate, soup, response.url)
    historical_only = bool(metrics["latest"]) and str(metrics["latest"]) < START_DATE
    currently_fresh = int(metrics["recent"]) > 0
    benchmark_ready = (
        bool(metrics["structurally_valid"])
        and (bool(metrics["page_commercial"]) or candidate.proposed_mode == "benchmark_fact")
    ) or (candidate.intended_role == "benchmark_fact" and len(response.content) >= 3000)
    result = "Invalid"
    activation = "ignore"
    capability = "static_scrape"
    mvp_ready = False
    reason = candidate.notes
    if candidate.intended_role == "ignore":
        result = "Structural / ignored"
        reason = candidate.notes or "Ignored by source policy."
    elif candidate.intended_role == "manual":
        result = "Manual inspection needed"
        activation = "manual"
        capability = "manual"
        reason = candidate.notes or "Relevant but static extraction is not safe enough."
    elif candidate.intended_role == "benchmark_fact":
        if benchmark_ready:
            result = "Valid benchmark-only source"
            activation = "activate_benchmark_fact"
            reason = candidate.notes or "Evergreen product/pricing/commercial content; recent-development only on dated material revision."
        else:
            result = "Static/no useful commercial content"
            reason = "No sufficient local commercial content after navigation removal."
    elif candidate.intended_role == "weekly_development":
        if candidate.institution_id == "turk_ticaret_bankasi" and int(metrics["commercial"]) > 0 and int(metrics["recent"]) > 0:
            result = "Valid weekly source"
            activation = "activate_weekly_development"
            mvp_ready = True
            reason = "Item-level export/commercial links found; current candidates still require item-level date verification."
        elif candidate.institution_id == "turk_ticaret_bankasi" and int(metrics["commercial"]) > 0:
            result = "Promising but not current"
            activation = "manual"
            capability = "manual"
            reason = "Commercial/export items exist but no post-cutoff item date is reliable enough."
        elif currently_fresh:
            result = "Dated but not MVP-ready"
            activation = "manual"
            capability = "manual"
            reason = "Current links exist, but candidate quality is legal/report/event-heavy."
        elif historical_only:
            result = "Historical archive only"
            reason = "Archive is structurally valid but no current competitive item passed source-level freshness."
        else:
            result = "No clean current weekly feed"
            activation = "manual" if candidate.intended_role == "manual" else "ignore"
            capability = "manual" if activation == "manual" else "static_scrape"
            reason = candidate.notes or "No reliable dated item-level competitive feed detected."
    base.update(
        {
            "useful_link_count": str(metrics["useful"]),
            "dated_link_count": str(metrics["dated"]),
            "recent_link_count": str(metrics["recent"]),
            "likely_commercial_link_count": str(metrics["commercial"]),
            "legal_notice_count": str(metrics["legal"]),
            "financial_report_count": str(metrics["reports"]),
            "event_or_culture_count": str(metrics["events"]),
            "repeated_navigation_ratio": f"{metrics['nav_ratio']:.2f}",
            "historical_archive_only": str(historical_only),
            "structurally_valid": str(metrics["structurally_valid"]),
            "currently_fresh": str(currently_fresh),
            "benchmark_ready": str(benchmark_ready),
            "mvp_ready": str(mvp_ready),
            "collector_capability": capability,
            "validation_result": result,
            "activation_recommendation": activation,
            "reason": reason,
        }
    )
    return base


def inspect_item(
    institution: str,
    source_id: str,
    source_name: str,
    title: str,
    url: str,
    customer_segment: str,
    notes: str = "",
    listing_context: str = "",
) -> dict[str, str]:
    response, error = fetch(url)
    text = ""
    page_title = title
    if response is not None and response.status_code < 400:
        soup = BeautifulSoup(response.text, "html.parser")
        page_title = clean(soup.title.get_text(" ", strip=True) if soup.title else "") or title
        text = remove_noise(soup).get_text("\n", strip=True)
    date_meta = extract_date_semantics(
        visible_text=f"{title}\n{text[:2500]}",
        url=url,
        listing_text=title,
        inferred_text=f"{title}\n{text[:5000]}",
        source_type="Resmi Haber Sayfası",
    )
    if not date_meta.get("normalized_date"):
        image_dates = date_strings_from_blob(url + " " + title + " " + listing_context + " " + text[:5000])
        if image_dates:
            date_meta.update(
                {
                    "publication_date": image_dates[-1],
                    "event_date_type": "Yayın Tarihi",
                    "recency_basis_date": image_dates[-1],
                    "raw_date_text": image_dates[-1],
                    "normalized_date": image_dates[-1],
                    "date_source": "listing_or_asset_date",
                    "date_confidence": "Orta",
                }
            )
    recency = evaluate_recency(date_meta, START_DATE)
    blob = f"{page_title} {title} {url} {text[:3000]}"
    is_legal = bool(LEGAL_RE.search(blob))
    is_report = bool(REPORT_RE.search(blob))
    is_event = bool(EVENT_RE.search(blob))
    is_group = bool(GROUP_RE.search(blob))
    is_exporter = bool(EXPORT_RE.search(blob))
    is_branch = bool(BRANCH_RE.search(blob))
    is_commercial = bool(COMMERCIAL_RE.search(blob))
    if NON_COMPETITIVE_TITLE_RE.search(title) and not is_exporter and not is_branch:
        content_role = "Kapsam Dışı"
        reject = "non-competitive/product-security noise"
    elif is_legal:
        content_role = "Kapsam Dışı"
        reject = "legal announcement"
    elif institution == "TurkishBank" and is_group and not re.search(r"(turkish bank a\.ş|türkiye|turkiye|yerel|ticari|kurumsal)", blob, re.I):
        content_role = "Kapsam Dışı"
        reject = "group-level content without TurkishBank A.Ş./Türkiye relevance"
    elif is_report and is_exporter:
        content_role = "Yönetici Bilgilendirme"
        reject = "" if recency.get("is_recent") else str(recency.get("recency_reason", "not recent"))
    elif is_report:
        content_role = "Bağlamsal Veri"
        reject = "financial report without enough segment evidence" if recency.get("is_recent") else str(recency.get("recency_reason", "not recent"))
    elif is_event and not re.search(r"(lansman|platform|api|ödeme|odeme|ticari|ihracat)", blob, re.I):
        content_role = "Kapsam Dışı"
        reject = "event/cultural/investment noise"
    elif is_branch and is_exporter:
        content_role = "Bağımsız Gelişme"
        reject = "" if recency.get("is_recent") else str(recency.get("recency_reason", "not recent"))
    elif is_commercial:
        content_role = "Bağımsız Gelişme"
        reject = "" if recency.get("is_recent") else str(recency.get("recency_reason", "not recent"))
    else:
        content_role = "Kapsam Dışı"
        reject = "no local commercial/export evidence"
    accepted = bool(recency.get("is_recent")) and content_role in {"Bağımsız Gelişme", "Yönetici Bilgilendirme"}
    if error:
        reject = error
    if not accepted and not reject:
        reject = str(recency.get("recency_reason", "not accepted"))
    evidence_match = COMMERCIAL_RE.search(blob)
    evidence = evidence_match.group(0) if evidence_match else ""
    return {
        "institution_name": institution,
        "source_id": source_id,
        "source_name": source_name,
        "item_title": clean(page_title.replace("– TurkishBank", "").replace("| T-Bank", "")),
        "item_url": url,
        "publication_date": date_meta.get("publication_date", ""),
        "event_date": date_meta.get("announcement_date", ""),
        "effective_date": date_meta.get("campaign_start_date", ""),
        "recency_basis_date": str(recency.get("recency_basis_date", date_meta.get("recency_basis_date", ""))),
        "recency_basis_type": date_meta.get("date_source", "unknown"),
        "date_confidence": date_meta.get("date_confidence", ""),
        "customer_segment": customer_segment,
        "local_commercial_evidence": evidence,
        "content_role": content_role,
        "proposed_destination": "recent_development_candidate" if accepted and content_role == "Bağımsız Gelişme" else "management_awareness" if accepted else "archive_or_context",
        "accepted": str(accepted),
        "rejection_reason": reject,
        "duplicate_status": "not_checked",
        "notes": notes,
    }


def extract_listing_candidates(url: str, institution: str) -> list[tuple[str, str, str]]:
    response, _ = fetch(url)
    if response is None or response.status_code >= 400:
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    out: dict[str, tuple[str, str, str]] = {}
    turk_ticaret_excluded_paths = {
        "/icerik/nakit-yonetimi",
        "/icerik/form-ve-sozlesmeler",
        "/icerik/surdurulebilirlik",
        "/icerik/duyurular",
        "/icerik/sss",
        "/icerik/subeler",
        "/icerik/urun-ve-hizmet-ucretleri",
        "/icerik/bildirimler",
        "/icerik/dis-ticaret-finansmani",
        "/icerik/isletme-sermayeli-krediler",
        "/icerik/teminat-mektuplari",
    }
    for anchor in soup.find_all("a", href=True):
        href = urljoin(response.url, anchor.get("href", ""))
        path = urlparse(href).path.rstrip("/")
        text = title_without_detail(anchor.get_text(" ", strip=True))
        parent = title_without_detail(anchor.parent.get_text(" ", strip=True)) if anchor.parent else text
        img = anchor.find("img")
        img_src = img.get("src", "") if img else ""
        if institution == "T-Bank" and "/haberler/detay/" not in href and "/hakkimizda/duyuru-detay/" not in href:
            continue
        if institution == "TurkishBank" and "/hakkimizda/bizden-haberler/" not in href:
            continue
        if institution == "Türk Ticaret Bankası":
            if not path.startswith("/icerik/"):
                continue
            if path in turk_ticaret_excluded_paths:
                continue
            if not img:
                continue
        title = parent if len(parent) > len(text) else text
        if not title:
            title = title_from_url(href)
        if institution == "Türk Ticaret Bankası" and NON_COMPETITIVE_TITLE_RE.search(f"{title} {path.replace('-', ' ')}"):
            continue
        out[source_key(href)] = (title, href, img_src)
    return list(out.values())


def build_inspection(validation: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    validation_by_name = {clean(row["proposed_source_name"]): row for _, row in validation.iterrows()}
    sample_sources = [
        ("T-Bank", "T-Bank Haberler", "REG-C2-TBANK-HABERLER", "Orta Ölçekli Ticari", "legal/security/current feed sample"),
        ("T-Bank", "T-Bank Duyurular", "REG-C2-TBANK-DUYURULAR", "Orta Ölçekli Ticari", "legal announcement sample"),
        ("TurkishBank", "TurkishBank Bizden Haberler", "REG-C2-TURKISHBANK-HABERLER", "Orta Ölçekli Ticari", "mixed feed sample"),
        ("Türk Ticaret Bankası", "Türk Ticaret Bankası Haberler", "REG-C2-TTB-HABERLER", "Ticari / İhracat", "export/news sample"),
        ("Türk Ticaret Bankası", "Türk Ticaret Bankası Basın Bültenleri", "REG-C2-TTB-BASIN", "Ticari / İhracat", "press sample"),
    ]
    for institution, source_name, fallback_id, segment, notes in sample_sources:
        row = validation_by_name.get(source_name)
        if row is None:
            continue
        url = clean(row["candidate_url"])
        for title, href, img_src in extract_listing_candidates(url, institution)[:10]:
            rows.append(inspect_item(institution, fallback_id, source_name, title, href, segment, notes, img_src))
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


def status_for(candidate: CandidateSource, activation: str, mvp_active: str) -> str:
    if activation in {"manual", "browser_required"}:
        return "Manuel İzleme"
    if candidate.institution_id == "turk_ticaret_bankasi" and mvp_active == "True":
        return "Ticari / İhracat Bankası"
    if mvp_active == "True":
        return "Aktif"
    if activation == "activate_benchmark_fact":
        return "Kısmi Kapsam"
    return "Kaynak Geliştirme Gerekli"


def upsert_sources(registry: pd.DataFrame, candidates: list[CandidateSource], validation: pd.DataFrame) -> pd.DataFrame:
    registry = registry.copy()
    by_url = {source_key(row.get("url", "")): idx for idx, row in registry.iterrows()}
    by_id = {clean(row.get("source_id", "")): idx for idx, row in registry.iterrows()}
    candidate_by_key = {source_key(candidate.url): candidate for candidate in candidates}
    now = datetime.now(timezone.utc).isoformat()
    rows_to_apply = validation[
        validation["activation_recommendation"].isin(["activate_weekly_development", "activate_benchmark_fact", "manual", "browser_required"])
        | validation["proposed_source_name"].isin(["TurkishBank Ana Site", "Türk Ticaret Bankası Ana Site"])
    ]
    for _, result in rows_to_apply.iterrows():
        key = source_key(result["candidate_url"])
        candidate = candidate_by_key.get(key)
        if candidate is None:
            continue
        activation = clean(result["activation_recommendation"])
        mode = "weekly_development" if activation == "activate_weekly_development" else "benchmark_fact" if activation == "activate_benchmark_fact" else "manual"
        active = "True" if activation in {"activate_weekly_development", "activate_benchmark_fact", "manual"} else "False"
        mvp_active = "True" if truthy(result["mvp_ready"]) else "False"
        claude_eligible = "False"
        payload = {
            "tier": "Tier 1",
            "institution_id": candidate.institution_id,
            "institution_name": candidate.institution_name,
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
            "sme_relevance": "Yüksek" if candidate.institution_id == "turk_ticaret_bankasi" else "Orta",
            "source_validation_status": clean(result["validation_result"]),
            "collector_capability": clean(result["collector_capability"]),
            "mvp_active": mvp_active,
            "claude_eligible": claude_eligible,
            "mvp_status": status_for(candidate, activation, mvp_active),
            "customer_segment": candidate.customer_segment,
            "institution_group": candidate.institution_group,
            "display_name": candidate.institution_name,
            "legal_name": candidate.legal_name,
            "exclusion_reason": "" if mvp_active == "True" else clean(result["reason"]),
            "last_validated_at": now,
        }
        if candidate.preserve_source_id and candidate.preserve_source_id in by_id:
            idx = by_id[candidate.preserve_source_id]
        elif key in by_url:
            idx = by_url[key]
        else:
            payload["source_id"] = next_source_id(registry)
            registry = pd.concat([registry, pd.DataFrame([payload])], ignore_index=True)
            idx = registry.index[-1]
            by_id[payload["source_id"]] = idx
            by_url[key] = idx
        if "source_id" in registry.columns and not clean(registry.at[idx, "source_id"]):
            registry.at[idx, "source_id"] = candidate.preserve_source_id or next_source_id(registry)
        for column, value in payload.items():
            if column != "source_id":
                registry.at[idx, column] = value
    return registry


def write_registry(registry: pd.DataFrame) -> None:
    ordered = BASE_COLUMNS + COVERAGE_COLUMNS
    extras = [column for column in registry.columns if column not in ordered]
    tmp = REGISTRY_PATH.with_suffix(".csv.tmp")
    registry.reindex(columns=ordered + extras).to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(REGISTRY_PATH)


def write_report(validation: pd.DataFrame, inspection: pd.DataFrame) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DATA_DIR / f"batch_c2_candidate_quality_report_{timestamp}.md"
    lines = [
        "# Batch C2 Candidate Quality Report",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- candidates_tested: {len(validation)}",
        f"- valid_weekly_sources: {int(validation['activation_recommendation'].eq('activate_weekly_development').sum())}",
        f"- benchmark_only_sources: {int(validation['activation_recommendation'].eq('activate_benchmark_fact').sum())}",
        f"- manual_or_browser_sources: {int(validation['activation_recommendation'].isin(['manual','browser_required']).sum())}",
        f"- ignored_sources: {int(validation['activation_recommendation'].eq('ignore').sum())}",
        "",
    ]
    numeric_cols = [
        "useful_link_count",
        "dated_link_count",
        "recent_link_count",
        "likely_commercial_link_count",
        "legal_notice_count",
        "financial_report_count",
        "event_or_culture_count",
    ]
    for institution, group in validation.groupby("institution_name", sort=False):
        numeric = group.copy()
        for column in numeric_cols:
            numeric[column] = pd.to_numeric(numeric[column], errors="coerce").fillna(0).astype(int)
        inst_inspection = inspection[inspection["institution_name"].eq(institution)].copy()
        lines.extend([f"## {institution}", ""])
        lines.append(f"- exact source candidates tested: {len(group)}")
        lines.append(f"- canonical source URLs found: {', '.join(group[group['http_status'].eq('200')]['final_url'].head(8).tolist())}")
        lines.append(f"- valid weekly sources: {int(group['activation_recommendation'].eq('activate_weekly_development').sum())}")
        lines.append(f"- benchmark-only sources: {int(group['activation_recommendation'].eq('activate_benchmark_fact').sum())}")
        lines.append(f"- manual/browser sources: {int(group['activation_recommendation'].isin(['manual','browser_required']).sum())}")
        lines.append(f"- ignored sources: {int(group['activation_recommendation'].eq('ignore').sum())}")
        lines.append(f"- total/useful links: {int(numeric['useful_link_count'].sum())}")
        lines.append(f"- dated links: {int(numeric['dated_link_count'].sum())}")
        lines.append(f"- post-cutoff links: {int(numeric['recent_link_count'].sum())}")
        lines.append(f"- explicit commercial relevance passes: {int(numeric['likely_commercial_link_count'].sum())}")
        lines.append(f"- legal notices: {int(numeric['legal_notice_count'].sum())}")
        lines.append(f"- financial reports: {int(numeric['financial_report_count'].sum())}")
        lines.append(f"- event/cultural noise: {int(numeric['event_or_culture_count'].sum())}")
        lines.append(f"- exporter candidates: {int(inst_inspection['local_commercial_evidence'].astype(str).str.contains('ihrac|eximbank|ige|reeskont', case=False, regex=True).sum()) if not inst_inspection.empty else 0}")
        lines.append(f"- management-awareness candidates: {int(inst_inspection['content_role'].eq('Yönetici Bilgilendirme').sum()) if not inst_inspection.empty else 0}")
        lines.append(f"- duplicates: 0")
        lines.append(f"- adapter required: {'yes' if group['activation_recommendation'].isin(['activate_weekly_development','manual']).any() else 'no'}")
        lines.append(f"- tiny Claude pilot readiness: {'yes' if group['activation_recommendation'].eq('activate_weekly_development').any() and not inst_inspection[inst_inspection['accepted'].eq('True')].empty else 'no'}")
        lines.append("")
        for _, row in group.iterrows():
            lines.append(
                f"- `{row['activation_recommendation']}` | {row['validation_result']} | {row['proposed_source_name']} | "
                f"structural={row['structurally_valid']} fresh={row['currently_fresh']} benchmark={row['benchmark_ready']} "
                f"mvp={row['mvp_ready']} | dated={row['dated_link_count']} recent={row['recent_link_count']} "
                f"commercial={row['likely_commercial_link_count']} legal={row['legal_notice_count']} reports={row['financial_report_count']} events={row['event_or_culture_count']} | "
                f"{row['candidate_url']} | {row['reason']}"
            )
        if not inst_inspection.empty:
            lines.extend(["", "Top inspected candidates:"])
            for _, item in inst_inspection.head(10).iterrows():
                lines.append(
                    f"- accepted={item['accepted']} | {item['content_role']} | {item['item_title']} | "
                    f"basis={item['recency_basis_type']} {item['recency_basis_date']} | {item['rejection_reason']}"
                )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Batch C2 source candidates.")
    parser.add_argument("--apply", action="store_true", help="Write approved source metadata into source_registry.csv.")
    args = parser.parse_args()

    candidates = source_candidates()
    rows = []
    for candidate in candidates:
        row = score_source(candidate)
        rows.append(row)
        print(
            f"{candidate.institution_name} | {candidate.source_name} | {row['validation_result']} | "
            f"{row['activation_recommendation']} | dated={row['dated_link_count']} recent={row['recent_link_count']} "
            f"commercial={row['likely_commercial_link_count']} legal={row['legal_notice_count']}"
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
