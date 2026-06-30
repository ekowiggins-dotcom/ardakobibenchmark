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
VALIDATION_PATH = DATA_DIR / "batch_a_source_validation_candidates.csv"
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
    "likely_kobi_link_count",
    "retail_noise_ratio",
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

BANK_POSITIVE = {
    "Alternatif Bank": re.compile(
        r"(kobi|ticari|kurumsal|bonus business|pos|sanal pos|yazarkasa pos|üye işyeri|uye isyeri|"
        r"tahsilat|nakit yönetimi|nakit yonetimi|dış ticaret|dis ticaret|ticari hesap|vov tüzel|"
        r"vov tuzel|işletme|isletme|kgf|ihracat|iş birliği|is birligi|api|dijital ticari)",
        re.I,
    ),
    "DenizBank": re.compile(
        r"(kobi|işim için|isim icin|ticari|işletme|isletme|esnaf|pos|üye işyeri|uye isyeri|"
        r"üretici pos|uretici pos|ticari kart|işletme kart|isletme kart|tahsilat|nakit yönetimi|"
        r"nakit yonetimi|dbs|hesap hareketi|güvenli ödeme|guvenli odeme|dış ticaret|dis ticaret|"
        r"ihracat|nefes kredisi|tobb|kgf|turizm|tarım işletmesi|tarim isletmesi|iş birliği|is birligi|dijital ticari)",
        re.I,
    ),
    "ING": re.compile(
        r"(işiniz için|isiniz icin|kobi|ticari|ing business|pos ekstra|cebimde pos|nakit pos|sağlık pos|"
        r"saglik pos|yazarkasa pos|tr karekod|üye işyeri|uye isyeri|şirket kredi kartı|sirket kredi karti|"
        r"dijital ticari|şubeye gitmeden|subeye gitmeden|nakit yönetimi|nakit yonetimi|tahsilat|"
        r"açık bankacılık|acik bankacilik|api|e-fatura|dış ticaret|dis ticaret|leasing|kobi finansmanı|"
        r"kobilere|masrafsiz bankacilik)",
        re.I,
    ),
    "TEB": re.compile(
        r"(kobi|kobiyim|kobi’yim|cepteteb işte|cepteteb iste|ticari|bonus business|pos|üye işyeri|"
        r"uye isyeri|tahsilat|t-kart|dbs|sanal hesap|nakit ve çek|nakit ve cek|dijital ticari|"
        r"figopara|osbük|osbuk|osb|kadın patron|kadin patron|girişim bankacılığı|girisim bankaciligi|"
        r"ihracat|yeşil dönüşüm|yesil donusum|sürdürülebilir finansman|agir ticari|ağır ticari|"
        r"dış ticaret|dis ticaret|kgf|kamu finansmanı|kamu finansmani)",
        re.I,
    ),
}
BANK_NEGATIVE = {
    "Alternatif Bank": re.compile(
        r"(restoran|kozmetik|giyim|sevgililer günü|sevgililer gunu|okul alışverişi|okul alisverisi|"
        r"kişisel kart|kisisel kart|bireysel vov kart|akaryakıt|akaryakit|tatil|sinema|çekiliş|cekilis)",
        re.I,
    ),
    "DenizBank": re.compile(
        r"(deniz yatırım|deniz yatirim|günlük bülten|gunluk bulten|hisse analizi|bist|viop|"
        r"piyasa sabah notu|bireysel ihtiyaç|bireysel ihtiyac|emekli|afili|özel bankacılık|"
        r"ozel bankacilik|konut kredisi|kişisel kart|kisisel kart|tatil|restoran)",
        re.I,
    ),
    "ING": re.compile(
        r"(emekli|bireysel ihtiyaç|bireysel ihtiyac|turuncu hesap|konut|taşıt|tasit|"
        r"bireysel kart|çalışan deneyimi|calisan deneyimi|spor sponsorluğu|spor sponsorlugu|"
        r"generic csr|tasarruf araştırması|tasarruf arastirmasi)",
        re.I,
    ),
    "TEB": re.compile(
        r"(cepteteb bireysel|restoran|veteriner|petshop|sinema|tiyatro|bireysel kredi kartı|"
        r"bireysel kredi karti|bireysel mevduat|teb yatırım|teb yatirim|kariyer|employer|"
        r"sponsorluk|sponsorship|kobi akademi|/arama/)",
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
    exact_registry: bool = True


def batch_a_candidates() -> list[Candidate]:
    press = "İş Birlikleri; Kampanyalar; KOBİ Kredileri; Ödemeler ve POS"
    pay = "Ödemeler ve POS; Üye İşyeri; Tahsilat; Nakit Yönetimi"
    kobi = "KOBİ Kredileri; Nakit Yönetimi; Dijital KOBİ Yolculuğu; Kampanyalar"
    return [
        Candidate("Alternatif Bank", "https://www.alternatifbank.com.tr/hakkimizda/basin-odasi", "Alternatif Bank Basın Odası", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", press),
        Candidate("Alternatif Bank", "https://www.alternatifbank.com.tr/hakkimizda/basin-odasi/basin-bultenleri-ve-duyurular", "Alternatif Bank Basın Bültenleri ve Duyurular", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", press),
        Candidate("Alternatif Bank", "https://www.alternatifbank.com.tr/kampanyalar", "Alternatif Bank Kampanyalar", "Resmi Kampanya Sayfası", "weekly_development", "weekly_development", "Kampanyalar; KOBİ; Ticari Kartlar; POS"),
        Candidate("Alternatif Bank", "https://www.alternatifbank.com.tr/kurumsal/nakit-yonetimi/tahsilat-cozumleri", "Alternatif Bank Tahsilat Çözümleri", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("Alternatif Bank", "https://www.alternatifbank.com.tr/kurumsal/nakit-yonetimi/pos-ve-uye-isyeri-hizmetleri", "Alternatif Bank POS ve Üye İşyeri Hizmetleri", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("Alternatif Bank", "https://www.alternatifbank.com.tr/kurumsal/nakit-yonetimi/pos-ve-uye-isyeri-hizmetleri/pos-urunleri/yazarkasa-pos", "Alternatif Bank Yazarkasa POS", "Resmi POS Sayfası", "benchmark_fact", "ignore", pay, "Structural product example only."),
        Candidate("Alternatif Bank", "https://www.alternatifbank.com.tr/kampanyalar/alternatif-bank-otomotiv-kampanyasi", "Alternatif Bank Otomotiv Kampanyası", "Resmi Kampanya Sayfası", "weekly_development", "ignore", "Kampanyalar; Ticari Kartlar", "Parser test example only."),
        Candidate("DenizBank", "https://www.denizbank.com/hakkimizda/medya-merkezi/basinda-denizbank", "DenizBank Medya Merkezi / Basında DenizBank", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", press),
        Candidate("DenizBank", "https://www.denizbank.com/isim-icin", "DenizBank İşim İçin", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", kobi),
        Candidate("DenizBank", "https://www.denizbank.com/krediler/kobi-bankaciligi", "DenizBank KOBİ Kredileri", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", kobi),
        Candidate("DenizBank", "https://www.denizbank.com/isim-icin/kobi-bankaciligi/uye-isyeri-ve-pos-islemleri/pos-urunleri", "DenizBank POS Ürünleri", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("DenizBank", "https://www.denizbank.com/isim-icin/kobi-bankaciligi/uye-isyeri-ve-pos-islemleri/uye-isyeri-hizmetleri", "DenizBank Üye İşyeri Hizmetleri", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("DenizBank", "https://www.denizbank.com/isim-icin/kobi-bankaciligi/nakit-yonetimi-ve-dis-ticaret/nakit-yonetimi/hesap-hareketi-entegrasyonu", "DenizBank Hesap Hareketi Entegrasyonu", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("DenizBank", "https://www.denizbank.com/isim-icin/kobi-bankaciligi/nakit-yonetimi-ve-dis-ticaret/nakit-yonetimi/dogrudan-borclandirma-sistemi", "DenizBank Doğrudan Borçlandırma Sistemi", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("DenizBank", "https://www.denizbank.com/isim-icin/kobi-bankaciligi/nakit-yonetimi-ve-dis-ticaret/nakit-yonetimi/guvenli-arac-alim-satim-sistemi", "DenizBank Güvenli Araç Alım Satım Sistemi", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("ING", "https://www.ing.com.tr/tr/isiniz-icin", "ING İşiniz İçin", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", kobi),
        Candidate("ING", "https://www.ing.com.tr/tr/ing/basin-odasi/basin-bultenleri/2026", "ING Basın Bültenleri 2026", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", press),
        Candidate("ING", "https://www.ing.com.tr/tr/ing/basin-odasi/basin-bultenleri/2025", "ING Basın Bültenleri 2025", "Resmi Basın Bülteni Sayfası", "weekly_development", "ignore", press, "Archive fallback only; not active while 2026 works."),
        Candidate("ING", "https://www.ing.com.tr/tr/ing/basin-odasi/basin-bultenleri/2024", "ING Basın Bültenleri 2024", "Resmi Basın Bülteni Sayfası", "weekly_development", "ignore", press, "Archive fallback only; not active while 2026 works."),
        Candidate("ING", "https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri", "ING Üye İşyeri", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("ING", "https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/uye-is-yeri-hizmetleri", "ING Üye İşyeri Hizmetleri", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("ING", "https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/pos-urunleri", "ING POS Ürünleri", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("ING", "https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/ing-cebimde-pos", "ING Cebimde POS", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("ING", "https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/pos-ekstra", "ING POS Ekstra", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("ING", "https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/kobi-nakit-pos", "ING KOBİ Nakit POS", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("ING", "https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/saglik-pos", "ING Sağlık POS", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("ING", "https://www.ing.com.tr/tr/isiniz-icin/uye-isyeri/karekod-odeme", "ING Karekod Ödeme", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("TEB", "https://www.teb.com.tr/teb-hakkinda/basin-aciklamalari/", "TEB Basın Açıklamaları", "Resmi Basın Bülteni Sayfası", "weekly_development", "weekly_development", press),
        Candidate("TEB", "https://www.teb.com.tr/kobiyim/", "TEB KOBİ'yim", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", kobi),
        Candidate("TEB", "https://www.teb.com.tr/kobiyim/tahsilat-cozumleri/", "TEB Tahsilat Çözümleri", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", pay),
        Candidate("TEB", "https://www.teb.com.tr/kobiyim/cepteteb-kurumsal-sube/", "TEB CEPTETEB Kurumsal Şube", "Resmi Ürün Sayfası", "benchmark_fact", "benchmark_fact", "Dijital KOBİ Yolculuğu; Nakit Yönetimi"),
        Candidate("TEB", "https://www.teb.com.tr/kobiyim/teb-bonus-business-card/", "TEB Bonus Business Card", "Resmi POS Sayfası", "benchmark_fact", "benchmark_fact", "Ticari Kartlar; Ödemeler ve POS"),
        Candidate("TEB", "https://www.teb.com.tr/kobiyim/osb-urun/", "TEB OSB Ürün", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", "OSB; KOBİ Kredileri; Kampanyalar"),
        Candidate("TEB", "https://www.teb.com.tr/kobiyim/kamu-finansmani/", "TEB Kamu Finansmanı", "Resmi KOBİ Sayfası", "benchmark_fact", "benchmark_fact", "Kamu Finansmanı; KOBİ Kredileri"),
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
        "likely_kobi_link_count": "0",
        "retail_noise_ratio": "0.00",
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
            base.update(
                {
                    "validation_result": "Invalid",
                    "activation_recommendation": "ignore",
                    "reason": f"Redirected to not-found page: {response.url}",
                }
            )
            return base

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        page_text = soup.get_text(" ", strip=True)
        useful = dated = kobi = noisy = 0
        total_considered = 0
        for anchor in soup.find_all("a"):
            href = clean(anchor.get("href"))
            if not href:
                continue
            url = urljoin(response.url, href)
            if not same_site(response.url, url):
                continue
            parent_text = clean(anchor.parent.get_text(" ", strip=True) if anchor.parent else "")
            label = clean(anchor.get_text(" ", strip=True))
            blob = f"{label} {url} {parent_text}"
            if GENERIC_NAV_RE.search(blob):
                continue
            total_considered += 1
            has_positive = bool(positive_re.search(blob))
            has_negative = bool(negative_re.search(blob))
            useful += int(has_positive or DATE_RE.search(blob) is not None)
            dated += int(DATE_RE.search(blob) is not None and not has_negative)
            kobi += int(has_positive and not has_negative)
            noisy += int(has_negative and not has_positive)
        ratio = noisy / max(1, total_considered)
        page_date_count = len(DATE_RE.findall(page_text[:50000]))
        base.update(
            {
                "useful_link_count": str(useful),
                "dated_link_count": str(dated),
                "likely_kobi_link_count": str(kobi),
                "retail_noise_ratio": f"{ratio:.2f}",
            }
        )

        if candidate.intended_role == "ignore":
            base.update(
                {
                    "validation_result": "Validated for structural testing",
                    "activation_recommendation": "ignore",
                    "reason": candidate.notes or "Structural/test URL; do not activate as source.",
                }
            )
            return base
        if candidate.intended_role == "benchmark_fact":
            if len(page_text) >= 500 and (kobi > 0 or positive_re.search(page_text[:30000])):
                base.update(
                    {
                        "validation_result": "Valid benchmark-only source",
                        "activation_recommendation": "activate_benchmark_fact",
                        "reason": "Evergreen SME/commercial product content; no reliable dated detail feed required.",
                    }
                )
            else:
                base.update(
                    {
                        "validation_result": "Static/no dated links",
                        "activation_recommendation": "ignore",
                        "reason": "Static page did not expose enough SME/commercial content.",
                    }
                )
            return base

        if candidate.intended_role == "weekly_development":
            if ratio > 0.35 and kobi == 0:
                base.update(
                    {
                        "validation_result": "Retail-noise source",
                        "activation_recommendation": "ignore",
                        "reason": "Retail/noise dominates and no explicit SME/commercial links were found.",
                    }
                )
            elif dated > 0 or page_date_count > 0:
                base.update(
                    {
                        "validation_result": "Valid weekly source",
                        "activation_recommendation": "activate_weekly_development",
                        "reason": f"Dated source surface detected; page_date_count={page_date_count}, dated_link_count={dated}.",
                    }
                )
            elif kobi > 0 and useful >= 3:
                base.update(
                    {
                        "validation_result": "Static/no dated links",
                        "activation_recommendation": "ignore",
                        "reason": "SME/commercial links exist, but no reliable visible publication/start dates were detected.",
                    }
                )
            else:
                base.update(
                    {
                        "validation_result": "Static/no dated links",
                        "activation_recommendation": "ignore",
                        "reason": "No dated item-level feed detected.",
                    }
                )
            return base
        return base
    except Exception as exc:
        base["reason"] = str(exc)[:300]
        return base


def deactivate_unapproved_batch_a(registry: pd.DataFrame, approved_urls: set[str], reviewed_urls: set[str]) -> pd.DataFrame:
    batch_ids = {"alternatif_bank", "denizbank", "ing", "teb"}
    for idx, row in registry[registry["institution_id"].astype(str).isin(batch_ids)].iterrows():
        key = source_key(row.get("url", ""))
        if key in approved_urls:
            continue
        if clean(row.get("source_validation_status")) in {"Legacy active weekly source"}:
            continue
        if key in reviewed_urls or truthy(row.get("mvp_active")) or clean(row.get("extraction_mode")) in {"weekly_development", "both"}:
            registry.at[idx, "active"] = "False"
            registry.at[idx, "mvp_active"] = "False"
            registry.at[idx, "collection_method"] = "manual"
            registry.at[idx, "source_validation_status"] = "Disabled by Batch A exact-source review"
            registry.at[idx, "collector_capability"] = "manual"
            registry.at[idx, "exclusion_reason"] = "Not approved by focused Batch A exact URL validation."
    return registry


def upsert_approved_sources(registry: pd.DataFrame, candidates: list[Candidate], validation: pd.DataFrame) -> pd.DataFrame:
    registry = registry.copy()
    approved = validation[validation["activation_recommendation"].isin(["activate_weekly_development", "activate_benchmark_fact"])].copy()
    approved_urls = {source_key(url) for url in approved["candidate_url"].astype(str)}
    reviewed_urls = {source_key(url) for url in validation["candidate_url"].astype(str)}
    registry = deactivate_unapproved_batch_a(registry, approved_urls, reviewed_urls)
    existing_by_url = {source_key(row.get("url")): idx for idx, row in registry.iterrows()}
    candidate_by_url = {source_key(item.url): item for item in candidates}
    now = datetime.now(timezone.utc).isoformat()
    for _, result in approved.iterrows():
        key = source_key(result["candidate_url"])
        candidate = candidate_by_url[key]
        institution_id, institution_name = canonical_institution(candidate.institution_name)
        recommendation = clean(result["activation_recommendation"])
        active = "True"
        mvp_active = "True" if recommendation == "activate_weekly_development" else "False"
        method = "static_scrape"
        mode = "weekly_development" if recommendation == "activate_weekly_development" else "benchmark_fact"
        payload = {
            "tier": "Tier 1",
            "institution_id": institution_id,
            "institution_name": institution_name,
            "source_name": candidate.source_name,
            "source_type": candidate.source_type,
            "url": candidate.url,
            "collection_method": method,
            "update_frequency": "Weekly",
            "reliability_level": "Yüksek",
            "strategic_themes": candidate.strategic_themes,
            "active": active,
            "notes": clean(result["reason"]),
            "extraction_mode": mode,
            "coverage_scope": "KOBİ Rakip Banka",
            "coverage_priority": "A",
            "sme_relevance": "Yüksek" if institution_name in {"DenizBank", "TEB"} else "Orta",
            "source_validation_status": clean(result["validation_result"]),
            "collector_capability": method,
            "mvp_active": mvp_active,
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
    path = DATA_DIR / f"batch_a_source_validation_report_{timestamp}.md"
    lines = [
        "# Batch A Source Validation Report",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- candidates_tested: {len(validation)}",
        f"- activate_weekly_development: {int(validation['activation_recommendation'].eq('activate_weekly_development').sum())}",
        f"- activate_benchmark_fact: {int(validation['activation_recommendation'].eq('activate_benchmark_fact').sum())}",
        f"- ignored/manual/browser: {int(~validation['activation_recommendation'].isin(['activate_weekly_development','activate_benchmark_fact']).sum())}",
        "",
    ]
    for institution, group in validation.groupby("institution_name", sort=False):
        lines.extend([f"## {institution}", ""])
        for _, row in group.iterrows():
            lines.append(
                "- {role} | {result} | {source} | HTTP {http} | useful={useful} dated={dated} kobi={kobi} noise={noise} | {url} | {reason}".format(
                    role=row["activation_recommendation"],
                    result=row["validation_result"],
                    source=row["proposed_source_name"],
                    http=row["http_status"],
                    useful=row["useful_link_count"],
                    dated=row["dated_link_count"],
                    kobi=row["likely_kobi_link_count"],
                    noise=row["retail_noise_ratio"],
                    url=row["candidate_url"],
                    reason=row["reason"],
                )
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate exact Batch A source candidates before Claude.")
    parser.add_argument("--apply", action="store_true", help="Upsert approved rows into source_registry.csv.")
    args = parser.parse_args()

    candidates = batch_a_candidates()
    rows = []
    for candidate in candidates:
        result = fetch_and_score(candidate)
        rows.append(result)
        print(
            f"{candidate.institution_name} | {candidate.source_name} | {result['validation_result']} | "
            f"{result['activation_recommendation']} | useful={result['useful_link_count']} dated={result['dated_link_count']} "
            f"kobi={result['likely_kobi_link_count']} noise={result['retail_noise_ratio']}"
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
