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
VALIDATION_PATH = DATA_DIR / "batch_b_source_validation_candidates.csv"
sys.path.insert(0, str(ROOT_DIR))

from utils.institution_aliases import canonical_institution


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
    "exclusion_reason",
    "last_validated_at",
]
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
    "likely_sme_link_count",
    "operational_notice_count",
    "retail_noise_ratio",
    "repeated_navigation_ratio",
    "collector_capability",
    "validation_result",
    "activation_recommendation",
    "reason",
    "checked_at",
]

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
BLOCKED_RE = re.compile(r"(captcha|access denied|forbidden|cloudflare|request blocked|güvenlik doğrulaması)", re.I)
GENERIC_NAV_RE = re.compile(r"(login|giriş|giris|arama|search|site haritası|site-haritasi|menü|menu|çerez|cerez|kvkk)", re.I)
NAV_ATTR_RE = re.compile(r"(nav|menu|footer|header|sidebar|breadcrumb|cookie|social|sosyal)", re.I)
OPERATIONAL_NOTICE_RE = re.compile(
    r"(sistem çalışması|sistem calismasi|bakım çalışması|bakim calismasi|piyasa.*yarım gün|"
    r"zaman aşımı|zaman asimi|pay kaydileştirme|mevzuat bildirimi|kesinti|çalışma saatleri|calisma saatleri|"
    r"işlem saatleri|islem saatleri|tatil)",
    re.I,
)

BANK_POSITIVE = {
    "Şekerbank": re.compile(
        r"(esnaf|kobi|işletme|isletme|ticari|pos|üye işyeri|uye isyeri|pos kart|sanal pos|android pos|"
        r"qr ödeme|qr odeme|ökc|okc|narpos|ticari kart|tahsilat|e-fatura|efatura|şef|sef|nakit yönetimi|"
        r"yerinde kredi|tarım finansmanı|tarim finansmani|kadın girişimci|kadin girisimci|kadın kooperatifi|"
        r"kgf|ebrd|efse|sektörel iş birliği|osbük|osbuk|esnaf odası|ihracat|sürdürülebilir tarım)",
        re.I,
    ),
    "Fibabanka": re.compile(
        r"(kobi|esnaf|küçük işletme|kucuk isletme|işletme|isletme|ticari|efsane kobi kredisi|"
        r"efsane ticari kredi|fibabankabiz|ticari müşteri|ticari musteri|business kredi kartı|business kredi karti|"
        r"kiraz hesap işinizde|kiraz hesap isinizde|pos|üye işyeri|uye isyeri|sanal pos|alt üye işyeri|"
        r"nakit yönetimi|tahsilat|dijital teminat|dijital çek|dijital cek|açık bankacılık|acik bankacilik|"
        r"servis bankacılığı|iş birliği|is birligi|tarım|tedarikçi finansmanı)",
        re.I,
    ),
    "Anadolubank": re.compile(
        r"(kobi|ticari|işletme|isletme|işiniz için|isiniz icin|ticari ve kobi kredileri|kadın girişimci|"
        r"kadin girisimci|kgf|ige|ihracat|dış ticaret|dis ticaret|nakit yönetimi|dbs|tfs|açık bankacılık|"
        r"hesap bilgisi|ödeme ve tahsilat|cebpte pos|cepte pos|ödeal|odeal|business worldcard|troy business|"
        r"tarım kart|tarim kart|tarım işletmesi|şirketleşme|kobi yazılımı|işletme verimliliği|dijital imza|"
        r"karbon muhasebesi|tedarikçi finansmanı)",
        re.I,
    ),
    "Odeabank": re.compile(
        r"(ticari|kurumsal|kobi|işletme|isletme|nakit yönetimi|tahsilat|ödeme|odeme|dbs|tedarikçi finansmanı|"
        r"dış ticaret|dis ticaret|ihracat|teminat mektubu|ticari kredi|ticari müşteri|commercial boost|"
        r"rm dashboard|portföy yönetimi|ticari analitik|müşteri temsilcisi|dijital ticari|proje finansmanı|"
        r"işletme sermayesi|ticari mevduat|iş insanları|sektörel finansman)",
        re.I,
    ),
}
BANK_NEGATIVE = {
    "Şekerbank": re.compile(
        r"(sistem çalışması|bakım çalışması|piyasalar yarım gün|zaman aşımı|pay kaydileştirme|"
        r"bireysel kart|tatil|restoran|sinema|bireysel yatırım|mevzuat bildirimi)",
        re.I,
    ),
    "Fibabanka": re.compile(
        r"(bireysel efsane kredi|kiraz hesap bireysel|ihtiyaç kredisi|konut kredisi|bireysel yatırım|"
        r"fx market|borsa market|otomobil çekilişi|bireysel kart|lifestyle|bilgi bankası|seo|"
        r"form|sözleşme|sozlesme|kvkk)",
        re.I,
    ),
    "Anadolubank": re.compile(
        r"(özel bankacılık|ozel bankacilik|lounge|havalimanı|restoran|kahve|tur|spa|bireysel mastercard|"
        r"bireysel troy|otopark|ulaşım kampanyası|çocuk etkinliği|alışveriş|lifestyle|günlük piyasa bülteni)",
        re.I,
    ),
    "Odeabank": re.compile(
        r"(finansal okuryazarlık|yatırım alışkanlıkları|yatırım odaklı podcast|odea radyo|o.?blog|o.?mag|"
        r"bireysel fon|bireysel yatırım|kültür sanat|tiyatro|çocuk etkinliği|lifestyle|bireysel axess|"
        r"özel bankacılık|generic sustainability|podcast)",
        re.I,
    ),
}


@dataclass(frozen=True)
class Candidate:
    institution_name: str
    url: str
    source_name: str
    source_type: str
    proposed_mode: str
    intended_role: str
    strategic_themes: str
    notes: str = ""


def batch_b_candidates() -> list[Candidate]:
    press = "KOBİ Kredileri; Kampanyalar; İş Birlikleri; Dijital KOBİ Yolculuğu"
    pos = "Ödemeler ve POS; Tahsilat; Nakit Yönetimi"
    cash = "Nakit Yönetimi; Dış Ticaret; Dijital KOBİ Yolculuğu"
    return [
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/hakkimizda/basin-odasi", "Şekerbank Basın Odası", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", press),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi", "Şekerbank Esnaf KOBİ", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", press),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/kobi", "Şekerbank KOBİ", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", press),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/kampanyalar", "Şekerbank Esnaf KOBİ Kampanyalar", "Resmi Kampanya Sayfası", "weekly_development", "weekly_development", "Kampanyalar; KOBİ Kredileri"),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/kampanyalar/kobi-kampanyalari", "Şekerbank KOBİ Kampanyaları", "Resmi Kampanya Sayfası", "weekly_development", "weekly_development", "Kampanyalar; KOBİ Kredileri"),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos", "Şekerbank Üye İşyeri POS", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pos),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/pos-kampanyalari", "Şekerbank POS Kampanyaları", "Resmi Kampanya Sayfası", "weekly_development", "weekly_development", pos),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/okc-yazar-kasa-pos", "Şekerbank ÖKC Yazar Kasa POS", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pos),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/narpos", "Şekerbank NarPOS", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pos),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/esnafkobi-kredileri/kobi-kredileri/e-fatura-finansmani", "Şekerbank e-Fatura Finansmanı", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", "KOBİ Kredileri; Nakit Yönetimi"),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/sektorel-destek-ve-is-birlikleri", "Şekerbank Sektörel Destek ve İş Birlikleri", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", "Ekosistem İş Birlikleri"),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/pos-kampanyalari/yeni-musterilere-ozel-pos-kampanyasi", "Şekerbank Yeni Müşterilere Özel POS Kampanyası", "Resmi Kampanya Sayfası", "weekly_development", "ignore", pos, "Parser test item; source değil."),
        Candidate("Şekerbank", "https://www.sekerbank.com.tr/esnaf-kobi/uye-isyeri-pos/pos-kampanyalari/eczaci-musterilerimize-ozel-pos-kampanyasi", "Şekerbank Eczacı POS Kampanyası", "Resmi Kampanya Sayfası", "weekly_development", "ignore", pos, "Parser test item; source değil."),
        Candidate("Fibabanka", "https://www.fibabanka.com.tr/hakkimizda/duyuru-ve-haberler/2026", "Fibabanka Duyuru ve Haberler 2026", "Resmi Basın Bülteni Sayfası", "weekly_development", "manual", press, "Accordion-style page; no item-level URLs in static HTML."),
        Candidate("Fibabanka", "https://www.fibabanka.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri/2026", "Fibabanka Basın Bültenleri 2026", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", press),
        Candidate("Fibabanka", "https://www.fibabanka.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri/2025", "Fibabanka Basın Bültenleri 2025", "Resmi Basın Bülteni Sayfası", "weekly_development", "ignore", press, "Fallback archive; 2026 structure test edilir."),
        Candidate("Fibabanka", "https://www.fibabanka.com.tr/kampanyalar/guncel-ozel-kampanyalar", "Fibabanka Güncel Özel Kampanyalar", "Resmi Kampanya Sayfası", "weekly_development", "weekly_development", "Kampanyalar; KOBİ Kredileri; Ticari Kartlar"),
        Candidate("Fibabanka", "https://www.fibabanka.com.tr/kucuk-isletme-ve-tarim/kobi-kredileri", "Fibabanka KOBİ Kredileri", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", "KOBİ Kredileri"),
        Candidate("Fibabanka", "https://www.fibabanka.com.tr/kucuk-isletme-ve-tarim/isletme-ve-tarim-kredi-basvuru-formu", "Fibabanka İşletme ve Tarım Kredi Başvuru", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", "KOBİ Kredileri; Tarım Finansmanı"),
        Candidate("Fibabanka", "https://www.fibabanka.com.tr/ticari-musteri-olmak-istiyorum", "Fibabanka Ticari Müşteri Olmak İstiyorum", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", "Dijital KOBİ Yolculuğu"),
        Candidate("Fibabanka", "https://www.fibabanka.com.tr/ticari-kurumsal/nakit-yonetim-urunleri", "Fibabanka Nakit Yönetim Ürünleri", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", cash),
        Candidate("Fibabanka", "https://www.fibabanka.com.tr/tuzel-musteriler-bankacilik-islemleri", "Fibabanka Tüzel Müşteri Ücretleri", "Resmi Ücret/Pricing Sayfası", "benchmark_fact", "benchmark_fact", "Pricing; Nakit Yönetimi"),
        Candidate("Anadolubank", "https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar", "Anadolubank Basın Bültenleri ve Röportajlar", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", press),
        Candidate("Anadolubank", "https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2026", "Anadolubank Basın Bültenleri 2026", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", press),
        Candidate("Anadolubank", "https://www.anadolubank.com.tr/sizin-icin", "Anadolubank Sizin İçin Kampanya Yüzeyi", "Resmi Kampanya Sayfası", "weekly_development", "ignore", "Kampanyalar", "Retail/lifestyle noise riski yüksek."),
        Candidate("Anadolubank", "https://www.anadolubank.com.tr/isiniz-icin/nakit-yonetimi/acik-bankacilik-cozumlerimiz", "Anadolubank Açık Bankacılık Çözümleri", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", cash),
        Candidate("Anadolubank", "https://www.anadolubank.com.tr/isiniz-icin/nakit-yonetimi/dogrudan-borclandirma-sistemi", "Anadolubank Doğrudan Borçlandırma Sistemi", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", cash),
        Candidate("Anadolubank", "https://www.anadolubank.com.tr/sizin-icin/nakit-yonetimi", "Anadolubank Nakit Yönetimi", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", cash),
        Candidate("Anadolubank", "https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2023/anadolubanktan-7-24-ticareti-destekleyen-hizmet", "Anadolubank 7/24 Ticareti Destekleyen Hizmet", "Resmi Basın Bülteni Sayfası", "weekly_development", "ignore", cash, "Historical parser test item."),
        Candidate("Anadolubank", "https://www.anadolubank.com.tr/hakkimizda/kurumsal-iletisim/basin-bultenleri-ve-roportajlar/2022/anadolubank-pos-artik-cebinde", "Anadolubank POS Artık Cebinde", "Resmi Basın Bülteni Sayfası", "weekly_development", "ignore", pos, "Historical parser test item."),
        Candidate("Odeabank", "https://www.odeabank.com.tr/hakkimizda/basin-bultenleri", "Odeabank Basın Bültenleri", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", press),
        Candidate("Odeabank", "https://www.odeabank.com.tr/kampanyalar", "Odeabank Kampanyalar", "Resmi Kampanya Sayfası", "weekly_development", "weekly_development", "Kampanyalar; Ticari Kartlar"),
        Candidate("Odeabank", "https://www.odeabank.com.tr/ticari", "Odeabank Ticari", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", cash),
        Candidate("Odeabank", "https://www.odeabank.com.tr/ticari/nakit-yonetimi", "Odeabank Nakit Yönetimi", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", cash),
        Candidate("Odeabank", "https://www.odeabank.com.tr/ticari/dis-ticaret-ve-finansman/dis-ticaret-ve-nakit-yonetimi-uzman-hatti", "Odeabank Dış Ticaret ve Nakit Yönetimi Uzman Hattı", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", "Dış Ticaret; Nakit Yönetimi"),
        Candidate("Odeabank", "https://www.odeabank.com.tr/hakkimizda/basin-bultenleri/odeabankin-ticari-bankacilik-projesine-qorustan-1incilik-odulu", "Odeabank Ticari Bankacılık Projesi Ödülü", "Resmi Basın Bülteni Sayfası", "weekly_development", "ignore", "Yönetici Bilgilendirme; Dijital Ticari", "Management-awareness parser test item; source değil."),
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


def next_source_id(registry: pd.DataFrame) -> str:
    nums = []
    for value in registry.get("source_id", pd.Series(dtype=str)).astype(str):
        match = re.search(r"REG-(\d+)", value)
        if match:
            nums.append(int(match.group(1)))
    return f"REG-{(max(nums) if nums else 0) + 1:03d}"


def read_registry() -> pd.DataFrame:
    df = pd.read_csv(REGISTRY_PATH, encoding="utf-8-sig").fillna("")
    for column in BASE_COLUMNS + COVERAGE_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df.astype({column: "object" for column in df.columns})


def local_anchor_text(anchor) -> str:
    parts = [clean(anchor.get_text(" ", strip=True))]
    parent = anchor.parent
    if parent:
        parts.append(clean(parent.get_text(" ", strip=True)))
    return " ".join(part for part in parts if part)


def count_navigation_links(soup: BeautifulSoup) -> tuple[int, int]:
    total = 0
    nav = 0
    for anchor in soup.find_all("a"):
        total += 1
        lineage = []
        node = anchor
        for _ in range(4):
            if not node:
                break
            attrs = getattr(node, "attrs", {}) or {}
            classes = attrs.get("class", "")
            if isinstance(classes, list):
                classes = " ".join(str(value) for value in classes)
            lineage.append(" ".join(str(value) for value in [node.name, attrs.get("id", ""), classes, attrs.get("role", "")] if value))
            node = node.parent
        if NAV_ATTR_RE.search(" ".join(lineage)):
            nav += 1
    return total, nav


def remove_global_noise(soup: BeautifulSoup) -> BeautifulSoup:
    clone = BeautifulSoup(str(soup), "html.parser")
    for tag in clone(["script", "style", "noscript", "svg", "header", "nav", "footer"]):
        tag.decompose()
    for tag in list(clone.find_all(True)):
        attrs = getattr(tag, "attrs", {}) or {}
        classes = attrs.get("class", "")
        if isinstance(classes, list):
            classes = " ".join(str(value) for value in classes)
        blob = " ".join(str(value) for value in [attrs.get("id", ""), classes, attrs.get("role", ""), attrs.get("aria-label", "")] if value)
        if NAV_ATTR_RE.search(blob):
            tag.decompose()
    return clone


def fetch_and_score(candidate: Candidate) -> dict[str, str]:
    checked_at = datetime.now(timezone.utc).isoformat()
    positive_re = BANK_POSITIVE[candidate.institution_name]
    negative_re = BANK_NEGATIVE[candidate.institution_name]
    base = {
        "institution_name": candidate.institution_name,
        "candidate_url": candidate.url,
        "proposed_source_name": candidate.source_name,
        "proposed_source_type": candidate.source_type,
        "proposed_extraction_mode": candidate.proposed_mode,
        "http_status": "",
        "final_url": "",
        "response_size": "0",
        "useful_link_count": "0",
        "dated_link_count": "0",
        "likely_sme_link_count": "0",
        "operational_notice_count": "0",
        "retail_noise_ratio": "0.00",
        "repeated_navigation_ratio": "0.00",
        "collector_capability": "static_scrape",
        "validation_result": "Invalid",
        "activation_recommendation": "ignore",
        "reason": "",
        "checked_at": checked_at,
    }
    try:
        response = requests.get(candidate.url, headers=HEADERS, timeout=20, allow_redirects=True)
        base["http_status"] = str(response.status_code)
        base["final_url"] = response.url
        base["response_size"] = str(len(response.content))
        html = response.text or ""
        if response.status_code in {401, 403, 429} or BLOCKED_RE.search(html[:6000]):
            base.update(
                {
                    "collector_capability": "browser_required",
                    "validation_result": "Browser required",
                    "activation_recommendation": "browser_required",
                    "reason": f"HTTP {response.status_code} or browser challenge detected.",
                }
            )
            return base
        if response.status_code >= 400:
            base["reason"] = f"HTTP {response.status_code}."
            return base
        if "filenotfound" in response.url.casefold():
            base.update({"reason": f"Redirected to not-found page: {response.url}"})
            return base

        soup = BeautifulSoup(html, "html.parser")
        total_nav_links, nav_links = count_navigation_links(soup)
        repeated_navigation_ratio = nav_links / max(1, total_nav_links)
        scoped = remove_global_noise(soup)
        page_text = scoped.get_text(" ", strip=True)
        useful = dated = sme = retail = operational = 0
        considered = 0
        for anchor in scoped.find_all("a"):
            href = clean(anchor.get("href"))
            if not href:
                continue
            url = urljoin(response.url, href)
            if not same_site(response.url, url):
                continue
            label = clean(anchor.get_text(" ", strip=True))
            blob = f"{label} {url} {local_anchor_text(anchor)}"
            if GENERIC_NAV_RE.search(blob):
                continue
            considered += 1
            has_positive = bool(positive_re.search(blob))
            has_negative = bool(negative_re.search(blob))
            has_date = DATE_RE.search(blob) is not None
            has_operational = OPERATIONAL_NOTICE_RE.search(blob) is not None
            useful += int(has_positive or has_date)
            dated += int(has_date and not has_negative and not has_operational)
            sme += int(has_positive and not has_negative and not has_operational)
            retail += int(has_negative and not has_positive)
            operational += int(has_operational and not has_positive)
        retail_noise_ratio = retail / max(1, considered)
        page_date_count = len(DATE_RE.findall(page_text[:50000]))
        page_positive = bool(positive_re.search(page_text[:30000]))
        base.update(
            {
                "useful_link_count": str(useful),
                "dated_link_count": str(dated),
                "likely_sme_link_count": str(sme),
                "operational_notice_count": str(operational),
                "retail_noise_ratio": f"{retail_noise_ratio:.2f}",
                "repeated_navigation_ratio": f"{repeated_navigation_ratio:.2f}",
            }
        )

        if candidate.intended_role == "ignore":
            base.update(
                {
                    "validation_result": "Validated for structural testing",
                    "activation_recommendation": "ignore",
                    "reason": candidate.notes or "Structural URL; not activated as source.",
                }
            )
            return base
        if candidate.intended_role == "manual":
            base.update(
                {
                    "validation_result": "Manual source - no item-level URLs",
                    "activation_recommendation": "manual",
                    "reason": candidate.notes or "Relevant source exists, but static HTML does not expose item-level URLs.",
                }
            )
            return base
        if candidate.intended_role == "benchmark_fact":
            if len(page_text) >= 500 and (sme > 0 or page_positive):
                base.update(
                    {
                        "validation_result": "Valid benchmark-only source",
                        "activation_recommendation": "activate_benchmark_fact",
                        "reason": "Evergreen SME/commercial product content; weekly item requires explicit dated material change.",
                    }
                )
            else:
                base.update(
                    {
                        "validation_result": "Static/no useful SME content",
                        "activation_recommendation": "ignore",
                        "reason": "No sufficient local SME/commercial product evidence after navigation removal.",
                    }
                )
            return base
        if candidate.intended_role == "weekly_development":
            if retail_noise_ratio > 0.35 and sme == 0:
                base.update(
                    {
                        "validation_result": "Retail-noise source",
                        "activation_recommendation": "ignore",
                        "reason": "Retail/noise dominates and no explicit local SME/commercial links were found.",
                    }
                )
            elif dated > 0 and (sme > 0 or page_positive):
                base.update(
                    {
                        "validation_result": "Valid weekly source",
                        "activation_recommendation": "activate_weekly_development",
                        "reason": f"Dated item surface plus SME/commercial evidence detected; page_date_count={page_date_count}.",
                    }
                )
            elif page_date_count > 0 and page_positive and considered > 0:
                base.update(
                    {
                        "validation_result": "Manual inspection needed",
                        "activation_recommendation": "manual",
                        "reason": "Dated page and SME evidence exist, but static HTML did not expose clean dated item links.",
                    }
                )
            elif sme > 0:
                base.update(
                    {
                        "validation_result": "Static/no dated links",
                        "activation_recommendation": "ignore",
                        "reason": "SME/commercial evidence exists, but no reliable publication/start-date feed was detected.",
                    }
                )
            else:
                base.update(
                    {
                        "validation_result": "Invalid weekly source",
                        "activation_recommendation": "ignore",
                        "reason": "No dated item-level SME/commercial feed detected after navigation removal.",
                    }
                )
            return base
        return base
    except Exception as exc:
        base["reason"] = str(exc)[:300]
        return base


def deactivate_unapproved_batch_b(registry: pd.DataFrame, approved_urls: set[str], reviewed_urls: set[str]) -> pd.DataFrame:
    batch_ids = {"sekerbank", "fibabanka", "anadolubank", "odeabank"}
    superseded_urls = {
        source_key("https://www.fibabanka.com.tr/kampanyalar"): "Superseded by exact current campaign URL.",
    }
    for idx, row in registry[registry["institution_id"].astype(str).isin(batch_ids)].iterrows():
        key = source_key(row.get("url", ""))
        if key in approved_urls:
            continue
        if (key in reviewed_urls or key in superseded_urls) and (truthy(row.get("active")) or truthy(row.get("mvp_active"))):
            registry.at[idx, "active"] = "False"
            registry.at[idx, "mvp_active"] = "False"
            registry.at[idx, "collection_method"] = "manual"
            registry.at[idx, "source_validation_status"] = "Disabled by Batch B exact-source review"
            registry.at[idx, "collector_capability"] = "manual"
            registry.at[idx, "exclusion_reason"] = superseded_urls.get(key, "Not approved by focused Batch B exact URL validation.")
    return registry


def upsert_approved_sources(registry: pd.DataFrame, candidates: list[Candidate], validation: pd.DataFrame) -> pd.DataFrame:
    registry = registry.copy()
    approved = validation[validation["activation_recommendation"].isin(["activate_weekly_development", "activate_benchmark_fact"])].copy()
    approved_urls = {source_key(url) for url in approved["candidate_url"].astype(str)}
    reviewed_urls = {source_key(url) for url in validation["candidate_url"].astype(str)}
    registry = deactivate_unapproved_batch_b(registry, approved_urls, reviewed_urls)
    existing_by_url = {source_key(row.get("url")): idx for idx, row in registry.iterrows()}
    candidate_by_url = {source_key(item.url): item for item in candidates}
    now = datetime.now(timezone.utc).isoformat()
    for _, result in approved.iterrows():
        key = source_key(result["candidate_url"])
        candidate = candidate_by_url[key]
        institution_id, institution_name = canonical_institution(candidate.institution_name)
        recommendation = clean(result["activation_recommendation"])
        mode = "weekly_development" if recommendation == "activate_weekly_development" else "benchmark_fact"
        payload = {
            "tier": "Tier 2",
            "institution_id": institution_id,
            "institution_name": institution_name,
            "source_name": candidate.source_name,
            "source_type": candidate.source_type,
            "url": candidate.url,
            "collection_method": "static_scrape",
            "update_frequency": "Weekly",
            "reliability_level": "Yüksek",
            "strategic_themes": candidate.strategic_themes,
            "active": "True",
            "notes": clean(result["reason"]),
            "extraction_mode": mode,
            "coverage_scope": "KOBİ Rakip Banka",
            "coverage_priority": "B",
            "sme_relevance": "Yüksek" if mode == "weekly_development" else "Orta",
            "source_validation_status": clean(result["validation_result"]),
            "collector_capability": "static_scrape",
            "mvp_active": "True" if mode == "weekly_development" else "False",
            "exclusion_reason": "",
            "last_validated_at": now,
        }
        if key in existing_by_url:
            idx = existing_by_url[key]
            for column, value in payload.items():
                registry.at[idx, column] = value
        else:
            payload["source_id"] = next_source_id(registry)
            registry = pd.concat([registry, pd.DataFrame([payload])], ignore_index=True)
            existing_by_url[key] = registry.index[-1]
    return registry


def write_registry(registry: pd.DataFrame) -> None:
    ordered = BASE_COLUMNS + COVERAGE_COLUMNS
    extras = [column for column in registry.columns if column not in ordered]
    registry.reindex(columns=ordered + extras).to_csv(REGISTRY_PATH, index=False, encoding="utf-8-sig")


def write_report(validation: pd.DataFrame) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DATA_DIR / f"batch_b_source_validation_report_{timestamp}.md"
    lines = [
        "# Batch B Source Validation Report",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- candidates_tested: {len(validation)}",
        f"- activate_weekly_development: {int(validation['activation_recommendation'].eq('activate_weekly_development').sum())}",
        f"- activate_benchmark_fact: {int(validation['activation_recommendation'].eq('activate_benchmark_fact').sum())}",
        f"- manual_or_browser: {int(validation['activation_recommendation'].isin(['manual','browser_required']).sum())}",
        f"- ignored: {int(validation['activation_recommendation'].eq('ignore').sum())}",
        "",
    ]
    for institution, group in validation.groupby("institution_name", sort=False):
        lines.extend([f"## {institution}", ""])
        for _, row in group.iterrows():
            lines.append(
                "- {role} | {result} | {source} | HTTP {http} | useful={useful} dated={dated} sme={sme} "
                "ops={ops} retail={retail} nav={nav} | {url} | {reason}".format(
                    role=row["activation_recommendation"],
                    result=row["validation_result"],
                    source=row["proposed_source_name"],
                    http=row["http_status"],
                    useful=row["useful_link_count"],
                    dated=row["dated_link_count"],
                    sme=row["likely_sme_link_count"],
                    ops=row["operational_notice_count"],
                    retail=row["retail_noise_ratio"],
                    nav=row["repeated_navigation_ratio"],
                    url=row["candidate_url"],
                    reason=row["reason"],
                )
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate exact Batch B source candidates before Claude.")
    parser.add_argument("--apply", action="store_true", help="Upsert approved rows into source_registry.csv.")
    args = parser.parse_args()

    candidates = batch_b_candidates()
    rows = []
    for candidate in candidates:
        result = fetch_and_score(candidate)
        rows.append(result)
        print(
            f"{candidate.institution_name} | {candidate.source_name} | {result['validation_result']} | "
            f"{result['activation_recommendation']} | useful={result['useful_link_count']} dated={result['dated_link_count']} "
            f"sme={result['likely_sme_link_count']} ops={result['operational_notice_count']} "
            f"retail={result['retail_noise_ratio']} nav={result['repeated_navigation_ratio']}"
        )
    validation = pd.DataFrame(rows).reindex(columns=VALIDATION_COLUMNS)
    validation.to_csv(VALIDATION_PATH, index=False, encoding="utf-8-sig")
    report_path = write_report(validation)
    if args.apply:
        registry = read_registry()
        registry = upsert_approved_sources(registry, candidates, validation)
        write_registry(registry)
        print(f"Updated registry: {REGISTRY_PATH.relative_to(ROOT_DIR)}")
    else:
        print("Dry run only; registry not updated. Use --apply to persist approved rows.")
    print(f"Candidate validation CSV: {VALIDATION_PATH.relative_to(ROOT_DIR)}")
    print(f"Validation report: {report_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
