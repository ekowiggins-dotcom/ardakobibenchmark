from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(ROOT_DIR))

from utils.translations import to_tr
from utils.date_utils import extract_date_semantics, parse_turkish_date
from utils.development_classifier import classify_actual_development
from utils.recency import bool_from_env, evaluate_recency, resolve_start_date

METADATA_PATH = DATA_DIR / "raw_documents_metadata.csv"
REGISTRY_PATH = DATA_DIR / "source_registry.csv"
RECENT_ITEMS_PATH = DATA_DIR / "recent_items.csv"
AUDIT_PATH = DATA_DIR / "recent_item_extraction_audit.csv"
SSL_VERIFY_FALLBACK_HOSTS = {"www.bddk.org.tr"}

RECENT_ITEM_COLUMNS = [
    "recent_item_id",
    "document_id",
    "source_id",
    "tier",
    "institution_id",
    "institution_name",
    "source_name",
    "source_type",
    "source_url",
    "item_title",
    "item_date",
    "item_url",
    "item_text",
    "item_hash",
    "canonical_item_url",
    "normalized_title",
    "content_fingerprint",
    "detected_at",
    "extraction_method",
    "relevance_status",
    "content_role",
    "item_quality",
    "publication_date",
    "announcement_date",
    "campaign_start_date",
    "campaign_end_date",
    "event_date_type",
    "recency_basis_date",
    "recency_basis_type",
    "recency_basis_reason",
    "is_active_campaign",
    "active_campaign_reason",
    "cluster_published",
    "cluster_id",
    "normalized_item_date",
    "date_confidence",
    "date_source",
    "is_recent",
    "recency_cutoff",
    "recency_reason",
    "development_candidate_type",
    "is_actual_development",
    "actual_development_reason",
]

AUDIT_COLUMNS = [
    "audit_id",
    "run_id",
    "institution_name",
    "source_id",
    "source_name",
    "candidate_title",
    "candidate_url",
    "canonical_item_url",
    "normalized_title",
    "content_fingerprint",
    "raw_date_text",
    "publication_date",
    "announcement_date",
    "campaign_start_date",
    "campaign_end_date",
    "event_date_type",
    "recency_basis_date",
    "recency_basis_type",
    "recency_basis_reason",
    "is_active_campaign",
    "active_campaign_reason",
    "normalized_item_date",
    "date_confidence",
    "date_source",
    "is_recent",
    "recency_cutoff",
    "recency_reason",
    "development_candidate_type",
    "is_actual_development",
    "actual_development_reason",
    "content_role",
    "content_role_reason",
    "item_quality",
    "saved_to_recent_items",
    "rejected_reason",
    "duplicate_of_recent_item_id",
    "checked_at",
]

WEEKLY_SOURCE_TYPES = {
    "Resmi Haber Sayfası",
    "Resmi Kampanya Sayfası",
    "Resmi Basın Bülteni Sayfası",
    "Official Campaign Page",
    "Official Press Release Page",
    "Regulator",
    "Industry Association",
    "News Site",
    "Fintech News",
    "Business News",
    "Regülatör",
    "Sektör Birliği",
    "Haber Sitesi",
    "Fintech Haberi",
    "İş/Ekonomi Haberi",
}

POSITIVE_RE = re.compile(
    r"(haber|duyuru|basin|basın|bulten|bülten|kampanya|yenilik|is-birligi|iş-birliği|"
    r"kobi|kobİ|esnaf|ticari|pos|uye-isyeri|üye-işyeri|odeme|ödeme|garanti-bbva-dan|"
    r"garanti-bbvadan|qnb-kobi|qnb-kobİ|üye işyeri|uye isyeri|sanal-pos|sanal pos|"
    r"link-pos|link pos|ceppos|cep-pos|yazar-kasa|yazar kasa|kobi-rahat|kobi rahat|"
    r"isim-icin|işim-için|parapuan|taksit|aidat|dijital-kanal|dijital kanal|"
    r"e-fatura|efatura|e-arşiv|e-arsiv|e-dönüşüm|e-donusum|tahsilat|"
    r"press|release|newsroom|announcement|campaign|partnership)",
    re.IGNORECASE,
)
NEGATIVE_RE = re.compile(
    r"(login|giris|giriş|arama|search|menu|footer|social|facebook|instagram|linkedin|"
    r"twitter|x\.com|youtube|gizlilik|cerez|çerez|yasal|kvkk|iletisim|iletişim|"
    r"sube|şube|atm|hesaplama|hesapla|musteri-ol|müşteri-ol|parola|site-haritasi|"
    r"site haritası|sozlesmeler|sözleşmeler|guvenlik|güvenlik|sona ermiştir|"
    r"qnb-first|qnb first|qnb-private|qnb private|bireysel|ihtiyac-kredisi|ihtiyaç kredisi|"
    r"konut|tasit|taşıt|miles|doktor|emekli|ogrenci|öğrenci|tatil|restoran|giyim|"
    r"market|akaryakit|akaryakıt|kozmetik|sinema|konser|cekilis|çekiliş|"
    r"kisisel-kredi-karti|kişisel kredi kartı)",
    re.IGNORECASE,
)
SME_COMMERCE_SIGNAL_RE = re.compile(
    r"(kobi|kobiler|ticari|işletme|isletme|esnaf|pos|üye işyeri|uye isyeri|sanal pos|"
    r"ödeme|odeme|tahsilat|kredi|kart|nakit|api|kampanya|masraf|finansman|girişimci|girisimci|"
    r"merchant|commercial|business|sme)",
    re.IGNORECASE,
)
LOW_VALUE_PR_RE = re.compile(
    r"(üst düzey atama|ust duzey atama|atama gerçekleşti|atama gerceklesti|finansal sonuç|finansal sonuc|"
    r"aktif büyüklüğü|aktif buyuklugu|anaokulu|kampüs|kampus|yetenek programı|yetenek programi|"
    r"çalışanlarına yönelik|calisanlarina yonelik|kadınlar günü|kadinlar gunu|ödül|odul|"
    r"kültür|kultur|sanat|sosyal sorumluluk|global summit|liderlerini)",
    re.IGNORECASE,
)
LOW_VALUE_RESEARCH_RE = re.compile(r"(tasarruf araştırması|tasarruf arastirmasi)", re.IGNORECASE)
PRODUCT_NAV_PATH_RE = re.compile(
    r"^/(?:(?:kobi|bireysel|ticari)/)?(?:kartlar|mevduat|krediler|dijital-bankacilik|"
    r"odemeler-ve-hizmetler|yatirim|sigorta-ve-emeklilik|hesaplama-araclari|"
    r"urun-ve-hizmet-ucretleri|sube-ve-atm)(?:/|$)",
    re.IGNORECASE,
)
DETAIL_PATH_RE = re.compile(
    r"(/content/public-website/kurumsal-iletisim/|/kurumsal-iletisim/.+|/kampanyalar/.+|"
    r"/basin|/haber|/duyuru|/press|/newsroom|/campaign)",
    re.IGNORECASE,
)
LISTING_PATH_RE = re.compile(r"(/kurumsal-iletisim/garanti-bbvadan-haberler/?$|/kampanyalar/?$)", re.IGNORECASE)
YAPI_KREDI_CAMPAIGN_DETAIL_RE = re.compile(r"/kampanyalar/detay/\d+", re.IGNORECASE)
YAPI_KREDI_PRESS_DOWNLOAD_RE = re.compile(r"/medium/file/.+/download/?$", re.IGNORECASE)
QNB_SOURCE_IDS = {"REG-061", "REG-062", "REG-063", "REG-064", "REG-065", "REG-066", "REG-067", "REG-068"}
VISA_RECENT_SOURCE_IDS = {"REG-034", "REG-070"}
ALTERNATIF_WEEKLY_SOURCE_IDS = {"REG-118"}
ING_WEEKLY_SOURCE_IDS = {"REG-083"}
BATCH_B_INSTITUTION_IDS = {
    "sekerbank",
    "fibabanka",
    "anadolubank",
    "odeabank",
    "burgan_bank",
    "hsbc",
    "enpara",
    "t_bank",
    "turkish_bank",
    "turk_ticaret_bankasi",
}
SEKERBANK_WEEKLY_SOURCE_IDS = {"REG-140"}
FIBABANKA_WEEKLY_SOURCE_IDS = {"REG-148"}
ANADOLUBANK_WEEKLY_SOURCE_IDS = {"REG-153"}
ODEABANK_WEEKLY_SOURCE_IDS = {"REG-096"}
BURGAN_WEEKLY_SOURCE_IDS = {"REG-098"}
ENPARA_WEEKLY_SOURCE_IDS = {"REG-101"}
IS_BANKASI_DUYURU_SOURCE_IDS = {"REG-006"}
BDDK_SOURCE_IDS = {"REG-052"}
HSBC_WEEKLY_SOURCE_IDS: set[str] = set()
ENPARA_QNB_ALIAS_NAMES = {"enpara", "enpara.com", "enpara bank", "enpara bank a.ş.", "qnb finansbank", "qnb bank", "qnb"}
QNB_CAMPAIGN_API_URL = "https://www.qnb.com.tr/api/Campaigns?categorySeoName=kobi-kampanyalari&isArchived=false"
QNB_CARD_DETAIL_RE = re.compile(r"/qnb-kobi-ticari-kredi-karti-kampanyalari/.+", re.IGNORECASE)
QNB_POSITIVE_RE = re.compile(
    r"(kobi|ticari|ticari kart|qnb kobi|pos|üye işyeri|uye isyeri|sanal pos|link pos|ceppos|"
    r"yazar kasa|kobi rahat|işim için|isim icin|kredi|kampanya|parapuan|taksit|aidat|"
    r"dijital kanal|e-fatura|efatura|e-arşiv|e-arsiv|e-dönüşüm|e-donusum|tahsilat|ödeme|odeme)",
    re.IGNORECASE,
)
QNB_NEGATIVE_RE = re.compile(
    r"(qnb first|qnb private|bireysel|ihtiyaç kredisi|ihtiyac kredisi|konut|taşıt|tasit|"
    r"miles|doktor|emekli|öğrenci|ogrenci|tatil|restoran|giyim|market|akaryakıt|"
    r"akaryakit|kozmetik|sinema|konser|çekiliş|cekilis|kişisel kredi kartı|kisisel kredi karti)",
    re.IGNORECASE,
)
IS_BANKASI_VALID_DETAIL_RE = re.compile(
    r"(/duyurular/.+|/kampanyalar/.+|/bankamizi-taniyin/is-bankasindan-haberler/.+|"
    r"/contentmanagement/documents/.+|/documents/.+)",
    re.IGNORECASE,
)
IS_BANKASI_ROOT_OR_NAV_RE = re.compile(
    r"^/(is-ticari|krediler|kartlar|genel-bilgi|mevduat-ve-yatirim|dijital-bankacilik|"
    r"sigorta-ve-emeklilik|odemeler-ve-para-transferi|bankamizi-taniyin|guvenlik|"
    r"urun-ve-hizmet-ucretleri|duyurular|kampanyalar)/?$",
    re.IGNORECASE,
)
IS_BANKASI_LOCAL_SIGNAL_RE = re.compile(
    r"(kobi|kobİ|ticari|işletme|isletme|esnaf|pos|ticari kart|bankamatik|tahsilat|"
    r"nakit yönetimi|nakit yonetimi|kredi|mevduat|dış ticaret|dis ticaret|ödeme|odeme|"
    r"üye işyeri|uye isyeri|merchant|commercial|kampanya|duyuru|basın|basin|haber)",
    re.IGNORECASE,
)
VISA_RELEVANT_RE = re.compile(
    r"(small business|sme|merchant|acquiring|pos|commercial|commercial card|business card|"
    r"accounts receivable|virtual card|payable|supplier|issuer|b2b|embedded|openai|"
    r"ai commerce|agentic|programmable commerce|stablecoin|token|settlement|identity|"
    r"\btap\b|digital commerce|payment|payments)",
    re.IGNORECASE,
)
VISA_NOISE_RE = re.compile(
    r"(investor|conference|common stock|exchange offer|class b|press releases listing|"
    r"see all press releases|fifa|soccer|football|fan-powered|fan powered|sudeikis|"
    r"men in blazers|olympic|paralympic)",
    re.IGNORECASE,
)
BATCH_B_STRONG_SME_RE = re.compile(
    r"(kobi|kobiler|esnaf|küçük işletme|kucuk isletme|işletme|isletme|ticari|kurumsal müşteri|"
    r"üye işyeri|uye isyeri|merchant|business card|business kredi kartı|business kredi karti|ticari kart|"
    r"pos|sanal pos|android pos|softpos|yazar kasa|ökc|okc|narpos|tahsilat|nakit yönetimi|"
    r"açık bankacılık|acik bankacilik|dbs|tedarikçi finansmanı|dış ticaret|dis ticaret|ihracat|"
    r"ticari kredi|kobi kredisi|kgf|kadın girişimci|kadin girisimci|tarım finansmanı|tarim finansmani|"
    r"ticari müşteri|ticari musteri|kurumsal bankacılık|kurumsal bankacilik|commercial banking|"
    r"working capital|trade finance|global trade|foreign exchange|international payments|"
    r"payroll|maaş|maas|sgk|vergi|commercial|sme|ihracatçı|ihracatci|ihracat finansmanı|"
    r"ihracat finansmani|reeskont|eximbank|ihracatı geliştirme|ihracati gelistirme|"
    r"teknoloji bankacılığı|teknoloji bankaciligi|servis bankacılığı|servis bankaciligi|"
    r"finansal kurumlar|ilişki bankacılığı|iliski bankaciligi)",
    re.IGNORECASE,
)
BATCH_B_CONTEXT_ONLY_RE = re.compile(
    r"(finansal okuryazarlık|yatırım alışkanlıkları|tasarruf araştırması|tüketici araştırması|"
    r"bireysel müşteri araştırması|consumer research|genel araştırma|pazar araştırması)",
    re.IGNORECASE,
)
BATCH_B_SCOPE_OUT_RE = re.compile(
    r"(sistem çalışması|sistem calismasi|bakım çalışması|bakim calismasi|kesinti|çalışma saatleri|"
    r"piyasa.*yarım gün|pay kaydileştirme|mevzuat bildirimi|login|giriş|arama|kvkk|çerez|cerez|"
    r"bireysel ihtiyaç|bireysel ihtiyac|konut kredisi|taşıt kredisi|tatil|restoran|sinema|kahve|spa|"
    r"havalimanı|çocuk etkinliği|kültür sanat|podcast|o.?blog|o.?mag|genel kurul|ttsg|"
    r"rüçhan|ruchan|esas sözleşme|bilanço ilanı|fatca|crs|zaman aşımı|sahte e-posta|"
    r"dolandırıcılık|dolandiricilik|güvenlik uyarısı|guvenlik uyarisi|tahsili gecikmiş|"
    r"spk duyurusu|yatırım sohbeti|yatirim sohbeti|vergi söyleşisi|vergi soylesisi|"
    r"tiyatro|kokteyl|yeni yıl etkinliği|yeni yil etkinligi)",
    re.IGNORECASE,
)
FINANCIAL_REPORT_RE = re.compile(r"(finansal tablo|denetim raporu|faaliyet raporu|mali tablo|çeyrek sonuç|ceyrek sonuc|finansal sonuç|finansal sonuc)", re.IGNORECASE)
FINANCIAL_RESULTS_EXPORT_EVIDENCE_RE = re.compile(
    r"(ihracatçı(?: kesim| müşteri| firma| şirket)?|ihracatci(?: kesim| musteri| firma| sirket)?|"
    r"ihracatçının finansmanı|ihracatcinin finansmani|ihracatçı odaklı|ihracatci odakli|"
    r"dış ticaret finansmanı|dis ticaret finansmani|nakdi kredi hacmi|gayri nakdi kredi|"
    r"kredilerin aktif içindeki payı|kredilerin aktif icindeki payi|finansmana erişim|finansmana erisim|"
    r"ihracatın yoğun olduğu iller|ihracatin yogun oldugu iller|ticari kredi|işletme sermayesi|"
    r"isletme sermayesi|reeskont|eximbank|ige|tim|osb|teminat|akreditif)",
    re.IGNORECASE,
)
EXPORT_FINANCE_RE = re.compile(r"(ihracat|ihracatçı|ihracatci|dış ticaret|dis ticaret|eximbank|reeskont|ige|ihracatı geliştirme|ihracati gelistirme|tim)", re.IGNORECASE)
BRANCH_OPENING_RE = re.compile(r"(şube|sube).{0,80}(hizmete açıldı|hizmete acildi|açıldı|acildi)", re.IGNORECASE)
BATCH_B_AWARD_RE = re.compile(r"(ödül|odul|ödülleri|odulleri|1incilik|birincilik|en iyi|award|qorus)", re.IGNORECASE)
DATE_RE = re.compile(
    r"(\b\d{1,2}[./]\d{1,2}[./]\d{4}\b|\b\d{4}-\d{2}-\d{2}\b|"
    r"\b\d{1,2}\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+\d{4}\b)",
    re.IGNORECASE,
)
US_SLASH_DATE_RE = re.compile(r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{4})\b")
ENGLISH_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
ENGLISH_MDY_DATE_RE = re.compile(
    r"\b(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t)?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+(?P<day>\d{1,2}),\s*(?P<year>20\d{2})\b",
    re.IGNORECASE,
)
ENGLISH_DMY_DATE_RE = re.compile(
    r"\b(?P<day>\d{1,2})\s+"
    r"(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t)?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+(?P<year>20\d{2})\b",
    re.IGNORECASE,
)
GLOBAL_PAYMENTS_SOURCE_IDS = {
    "REG-041",
    "REG-232",
    "REG-233",
    "REG-234",
    "REG-235",
    "REG-236",
    "REG-238",
    "REG-239",
    "REG-240",
    "REG-241",
    "REG-242",
    "REG-243",
    "REG-244",
}
STRIPE_NEWSROOM_SOURCE_IDS = {"REG-041"}
BLOCK_PRESS_SOURCE_IDS = {"REG-232"}
SQUARE_PRESS_SOURCE_IDS = {"REG-233"}
PAYPAL_NEWSROOM_SOURCE_IDS = {"REG-234"}
SHOPIFY_NEWSROOM_SOURCE_IDS = {"REG-235"}
AIRWALLEX_NEWSROOM_SOURCE_IDS = {"REG-236"}
CHECKOUT_NEWSROOM_SOURCE_IDS = {"REG-238"}
WISE_NEWSROOM_SOURCE_IDS = {"REG-239"}
FINEXTRA_PAYMENTS_SOURCE_IDS = {"REG-240"}
PAYMENTS_DIVE_SOURCE_IDS = {"REG-241"}
THE_PAYPERS_SOURCE_IDS = {"REG-242"}
PYMNTS_B2B_SOURCE_IDS = {"REG-243"}
BANKING_DIVE_PAYMENTS_SOURCE_IDS = {"REG-244"}
GLOBAL_PAYMENTS_DETAIL_DATE_SOURCE_IDS = (
    FINEXTRA_PAYMENTS_SOURCE_IDS
    | PAYMENTS_DIVE_SOURCE_IDS
    | PYMNTS_B2B_SOURCE_IDS
    | BANKING_DIVE_PAYMENTS_SOURCE_IDS
)
GLOBAL_PAYMENTS_EXTERNAL_NEWS_SOURCE_IDS = (
    FINEXTRA_PAYMENTS_SOURCE_IDS
    | PAYMENTS_DIVE_SOURCE_IDS
    | THE_PAYPERS_SOURCE_IDS
    | PYMNTS_B2B_SOURCE_IDS
    | BANKING_DIVE_PAYMENTS_SOURCE_IDS
)
GLOBAL_PAYMENT_RELEVANCE_RE = re.compile(
    r"(small business|sme|merchant|seller|business ownership|businesses|commercial|commerce|"
    r"payments?|checkout|pos|point of sale|acquiring|card|stablecoin|agentic|ai agent|"
    r"openai|chatgpt|claude|embedded finance|banking|cash flow|working capital|treasury|"
    r"accounts payable|accounts receivable|reconciliation|global payments?|cross-border|"
    r"digital commerce|retail operation|commerce platform|b2b|smb|middle market|"
    r"virtual card|commercial card|supplier payments?|procurement|invoice|billing|"
    r"disbursements?|payment infrastructure|acceptance|freight payments?|swift|wero|fednow|rtp)",
    re.IGNORECASE,
)
GLOBAL_PAYMENT_NOISE_RE = re.compile(
    r"(investor day|quarter results|annual letter|tender offer|board of directors|chief revenue officer|"
    r"chief financial officer|appointment|appointed|conference|stock|football|soccer|seahawks|arsenal|"
    r"jersey|sponsorship|climate|child safety|teen advisory|ipo|valuation|funding round|"
    r"podcasts?|consumer fraud|chip-enabled ebt|personal wallet|personal account|"
    r"raises? \$|raises? usd|series [abc]|funding|digital bank service|discontinue)",
    re.IGNORECASE,
)
GLOBAL_PAYMENT_EXTERNAL_STRONG_RE = re.compile(
    r"(small business|sme|smb|merchant|seller|commercial|b2b|middle market|treasury|"
    r"cash flow|working capital|accounts payable|accounts receivable|reconciliation|"
    r"cross-border|global payments?|stablecoin|embedded|api|open banking|payment infrastructure|"
    r"virtual card|commercial card|supplier payments?|procurement|invoice|billing|"
    r"acceptance|acquiring|pos|freight payments?|swift|wero|fednow|rtp)",
    re.IGNORECASE,
)
BAD_TITLE_RE = re.compile(
    r"(tekil gelişme kontrol|fallback|source page|communication / press releases için)",
    re.IGNORECASE,
)
GENERIC_LINK_TITLE_RE = re.compile(
    r"^(detaylı bilgi|detayli bilgi|bülteni indir|bulteni indir|indir|download|pdf|oku|devamı|devami)$",
    re.IGNORECASE,
)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def ssl_fallback_allowed(url: str) -> bool:
    return urlparse(url).netloc.casefold() in SSL_VERIFY_FALLBACK_HOSTS


def get_with_source_ssl_fallback(url: str, timeout: int) -> requests.Response:
    try:
        return requests.get(url, timeout=timeout, headers=HEADERS)
    except requests.exceptions.SSLError:
        if not ssl_fallback_allowed(url):
            raise
        logging.warning("SSL verification failed for detail URL; retrying with source-specific fallback: %s", url)
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        return requests.get(url, timeout=timeout, headers=HEADERS, verify=False)
TRACKING_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "yclid",
    "mc_cid",
    "mc_eid",
}
TITLE_SUFFIX_RE = re.compile(
    r"\s*\|\s*(Türkiye İş Bankası(?: A\.Ş\.)?|İş Bankası(?: A\.Ş\.)?|Garanti BBVA|Yapı Kredi|QNB Finansbank|Enpara Şirketim|Enpara|HSBC|Burgan Bank|T-Bank|TurkishBank|Türk Ticaret Bankası)\s*$",
    re.IGNORECASE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@dataclass(frozen=True)
class CandidateLink:
    title: str
    url: str
    score: int
    reason: str
    raw_date_text: str = ""
    date_source_hint: str = ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("RUN-%Y%m%d%H%M%S")


def read_recent_items() -> pd.DataFrame:
    if RECENT_ITEMS_PATH.exists():
        df = pd.read_csv(RECENT_ITEMS_PATH, encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=RECENT_ITEM_COLUMNS)
    for column in RECENT_ITEM_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df.reindex(columns=RECENT_ITEM_COLUMNS)


def read_audit() -> pd.DataFrame:
    if AUDIT_PATH.exists():
        df = pd.read_csv(AUDIT_PATH, encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=AUDIT_COLUMNS)
    for column in AUDIT_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df.reindex(columns=AUDIT_COLUMNS)


def stable_hash(*parts: str) -> str:
    text = "\n".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audit_id_for(run_id_value: str, source_id: str, candidate_url: str) -> str:
    digest = hashlib.sha1(f"{run_id_value}:{source_id}:{candidate_url}".encode("utf-8")).hexdigest()[:12]
    return f"RIAUD-{digest}"


def recent_item_id_for(content_fingerprint: str) -> str:
    digest = hashlib.sha1(str(content_fingerprint).encode("utf-8")).hexdigest()[:12]
    return f"RI-{digest}"


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonicalize_url(url: str, base_url: str = "") -> str:
    absolute = urljoin(str(base_url or ""), str(url or "").strip())
    parsed = urlparse(absolute)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def normalize_title_for_dedupe(title: str) -> str:
    value = TITLE_SUFFIX_RE.sub("", str(title or ""))
    value = value.casefold()
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s+[-–]\s+", " - ", value)
    return value


def content_fingerprint_for(institution_name: str, canonical_item_url: str, normalized_title: str, normalized_item_date: str) -> str:
    institution_key = alias_dedupe_key(institution_name)
    if canonical_item_url:
        raw = f"{institution_key}|{canonical_item_url}|{normalized_title}"
    else:
        raw = f"{institution_key}|{normalized_title}|{normalized_item_date}"
    return stable_hash(raw)


def alias_dedupe_key(institution_name: str) -> str:
    normalized = normalize_text(institution_name).casefold()
    if normalized in ENPARA_QNB_ALIAS_NAMES:
        return "enpara_qnb_alias_group"
    return normalized


def duplicate_index(existing: pd.DataFrame) -> dict[str, object]:
    for column in ["canonical_item_url", "normalized_title", "content_fingerprint", "recency_basis_date", "normalized_item_date", "institution_name", "recent_item_id"]:
        if column not in existing.columns:
            existing[column] = ""
    return {
        "by_institution_url": {
            (alias_dedupe_key(str(row.get("institution_name", ""))), str(row.get("canonical_item_url", ""))): str(row.get("recent_item_id", ""))
            for _, row in existing.iterrows()
            if str(row.get("canonical_item_url", "")).strip()
        },
        "by_fingerprint": {
            str(row.get("content_fingerprint", "")): str(row.get("recent_item_id", ""))
            for _, row in existing.iterrows()
            if str(row.get("content_fingerprint", "")).strip()
        },
        "rows": existing.copy(),
    }


def find_duplicate(
    index: dict[str, object],
    institution_name: str,
    canonical_item_url: str,
    content_fingerprint: str,
    normalized_title: str,
    recency_basis_date: str,
) -> tuple[bool, str, str]:
    institution_key = alias_dedupe_key(institution_name)
    if canonical_item_url:
        duplicate_id = index["by_institution_url"].get((institution_key, canonical_item_url))  # type: ignore[index]
        if duplicate_id:
            return True, "duplicate_canonical_item_url", str(duplicate_id)
    if content_fingerprint:
        duplicate_id = index["by_fingerprint"].get(content_fingerprint)  # type: ignore[index]
        if duplicate_id:
            return True, "duplicate_content_fingerprint", str(duplicate_id)

    candidate_date = pd.to_datetime(recency_basis_date, errors="coerce")
    rows = index["rows"]  # type: ignore[assignment]
    if not isinstance(rows, pd.DataFrame) or rows.empty or not normalized_title:
        return False, "", ""
    same_inst = rows[rows["institution_name"].astype(str).apply(alias_dedupe_key).eq(institution_key)].copy()
    for _, row in same_inst.iterrows():
        existing_title = str(row.get("normalized_title", "") or "")
        if not existing_title:
            continue
        existing_date = pd.to_datetime(row.get("recency_basis_date", "") or row.get("normalized_item_date", ""), errors="coerce")
        if pd.notna(candidate_date) and pd.notna(existing_date) and abs((candidate_date - existing_date).days) > 60:
            continue
        similarity = SequenceMatcher(None, normalized_title, existing_title).ratio()
        if similarity >= 0.92:
            return True, "duplicate_similar_title_60d", str(row.get("recent_item_id", ""))
    return False, "", ""


def add_to_duplicate_index(index: dict[str, object], row: dict[str, str]) -> None:
    institution_key = alias_dedupe_key(str(row.get("institution_name", "")))
    canonical = str(row.get("canonical_item_url", "") or "")
    fingerprint = str(row.get("content_fingerprint", "") or "")
    item_id = str(row.get("recent_item_id", "") or "")
    if canonical:
        index["by_institution_url"][(institution_key, canonical)] = item_id  # type: ignore[index]
    if fingerprint:
        index["by_fingerprint"][fingerprint] = item_id  # type: ignore[index]
    rows = index["rows"]  # type: ignore[assignment]
    if isinstance(rows, pd.DataFrame):
        index["rows"] = pd.concat([rows, pd.DataFrame([row])], ignore_index=True)


def is_negative_link(title: str, url: str) -> bool:
    parsed = urlparse(url)
    if LISTING_PATH_RE.search(parsed.path) or "/content/public-website/kurumsal-iletisim/" in parsed.path:
        return False
    blob = f"{title} {parsed.netloc} {parsed.path} {parsed.fragment}".casefold()
    if NEGATIVE_RE.search(blob):
        return True
    if PRODUCT_NAV_PATH_RE.search(parsed.path):
        return True
    return False


def is_same_or_subdomain(base_url: str, url: str) -> bool:
    base_netloc = urlparse(base_url).netloc.casefold().removeprefix("www.")
    target_netloc = urlparse(url).netloc.casefold().removeprefix("www.")
    if not base_netloc or not target_netloc:
        return True
    return target_netloc == base_netloc or target_netloc.endswith(f".{base_netloc}")


def title_from_slug(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").strip().title()


def title_from_url_filename(url: str) -> str:
    filename = unquote(urlparse(url).path.rstrip("/").split("/")[-1])
    filename = re.sub(r"\.(pdf|html?|aspx?)$", "", filename, flags=re.IGNORECASE)
    filename = re.sub(r"[_-]+", " ", filename)
    filename = re.sub(r"\bBB\b", "", filename)
    filename = normalize_text(filename)
    if len(filename) < 20:
        return title_from_slug(url)
    return filename[:1].upper() + filename[1:]


def is_generic_link_title(title: str) -> bool:
    return bool(GENERIC_LINK_TITLE_RE.match(normalize_text(title)))


def best_link_title(raw_title: str, url: str) -> str:
    title = normalize_text(raw_title)
    if not title or is_generic_link_title(title):
        parsed = urlparse(url)
        if parsed.path.casefold().endswith(".pdf"):
            return title_from_url_filename(url)
        if DETAIL_PATH_RE.search(parsed.path):
            return title_from_slug(url)
    return title


def passes_explicit_sme_relevance_gate(
    institution: str,
    url_path: str,
    title: str,
    main_body_text: str,
    source_section: str = "",
    card_product_type: str = "",
) -> tuple[bool, str]:
    local_blob = normalize_text(
        " ".join(
            [
                str(institution or ""),
                str(url_path or "").replace("-", " "),
                str(title or ""),
                str(source_section or ""),
                str(card_product_type or ""),
                str(main_body_text or "")[:2500],
            ]
        )
    )
    if BATCH_B_STRONG_SME_RE.search(local_blob):
        evidence = BATCH_B_STRONG_SME_RE.search(local_blob)
        return True, f"explicit_sme_signal:{evidence.group(0) if evidence else ''}"
    return False, "no_explicit_sme_signal_in_local_title_path_or_body"


def has_financial_results_export_evidence(text: str) -> bool:
    return bool(FINANCIAL_RESULTS_EXPORT_EVIDENCE_RE.search(normalize_text(text)))


def classify_content_role_for_candidate(row: pd.Series, title: str, item_url: str, item_text: str) -> tuple[str, str]:
    institution_id = str(row.get("institution_id", "") or "").casefold()
    if institution_id not in BATCH_B_INSTITUTION_IDS:
        return "Bağımsız Gelişme", "legacy_institution_default"

    parsed = urlparse(item_url)
    local_blob = normalize_text(f"{title} {parsed.path.replace('-', ' ')} {item_text[:2500]}")
    if institution_id in {"t_bank", "turkish_bank", "turk_ticaret_bankasi"}:
        if BATCH_B_SCOPE_OUT_RE.search(local_blob) and not (
            institution_id == "turk_ticaret_bankasi" and EXPORT_FINANCE_RE.search(local_blob) and BRANCH_OPENING_RE.search(local_blob)
        ):
            return "Kapsam Dışı", "legal_event_or_operational_noise"
        if institution_id == "turkish_bank" and re.search(r"(turkishbank group|group|grup)", local_blob, re.IGNORECASE):
            if not re.search(r"(turkish bank a\.ş|turkishbank a\.ş|türkiye|turkiye|yerel|ticari|kurumsal|teknoloji bankacılığı|teknoloji bankaciligi)", local_blob, re.IGNORECASE):
                return "Kapsam Dışı", "group_level_without_turkiye_or_bank_entity_evidence"
        if FINANCIAL_REPORT_RE.search(local_blob):
            if institution_id == "turk_ticaret_bankasi" and has_financial_results_export_evidence(local_blob):
                return "Yönetici Bilgilendirme", "financial_results_with_export_finance_evidence"
            return "Bağlamsal Veri", "financial_report_without_segment_evidence"
        if institution_id == "turk_ticaret_bankasi" and EXPORT_FINANCE_RE.search(local_blob):
            if BRANCH_OPENING_RE.search(local_blob):
                return "Bağımsız Gelişme", "exporter_branch_channel_expansion"
            return "Bağımsız Gelişme", "export_finance_commercial_evidence"
    if institution_id == "hsbc" and not re.search(r"(türkiye|turkiye|hsbc türkiye|hsbc turkiye|turkish|local|yerel)", local_blob, re.IGNORECASE):
        if re.search(r"(insights|global|menat|qatar|germany|holding|research|survey)", local_blob, re.IGNORECASE):
            return "Kapsam Dışı", "hsbc_global_content_without_turkiye_evidence"
    has_sme, sme_reason = passes_explicit_sme_relevance_gate(
        str(row.get("institution_name", "")),
        parsed.path,
        title,
        item_text,
        str(row.get("source_name", "")),
        str(row.get("source_type", "")),
    )
    if BATCH_B_SCOPE_OUT_RE.search(local_blob) and not has_sme:
        return "Kapsam Dışı", "operational_or_retail_noise_without_sme_signal"
    if BATCH_B_CONTEXT_ONLY_RE.search(local_blob) and not has_sme:
        return "Bağlamsal Veri", "consumer_or_general_research_context_only"
    if str(row.get("extraction_mode", "")).casefold() == "benchmark_fact":
        return "Benchmark Bilgisi", "benchmark_fact_source"
    if institution_id == "enpara" and str(row.get("extraction_mode", "")).casefold() == "benchmark_fact":
        return "Benchmark Bilgisi", "benchmark_fact_source"
    if BATCH_B_AWARD_RE.search(local_blob):
        if has_sme:
            return "Yönetici Bilgilendirme", f"product_or_commercial_award:{sme_reason}"
        return "Kapsam Dışı", "generic_award_without_commercial_relevance"
    if not has_sme:
        return "Kapsam Dışı", sme_reason
    return "Bağımsız Gelişme", sme_reason


def score_link(title: str, url: str) -> tuple[int, str]:
    parsed = urlparse(url)
    path = parsed.path
    blob = f"{title} {path}"
    score = 0
    reasons = []

    if (LOW_VALUE_PR_RE.search(blob) or LOW_VALUE_RESEARCH_RE.search(blob)) and not SME_COMMERCE_SIGNAL_RE.search(blob):
        return 0, "low_value_pr_noise"

    is_garanti_press_detail = "/content/public-website/kurumsal-iletisim/" in path
    is_listing = bool(LISTING_PATH_RE.search(path))

    if PRODUCT_NAV_PATH_RE.search(path) and not is_listing and not is_garanti_press_detail:
        return 0, "product_nav"

    if 20 <= len(title) <= 180:
        score += 2
        reasons.append("title_length")
    if POSITIVE_RE.search(blob):
        score += 2
        reasons.append("positive_keyword")
    if DETAIL_PATH_RE.search(path):
        score += 4
        reasons.append("detail_path")
    if is_listing:
        score += 10
        reasons.append("listing_path")
    if is_garanti_press_detail:
        score += 12
        reasons.append("garanti_press_detail")
    if title.lower() in {"detaylı bilgi", "detayli bilgi"} and DETAIL_PATH_RE.search(path):
        score += 1
        reasons.append("generic_detail_link")

    if reasons == ["title_length"]:
        return 0, "title_only"

    return score, ",".join(reasons)


def extract_candidate_links_from_html(raw_html_path: str | Path, base_url: str, source_id: str = "") -> tuple[list[CandidateLink], int]:
    path = ROOT_DIR / raw_html_path if not Path(raw_html_path).is_absolute() else Path(raw_html_path)
    if not path.exists():
        return [], 0
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    source_specific, total_links = extract_source_specific_candidates_from_soup(soup, base_url, source_id)
    if source_specific:
        return source_specific, total_links
    candidates, total_links = extract_candidate_links_from_soup(soup, base_url)
    if source_id in {"REG-011", "REG-012"}:
        candidates = [
            candidate
            for candidate in candidates
            if YAPI_KREDI_CAMPAIGN_DETAIL_RE.search(urlparse(candidate.url).path)
            or YAPI_KREDI_PRESS_DOWNLOAD_RE.search(urlparse(candidate.url).path)
        ]
    return candidates, total_links


def extract_source_specific_candidates_from_soup(soup: BeautifulSoup, base_url: str, source_id: str) -> tuple[list[CandidateLink], int]:
    total_links = len(soup.find_all("a"))
    parsed_base = urlparse(base_url)
    path = parsed_base.path.casefold()
    host = parsed_base.netloc.casefold()
    if "tbank.com.tr" in host and ("/haberler/" in path or "/duyurular/" in path):
        return extract_t_bank_links(soup, base_url), total_links
    if "turkishbank.com" in host and "/hakkimizda/bizden-haberler" in path:
        return extract_turkishbank_links(soup, base_url), total_links
    if "turkticaretbankasi.com.tr" in host and path.startswith("/icerikler/"):
        return extract_turk_ticaret_bankasi_links(soup, base_url), total_links
    if source_id in VISA_RECENT_SOURCE_IDS:
        return extract_visa_candidates(soup, base_url), total_links
    if source_id in SEKERBANK_WEEKLY_SOURCE_IDS:
        return extract_sekerbank_links(soup, base_url), total_links
    if source_id in FIBABANKA_WEEKLY_SOURCE_IDS:
        return extract_fibabanka_campaign_links(soup, base_url), total_links
    if source_id in ANADOLUBANK_WEEKLY_SOURCE_IDS:
        return extract_anadolubank_press_links(soup, base_url), total_links
    if source_id in ODEABANK_WEEKLY_SOURCE_IDS:
        return extract_odeabank_press_links(soup, base_url), total_links
    if source_id in ALTERNATIF_WEEKLY_SOURCE_IDS:
        return extract_alternatif_bank_links(soup, base_url), total_links
    if source_id in ING_WEEKLY_SOURCE_IDS:
        return extract_ing_links(soup, base_url), total_links
    if source_id in BURGAN_WEEKLY_SOURCE_IDS:
        return extract_burgan_bank_links(soup, base_url), total_links
    if source_id in ENPARA_WEEKLY_SOURCE_IDS:
        return extract_enpara_links(soup, base_url), total_links
    if source_id in IS_BANKASI_DUYURU_SOURCE_IDS:
        return extract_is_bankasi_duyuru_links(soup, base_url), total_links
    if source_id in BDDK_SOURCE_IDS:
        return extract_bddk_duyuru_links(soup, base_url), total_links
    if source_id in GLOBAL_PAYMENTS_SOURCE_IDS:
        return extract_global_payments_links(soup, base_url, source_id), total_links
    if source_id == "REG-011":
        scope = soup.select_one("main") or soup.select_one(".content") or soup
        return extract_yapi_kredi_campaign_candidates(scope, base_url), total_links
    if source_id == "REG-012":
        scope = soup.select_one("#pressReleaseResultContent")
        if scope:
            return extract_yapi_kredi_press_candidates(scope, base_url), total_links
    if source_id in QNB_SOURCE_IDS:
        return extract_qnb_candidates(soup, base_url, source_id), total_links
    return [], total_links


def english_date_to_iso(text: str) -> str:
    value = normalize_text(text)
    for regex in [ENGLISH_MDY_DATE_RE, ENGLISH_DMY_DATE_RE]:
        match = regex.search(value)
        if not match:
            continue
        month = ENGLISH_MONTHS.get(match.group("month").casefold())
        if not month:
            continue
        try:
            return datetime(int(match.group("year")), month, int(match.group("day"))).date().isoformat()
        except ValueError:
            return ""
    match = re.search(r"\b(?P<year>20\d{2})-(?P<month>\d{2})-(?P<day>\d{2})\b", value)
    if match:
        try:
            return datetime(int(match.group("year")), int(match.group("month")), int(match.group("day"))).date().isoformat()
        except ValueError:
            return ""
    return ""


def strip_global_date_and_cta(text: str) -> str:
    cleaned = normalize_text(text)
    cleaned = ENGLISH_MDY_DATE_RE.sub("", cleaned)
    cleaned = ENGLISH_DMY_DATE_RE.sub("", cleaned)
    cleaned = re.sub(r"\b20\d{2}-\d{2}-\d{2}\b", "", cleaned)
    cleaned = re.sub(r"\s*/\s*\d+\s*min\s*read\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*/\s*(news|fintech|payments?|b2b payments?|expert views)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:read article|read more|learn more)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(product|corporate|company|pov|insights|press releases?)\s+", "", cleaned, flags=re.IGNORECASE)
    return normalize_text(cleaned.strip(" -–|"))


def date_from_global_url(url: str) -> str:
    path = urlparse(url).path
    match = re.search(r"/(?P<year>20\d{2})-(?P<month>\d{2})-(?P<day>\d{2})-", path)
    if match:
        return f"{match.group('year')}-{match.group('month')}-{match.group('day')}"
    return ""


def should_keep_global_payment_candidate(source_id: str, title: str, context: str, url: str) -> bool:
    blob = normalize_text(f"{title} {context} {urlparse(url).path.replace('-', ' ')}")
    title_blob = normalize_text(title)
    if not GLOBAL_PAYMENT_RELEVANCE_RE.search(blob):
        return False
    if source_id in GLOBAL_PAYMENTS_EXTERNAL_NEWS_SOURCE_IDS and not GLOBAL_PAYMENT_EXTERNAL_STRONG_RE.search(blob):
        return False
    if source_id in GLOBAL_PAYMENTS_EXTERNAL_NEWS_SOURCE_IDS and re.search(
        r"(raises? \$|raises? usd|series [abc]|funding)",
        title_blob,
        re.IGNORECASE,
    ) and not re.search(
        r"(payments?|cross-border|stablecoin|treasury|merchant|sme|smb|commercial|working capital)",
        title_blob,
        re.IGNORECASE,
    ):
        return False
    if source_id in WISE_NEWSROOM_SOURCE_IDS:
        if re.search(r"(nasdaq|listing|stock|investor|consumer help|personal account)", blob, re.IGNORECASE):
            return False
        return bool(
            re.search(
                r"(wise platform|partner|partnership|bank|payments canada|payment infrastructure|"
                r"international payments?|business|businesses|api|embedded|cross-border)",
                blob,
                re.IGNORECASE,
            )
        )
    if source_id in PAYPAL_NEWSROOM_SOURCE_IDS and "european payments council" in blob.casefold():
        return True
    if GLOBAL_PAYMENT_NOISE_RE.search(blob) and not re.search(
        r"(seller|merchant|small business|sme|payment|checkout|commerce|stablecoin|agentic|pos|working capital|treasury)",
        blob,
        re.IGNORECASE,
    ):
        return False
    if re.search(r"(consumer|wallet|retail payments?)", blob, re.IGNORECASE) and not re.search(
        r"(merchant|business|commercial|b2b|sme|smb|supplier|treasury|acceptance|acquiring|pos|ecommerce|online payments?)",
        blob,
        re.IGNORECASE,
    ):
        return False
    return True


def extract_global_payments_links(soup: BeautifulSoup, base_url: str, source_id: str) -> list[CandidateLink]:
    path_rules = {
        "REG-041": re.compile(r"/newsroom/news/[^/]+/?$", re.IGNORECASE),
        "REG-232": re.compile(r"/inside/[^/]+/?$", re.IGNORECASE),
        "REG-233": re.compile(r"/us/en/press/[^/]+/?$", re.IGNORECASE),
        "REG-234": re.compile(r"/20\d{2}-[^/]+/?$", re.IGNORECASE),
        "REG-235": re.compile(r"/news/[^/]+/?$", re.IGNORECASE),
        "REG-236": re.compile(r"/global/newsroom/[^/]+/?$", re.IGNORECASE),
        "REG-238": re.compile(r"/newsroom/[^/]+/?$", re.IGNORECASE),
        "REG-239": re.compile(r"/en-[^/]+/\d+-[^/]+/?$", re.IGNORECASE),
        "REG-240": re.compile(r"/newsarticle/\d+/[^/]+/?$", re.IGNORECASE),
        "REG-241": re.compile(r"/news/[^/]+/\d+/?$", re.IGNORECASE),
        "REG-242": re.compile(r"/[^/]+/news/[^/]+/?$", re.IGNORECASE),
        "REG-243": re.compile(r"/news/b2b-payments/20\d{2}/[^/]+/?$", re.IGNORECASE),
        "REG-244": re.compile(r"/news/[^/]+/\d+/?$", re.IGNORECASE),
    }
    path_rule = path_rules.get(source_id)
    if not path_rule:
        return []

    by_url: dict[str, dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        href = normalize_text(anchor.get("href", ""))
        url = canonicalize_url(href, base_url)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not is_same_or_subdomain(base_url, url):
            continue
        if not path_rule.search(parsed.path):
            continue

        heading = anchor.find(["h1", "h2", "h3", "h4"])
        title_attr = normalize_text(anchor.get("title", ""))
        anchor_text = normalize_text(heading.get_text(" ", strip=True)) if heading else title_attr or normalize_text(anchor.get_text(" ", strip=True))
        parent_text = normalize_text(anchor.parent.get_text(" ", strip=True)) if anchor.parent else anchor_text
        context = normalize_text(f"{anchor_text} {parent_text} {parsed.path.replace('-', ' ')}")
        raw_date = english_date_to_iso(context) or date_from_global_url(url)
        title = strip_global_date_and_cta(anchor_text)
        if not title or title.casefold() in {"product", "corporate", "company", "pov", "insights", "press releases"}:
            title = strip_global_date_and_cta(parent_text)
        if len(title) > 180:
            title = normalize_text(title[:177]).rstrip(" ,.;:") + "..."

        score = 30
        if re.search(r"(small business|sme|merchant|seller|pos|checkout|commercial|working capital|treasury)", context, re.IGNORECASE):
            score += 8
        if re.search(r"(stablecoin|agentic|openai|chatgpt|claude|embedded|api|reconciliation)", context, re.IGNORECASE):
            score += 5
        current = by_url.setdefault(url, {"title": "", "raw_date": "", "score": "0", "context": ""})
        if title and len(title) >= 12 and (
            not current["title"] or score > int(current["score"]) or len(title) > len(current["title"])
        ):
            current["title"] = title
            current["score"] = str(score)
        if raw_date and not current["raw_date"]:
            current["raw_date"] = raw_date
        current["context"] = normalize_text(f"{current['context']} {context}")[:1400]

    candidates = [
        CandidateLink(
            title=value["title"],
            url=url,
            score=int(value["score"]),
            reason="global_payments_news_card",
            raw_date_text=value["raw_date"],
            date_source_hint="listing_page_nearby_date",
        )
        for url, value in by_url.items()
        if value["title"]
        and (value["raw_date"] or source_id in GLOBAL_PAYMENTS_DETAIL_DATE_SOURCE_IDS)
        and should_keep_global_payment_candidate(source_id, value["title"], value["context"], url)
    ]
    candidates = sorted(candidates, key=lambda item: (item.raw_date_text, item.score), reverse=True)
    if source_id in CHECKOUT_NEWSROOM_SOURCE_IDS:
        return candidates[:25]
    if source_id in GLOBAL_PAYMENTS_EXTERNAL_NEWS_SOURCE_IDS:
        return candidates[:20]
    return candidates


def extract_bddk_duyuru_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    candidates: dict[str, CandidateLink] = {}
    for anchor in soup.find_all("a", href=True):
        url = urljoin(base_url, normalize_text(anchor.get("href", "")))
        parsed = urlparse(url)
        if not is_same_or_subdomain(base_url, url):
            continue
        if not re.search(r"/Duyuru/Detay/\d+$", parsed.path, re.IGNORECASE):
            continue
        text = normalize_text(anchor.get_text(" ", strip=True))
        date_match = re.match(r"^(\d{1,2}\.\d{1,2}\.\d{4})\s+(.+)$", text)
        raw_date = date_match.group(1) if date_match else ""
        title = date_match.group(2).strip() if date_match else text
        if not raw_date or len(title) < 12:
            continue
        candidates[url] = CandidateLink(
            title=title,
            url=url,
            score=28,
            reason="bddk_duyuru_detail",
            raw_date_text=raw_date,
            date_source_hint="listing_page_nearby_date",
        )
    return sorted(candidates.values(), key=lambda item: item.score, reverse=True)


def extract_is_bankasi_duyuru_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    candidates: dict[str, CandidateLink] = {}
    for anchor in soup.find_all("a", href=True):
        href = normalize_text(anchor.get("href", ""))
        url = urljoin(base_url, href)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not is_same_or_subdomain(base_url, url):
            continue
        path = parsed.path
        title = best_link_title(anchor.get_text(" ", strip=True), url)
        parent_text = normalize_text(anchor.parent.get_text(" ", strip=True)) if anchor.parent else title
        blob = f"{title} {parent_text} {path.replace('-', ' ')}"
        if IS_BANKASI_ROOT_OR_NAV_RE.search(path):
            continue
        if not IS_BANKASI_VALID_DETAIL_RE.search(path):
            continue
        if not IS_BANKASI_LOCAL_SIGNAL_RE.search(blob):
            continue
        if is_negative_link(title, url) and not IS_BANKASI_LOCAL_SIGNAL_RE.search(title):
            continue
        raw_date = DATE_RE.search(blob)
        if not raw_date and parsed.path.casefold().endswith(".pdf") and not IS_BANKASI_LOCAL_SIGNAL_RE.search(title):
            continue
        score = 18
        if raw_date:
            score += 8
        if SME_COMMERCE_SIGNAL_RE.search(blob):
            score += 8
        if parsed.path.casefold().endswith(".pdf"):
            score += 2
        if not title or len(title) < 12:
            title = title_from_url_filename(url) if parsed.path.casefold().endswith(".pdf") else title_from_slug(url)
        if not title or len(title) < 12:
            continue
        candidates[url] = CandidateLink(
            title=title_without_date_suffix(title),
            url=url,
            score=score,
            reason="is_bankasi_duyuru_detail",
            raw_date_text=raw_date.group(0) if raw_date else "",
            date_source_hint="listing_page_nearby_date" if raw_date else "",
        )
    return sorted(candidates.values(), key=lambda item: item.score, reverse=True)


def extract_burgan_bank_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    positive = re.compile(
        r"(kobi|ticari|kurumsal|faktoring|ebrd|sendikasyon|finansman|nakit|dış ticaret|dis ticaret|"
        r"ihracat|ithalat|proje finansmanı|teminat|akreditif|ticari müşteri|ticari musteri)",
        re.IGNORECASE,
    )
    negative = re.compile(
        r"(on dijital|on plus|alışveriş|alisveris|vatan|biletinial|kripto|tatil|restoran|sinema|"
        r"istanbul modern|pati|great place|çalışan|calisan|employer|sponsor|yatırım fonu|eurobond)",
        re.IGNORECASE,
    )
    candidates: list[CandidateLink] = []
    for anchor in soup.find_all("a", href=True):
        href = normalize_text(anchor.get("href", ""))
        url = urljoin(base_url, href)
        parsed = urlparse(url)
        if not parsed.path.casefold().endswith(".pdf"):
            continue
        text = normalize_text(anchor.get_text(" ", strip=True))
        parent_text = normalize_text(anchor.parent.get_text(" ", strip=True)) if anchor.parent else text
        title = title_without_date_suffix(text or title_from_url_filename(url))
        blob = f"{title} {parent_text} {parsed.path.replace('-', ' ')}"
        date_match = DATE_RE.search(blob)
        if not positive.search(blob):
            continue
        if negative.search(blob) and not positive.search(title):
            continue
        raw_date = date_match.group(0) if date_match else ""
        candidates.append(
            CandidateLink(
                title=title,
                url=url,
                score=30 if raw_date else 22,
                reason="burgan_press_pdf",
                raw_date_text=raw_date,
                date_source_hint="listing_page_nearby_date" if raw_date else "",
            )
        )
    return sorted({item.url: item for item in candidates}.values(), key=lambda item: item.score, reverse=True)


def extract_enpara_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    positive = re.compile(
        r"(sirketim|şirketim|işletme|isletme|şirket|sirket|ticari|pos|sgk|maaş|maas|"
        r"ödeme|odeme|kredi kartı|kredi karti|günlük hesap|gunluk hesap|tavsiye|ücret|ucret|komisyon)",
        re.IGNORECASE,
    )
    candidates: list[CandidateLink] = []
    for anchor in soup.find_all("a", href=True):
        url = urljoin(base_url, normalize_text(anchor.get("href", "")))
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if "/sirketim/kampanyalar/" not in path:
            continue
        if path.endswith("/sirketim/kampanyalar"):
            continue
        title = normalize_text(anchor.get_text(" ", strip=True))
        parent_text = normalize_text(anchor.parent.get_text(" ", strip=True)) if anchor.parent else ""
        if not title:
            title = title_from_slug(url)
        blob = f"{title} {parent_text} {path.replace('-', ' ')}"
        if not positive.search(blob):
            continue
        candidates.append(
            CandidateLink(
                title=title,
                url=url,
                score=26,
                reason="enpara_sirketim_campaign_link",
            )
        )
    return sorted({item.url: item for item in candidates}.values(), key=lambda item: item.score, reverse=True)


def first_asset_date_from_node(node: BeautifulSoup) -> tuple[str, str]:
    blob_parts = []
    for img in node.find_all("img"):
        blob_parts.append(normalize_text(img.get("src", "")))
    blob = " ".join(blob_parts)
    day_match = re.search(r"([0-3]\d)([01]\d)(2[0-9])", blob)
    if day_match:
        day, month, year = day_match.groups()
        return f"{day}.{month}.20{year}", "listing_asset_date"
    month_match = re.search(r"/(20\d{2})/([01]\d)/", blob)
    if month_match:
        year, month = month_match.groups()
        return f"01.{month}.{year}", "listing_asset_month"
    return "", ""


def extract_t_bank_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    positive = re.compile(
        r"(tüzel|tuzel|ticari|kurumsal|kobi|nakit|kredi|döviz pozisyon|doviz pozisyon|"
        r"şube|sube|sendikasyon|finansman|nakit yönetimi|dış ticaret|dis ticaret)",
        re.IGNORECASE,
    )
    candidates: dict[str, CandidateLink] = {}
    for anchor in soup.find_all("a", href=True):
        url = urljoin(base_url, normalize_text(anchor.get("href", "")))
        path = urlparse(url).path
        if "/haberler/detay/" not in path and "/hakkimizda/duyuru-detay/" not in path:
            continue
        parent_text = normalize_text(anchor.parent.get_text(" ", strip=True)) if anchor.parent else ""
        title = re.sub(r"\bDevamı\b", "", parent_text, flags=re.IGNORECASE).strip() or title_from_slug(url)
        blob = f"{title} {path.replace('-', ' ')}"
        if not positive.search(blob) and not DATE_RE.search(blob):
            continue
        raw_date = detect_date(title, path.replace("-", " "))
        candidate = CandidateLink(
            title=title_without_date_suffix(title),
            url=url,
            score=24 if raw_date else 16,
            reason="tbank_local_news_link",
            raw_date_text=raw_date,
            date_source_hint="listing_page_nearby_date" if raw_date else "",
        )
        candidates[url] = candidate
    return sorted(candidates.values(), key=lambda item: item.score, reverse=True)


def extract_turkishbank_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    positive = re.compile(
        r"(ticari|kurumsal|teknoloji bankacılığı|teknoloji bankaciligi|t-gate|api|"
        r"açık bankacılık|acik bankacilik|finansal kurumlar|ödeme|odeme|tahsilat|"
        r"rapor|faaliyet|finansal tablo|turkishbank)",
        re.IGNORECASE,
    )
    negative = re.compile(r"(tiyatro|kokteyl|yeni yıl|vergi söyleşisi|ekonomi sohbetleri|açık yatırım|acik yatirim)", re.IGNORECASE)
    candidates: dict[str, CandidateLink] = {}
    for anchor in soup.find_all("a", href=True):
        url = urljoin(base_url, normalize_text(anchor.get("href", "")))
        path = urlparse(url).path
        if "/hakkimizda/bizden-haberler/" not in path or path.rstrip("/") == "/hakkimizda/bizden-haberler":
            continue
        title = normalize_text(anchor.get_text(" ", strip=True)) or title_from_slug(url)
        blob = f"{title} {path.replace('-', ' ')}"
        if negative.search(blob) and not re.search(r"(ticari|kurumsal|teknoloji|api|ödeme|odeme)", blob, re.IGNORECASE):
            continue
        if not positive.search(blob):
            continue
        raw_date = detect_date(title, path.replace("-", " "))
        candidates[url] = CandidateLink(
            title=title,
            url=url,
            score=24 if raw_date else 18,
            reason="turkishbank_news_link",
            raw_date_text=raw_date,
            date_source_hint="listing_page_nearby_date" if raw_date else "",
        )
    return sorted(candidates.values(), key=lambda item: item.score, reverse=True)


def extract_turk_ticaret_bankasi_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    positive = re.compile(
        r"(ihracat|ihracatçı|ihracatci|dış ticaret|dis ticaret|finansman|kredi|"
        r"işletme sermayesi|isletme sermayesi|teminat|akreditif|şube|sube|"
        r"nakdi|gayrinakdi|tim|eximbank|ige|reeskont|reel sektör|reel sektor)",
        re.IGNORECASE,
    )
    negative = re.compile(
        r"(siber güvenlik|siber guvenlik|salkım hesap|salkim hesap|sigorta|faaliyet raporu)",
        re.IGNORECASE,
    )
    candidates: dict[str, CandidateLink] = {}
    for anchor in soup.find_all("a", href=True):
        url = urljoin(base_url, normalize_text(anchor.get("href", "")))
        path = urlparse(url).path
        if not path.startswith("/icerik/"):
            continue
        if path in {"/icerik/duyurular", "/icerik/nakit-yonetimi", "/icerik/subeler", "/icerik/urun-ve-hizmet-ucretleri"}:
            continue
        parent_text = normalize_text(anchor.get_text(" ", strip=True))
        strong = anchor.find(["strong", "h2", "h3"])
        title = normalize_text(strong.get_text(" ", strip=True)) if strong else parent_text
        title = re.sub(r"\bDetaylı Bilgi\b", "", title, flags=re.IGNORECASE).strip() or title_from_slug(url)
        blob = f"{title} {parent_text} {path.replace('-', ' ')}"
        title_path_blob = f"{title} {path.replace('-', ' ')}"
        if negative.search(title_path_blob) and not re.search(r"(ihracat|şube|sube|finansman)", title_path_blob, re.IGNORECASE):
            continue
        if negative.search(blob) and not re.search(r"(ihracat|şube|sube|finansman|kredi)", blob, re.IGNORECASE):
            continue
        if not positive.search(blob):
            continue
        raw_date, date_hint = first_asset_date_from_node(anchor)
        candidate = CandidateLink(
            title=title,
            url=url,
            score=34 if raw_date else 24,
            reason="turk_ticaret_export_news",
            raw_date_text=raw_date,
            date_source_hint=date_hint if raw_date else "",
        )
        existing = candidates.get(url)
        if existing is None or candidate.score > existing.score or len(candidate.title) > len(existing.title):
            candidates[url] = candidate
    return sorted(candidates.values(), key=lambda item: item.score, reverse=True)


def title_without_date_suffix(title: str) -> str:
    cleaned = normalize_text(title)
    cleaned = DATE_RE.sub("", cleaned).strip(" -–|")
    return normalize_text(cleaned)


def batch_b_candidate_allowed(title: str, url: str, body: str = "") -> bool:
    parsed = urlparse(url)
    local = normalize_text(f"{parsed.path.replace('-', ' ')} {title} {body[:700]}")
    has_sme = bool(BATCH_B_STRONG_SME_RE.search(local))
    if BATCH_B_SCOPE_OUT_RE.search(local) and not has_sme:
        return False
    if BATCH_B_CONTEXT_ONLY_RE.search(local) and not has_sme:
        return False
    return has_sme


def extract_sekerbank_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    candidates: list[CandidateLink] = []
    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        try:
            data = json.loads(script.string)
            fallback = data.get("props", {}).get("pageProps", {}).get("fallback", [])
            announcement_list = fallback[0].get("announcementList", []) if fallback else []
            for item in announcement_list:
                title = normalize_text(item.get("title", ""))
                raw_url = normalize_text(item.get("url", ""))
                if raw_url and not raw_url.startswith(("http://", "https://", "/")):
                    raw_url = f"/{raw_url}"
                url = urljoin(base_url, raw_url)
                if not title or not url:
                    continue
                path = urlparse(url).path
                if "/duyurular/" in path and not batch_b_candidate_allowed(title, url):
                    continue
                if "/basin-bultenlerimiz/" not in path and not batch_b_candidate_allowed(title, url):
                    continue
                reason = "sekerbank_next_announcement"
                if BATCH_B_AWARD_RE.search(title):
                    reason += ",award_candidate"
                candidates.append(CandidateLink(title=title, url=url, score=28, reason=reason))
        except Exception as exc:
            logging.warning("Şekerbank embedded data parse failed: %s", exc)
    if candidates:
        return sorted({item.url: item for item in candidates}.values(), key=lambda item: item.score, reverse=True)

    generic, _ = extract_candidate_links_from_soup(soup, base_url)
    return [candidate for candidate in generic if batch_b_candidate_allowed(candidate.title, candidate.url)]


def extract_fibabanka_campaign_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    by_url: dict[str, CandidateLink] = {}
    for card in soup.select(".new-campaign-card"):
        card_text = normalize_text(card.get_text(" ", strip=True))
        for anchor in card.find_all("a", href=True):
            url = urljoin(base_url, normalize_text(anchor.get("href", "")))
            if "/kampanyalar/" not in urlparse(url).path:
                continue
            if canonicalize_url(url, base_url) == canonicalize_url(base_url, base_url):
                continue
            title = normalize_text(anchor.get_text(" ", strip=True))
            if len(title) > 180:
                title = normalize_text(title[:180])
            if not title:
                title = title_from_slug(url)
            if not batch_b_candidate_allowed(title, url, card_text):
                continue
            raw_date = ""
            match = DATE_RE.search(card_text)
            if match:
                raw_date = match.group(0)
            candidate = CandidateLink(
                title=title_without_date_suffix(title),
                url=url,
                score=30 if raw_date else 24,
                reason="fibabanka_campaign_card",
                raw_date_text=raw_date,
                date_source_hint="listing_page_nearby_date" if raw_date else "",
            )
            existing = by_url.get(url)
            if existing is None or candidate.score > existing.score or len(candidate.title) > len(existing.title):
                by_url[url] = candidate
    return sorted(by_url.values(), key=lambda item: item.score, reverse=True)


def extract_anadolubank_press_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    candidates: list[CandidateLink] = []
    scope = soup.select_one(".content-reports") or soup
    for li in scope.select("li"):
        link = li.find("a", href=True)
        if not link:
            continue
        url = urljoin(base_url, normalize_text(link.get("href", "")))
        text = normalize_text(li.get_text(" ", strip=True))
        title = normalize_text(re.sub(r"\bGörüntüle\b", "", text, flags=re.I))
        if not title:
            title = title_from_slug(url)
        path = urlparse(url).path
        if "/basin-bultenleri-ve-roportajlar/" not in path:
            continue
        if not batch_b_candidate_allowed(title, url, text):
            continue
        candidates.append(CandidateLink(title=title, url=url, score=24, reason="anadolubank_press_archive"))
    return sorted({item.url: item for item in candidates}.values(), key=lambda item: item.score, reverse=True)


def extract_odeabank_press_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    candidates: list[CandidateLink] = []
    for box in soup.select(".content-box--press-bulletin"):
        year_title = normalize_text(box.select_one(".content-box__title").get_text(" ", strip=True)) if box.select_one(".content-box__title") else ""
        for anchor in box.select("a.content-box__detail-link[href]"):
            url = urljoin(base_url, normalize_text(anchor.get("href", "")))
            title = normalize_text(anchor.get_text(" ", strip=True))
            if not title:
                title = title_from_slug(url)
            if not batch_b_candidate_allowed(title, url, year_title):
                continue
            reason = "odeabank_press_archive"
            if BATCH_B_AWARD_RE.search(title):
                reason += ",award_candidate"
            candidates.append(CandidateLink(title=title, url=url, score=24, reason=reason))
    return sorted({item.url: item for item in candidates}.values(), key=lambda item: item.score, reverse=True)


def visa_candidate_allowed(title: str, url: str) -> bool:
    parsed = urlparse(url)
    blob = f"{title} {parsed.path}".replace("-", " ")
    if VISA_NOISE_RE.search(blob):
        return False
    if "press-releases.releaseId." not in parsed.path:
        return False
    return bool(VISA_RELEVANT_RE.search(blob))


def extract_alternatif_bank_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    positive = re.compile(
        r"(kobi|ticari|kurumsal|bonus business|pos|sanal pos|yazarkasa pos|üye işyeri|uye isyeri|"
        r"tahsilat|nakit yönetimi|nakit yonetimi|dış ticaret|dis ticaret|vov tüzel|vov tuzel|"
        r"işletme|isletme|kgf|ihracat|iş birliği|is birligi|api|dijital ticari|masrafsız bankacılık|masrafsiz bankacilik)",
        re.IGNORECASE,
    )
    negative = re.compile(
        r"(restoran|kozmetik|giyim|sevgililer günü|sevgililer gunu|okul alışverişi|okul alisverisi|"
        r"kişisel kart|kisisel kart|bireysel|akaryakıt|akaryakit|tatil|sinema|çekiliş|cekilis|ihtiyaç kredisi|ihtiyac kredisi)",
        re.IGNORECASE,
    )
    candidates: list[CandidateLink] = []
    for item in soup.select(".item"):
        link = item.find("a", href=True)
        if not link:
            continue
        url = urljoin(base_url, link.get("href", ""))
        text = normalize_text(item.get_text(" ", strip=True))
        date_match = DATE_RE.search(text)
        title = text
        if date_match:
            title = normalize_text(text[: date_match.start()])
        title = re.sub(r"\bDetaylı Bilgi Al\b", "", title, flags=re.IGNORECASE).strip()
        blob = f"{title} {url}"
        if not title or negative.search(blob) or not positive.search(blob):
            continue
        raw_date = date_match.group(0) if date_match else ""
        candidates.append(
            CandidateLink(
                title=title,
                url=url,
                score=28 if raw_date else 18,
                reason="alternatif_bank_press_card",
                raw_date_text=raw_date,
                date_source_hint="listing_page_nearby_date" if raw_date else "",
            )
        )
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def extract_ing_links(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    positive = re.compile(
        r"(kobi|kobilere|ticari|ing business|pos|üye işyeri|uye isyeri|şirket kredi kartı|"
        r"sirket kredi karti|dijital ticari|nakit yönetimi|nakit yonetimi|tahsilat|açık bankacılık|"
        r"acik bankacilik|api|e-fatura|dış ticaret|dis ticaret|leasing|kobi finansmanı|ödeme|odeme)",
        re.IGNORECASE,
    )
    negative = re.compile(
        r"(emekli|bireysel ihtiyaç|bireysel ihtiyac|turuncu hesap|konut|taşıt|tasit|"
        r"bireysel kart|çalışan|calisan|spor|sponsor|tasarruf araştırması|tasarruf arastirmasi|"
        r"practica|yetenek programı|yetenek programi|anaokulu|kampüs|kampus|kadınlar günü|kadinlar gunu|"
        r"üst düzey atama|ust duzey atama|finansal sonuç|finansal sonuc|aktif büyüklüğü|aktif buyuklugu)",
        re.IGNORECASE,
    )
    candidates: list[CandidateLink] = []
    for anchor in soup.find_all("a", href=True):
        href = normalize_text(anchor.get("href", ""))
        if ".pdf" not in href.casefold():
            continue
        card = anchor.find_parent("div", class_="line") or anchor.parent
        text = normalize_text(card.get_text(" ", strip=True) if card else anchor.get_text(" ", strip=True))
        date_match = re.search(r"\b\d{1,2}[./]\d{1,2}[./]\d{4}\b", text)
        strong = card.find("strong") if card else None
        title = normalize_text(strong.get_text(" ", strip=True)) if strong else title_from_url_filename(href)
        if date_match and title.startswith(date_match.group(0)):
            title = normalize_text(title[len(date_match.group(0)) :])
        blob = f"{title} {href} {text[:300]}"
        if negative.search(blob) or not positive.search(blob):
            continue
        raw_date = date_match.group(0) if date_match else ""
        candidates.append(
            CandidateLink(
                title=title,
                url=urljoin(base_url, href),
                score=30 if raw_date else 18,
                reason="ing_press_pdf_card",
                raw_date_text=raw_date,
                date_source_hint="listing_page_nearby_date" if raw_date else "",
            )
        )
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def extract_visa_candidates(soup: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    candidates, _ = extract_candidate_links_from_soup(soup, base_url)
    filtered = [
        CandidateLink(
            title=candidate.title,
            url=candidate.url,
            score=candidate.score + 6,
            reason=f"visa_relevant,{candidate.reason}",
            raw_date_text=candidate.raw_date_text,
            date_source_hint=candidate.date_source_hint,
        )
        for candidate in candidates
        if visa_candidate_allowed(candidate.title, candidate.url)
    ]
    return sorted(filtered, key=lambda item: item.score, reverse=True)


def qnb_candidate_allowed(title: str, url: str) -> bool:
    blob = f"{title} {url}".replace("-", " ")
    if not QNB_POSITIVE_RE.search(blob):
        return False
    if QNB_NEGATIVE_RE.search(blob) and not re.search(r"(kobi|ticari|pos|üye işyeri|uye isyeri|kobi rahat)", blob, re.I):
        return False
    return True


def qnb_api_date(value: object) -> str:
    text = normalize_text(str(value or ""))
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{day}.{month}.{year}"


def extract_qnb_api_campaign_candidates(base_url: str) -> list[CandidateLink]:
    candidates = []
    try:
        response = requests.get(QNB_CAMPAIGN_API_URL, timeout=20, headers={**HEADERS, "Accept": "application/json"})
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logging.warning("QNB campaign API fetch failed: %s", exc)
        return []

    for item in data.get("Items", []):
        title = normalize_text(item.get("Title", ""))
        campaign_url = normalize_text(item.get("CampaignUrl", ""))
        external_url = normalize_text(item.get("ExternalUrl", ""))
        detail_url = urljoin("https://www.qnb.com.tr/kampanyalar/", campaign_url) if campaign_url else external_url
        if not title or not detail_url:
            continue
        if not qnb_candidate_allowed(title, detail_url):
            continue
        start_date = qnb_api_date(item.get("StartDate", ""))
        end_date = qnb_api_date(item.get("EndDate", ""))
        raw_date = start_date or end_date
        reason = "qnb_campaign_api"
        if start_date:
            reason += ",api_start_date"
        elif end_date:
            reason += ",api_end_date"
        candidates.append(
            CandidateLink(
                title=title,
                url=detail_url,
                score=24 if start_date else 18,
                reason=reason,
                raw_date_text=raw_date,
                date_source_hint="listing_page_nearby_date" if raw_date else "",
            )
        )
    return candidates


def extract_qnb_card_campaign_candidates(scope: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    by_url: dict[str, CandidateLink] = {}
    for anchor in scope.find_all("a"):
        href = normalize_text(anchor.get("href") or "")
        if not href:
            continue
        url = urljoin(base_url, href)
        if not QNB_CARD_DETAIL_RE.search(urlparse(url).path):
            continue
        title = best_link_title(anchor.get_text(" ", strip=True), url)
        if not title or title.lower() in {"detaylı bilgi", "detayli bilgi"}:
            title = title_from_slug(url)
        if not qnb_candidate_allowed(title, url):
            continue
        candidate = CandidateLink(title=title, url=url, score=22, reason="qnbcard_kobi_campaign_detail")
        existing = by_url.get(url)
        if existing is None or len(candidate.title) > len(existing.title):
            by_url[url] = candidate
    return sorted(by_url.values(), key=lambda item: item.score, reverse=True)


def extract_qnb_candidates(soup: BeautifulSoup, base_url: str, source_id: str) -> list[CandidateLink]:
    candidates = []
    if source_id == "REG-061":
        candidates.extend(extract_qnb_api_campaign_candidates(base_url))
    card_candidates = extract_qnb_card_campaign_candidates(soup, base_url)
    candidates.extend(card_candidates)
    if source_id == "REG-062":
        return card_candidates
    if source_id != "REG-061":
        scope = soup.select_one("main") or soup.select_one(".content") or soup
        for anchor in scope.find_all("a"):
            href = normalize_text(anchor.get("href") or "")
            title = normalize_text(anchor.get_text(" ", strip=True))
            if not href:
                continue
            url = urljoin(base_url, href)
            if not is_same_or_subdomain(base_url, url) or not qnb_candidate_allowed(title, url):
                continue
            score, reason = score_link(title, url)
            if score <= 0:
                continue
            candidates.append(CandidateLink(title=title or title_from_slug(url), url=url, score=score, reason=f"qnb_generic,{reason}"))
    dedup = {}
    for candidate in candidates:
        existing = dedup.get(candidate.url)
        if existing is None or candidate.score > existing.score:
            dedup[candidate.url] = candidate
    return sorted(dedup.values(), key=lambda item: item.score, reverse=True)


def extract_yapi_kredi_campaign_candidates(scope: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    by_url: dict[str, CandidateLink] = {}
    for anchor in scope.find_all("a"):
        href = normalize_text(anchor.get("href") or "")
        if not href:
            continue
        url = urljoin(base_url, href)
        if not YAPI_KREDI_CAMPAIGN_DETAIL_RE.search(urlparse(url).path):
            continue
        title = normalize_text(anchor.get_text(" ", strip=True))
        if not title or title.lower() in {"detaylı bilgi", "detayli bilgi"}:
            title = title_from_slug(url)
        score = 20 if 20 <= len(title) <= 180 else 16
        existing = by_url.get(url)
        if existing is None or score > existing.score or len(title) > len(existing.title):
            by_url[url] = CandidateLink(title=title, url=url, score=score, reason="yapi_kredi_campaign_detail")
    return sorted(by_url.values(), key=lambda item: item.score, reverse=True)


def extract_yapi_kredi_press_candidates(scope: BeautifulSoup, base_url: str) -> list[CandidateLink]:
    grouped: dict[str, list[str]] = {}
    for anchor in scope.find_all("a"):
        href = normalize_text(anchor.get("href") or "")
        if not href:
            continue
        url = urljoin(base_url, href)
        if not YAPI_KREDI_PRESS_DOWNLOAD_RE.search(urlparse(url).path):
            continue
        text = normalize_text(anchor.get_text(" ", strip=True))
        grouped.setdefault(url, [])
        if text:
            grouped[url].append(text)

    candidates = []
    for url, texts in grouped.items():
        title = ""
        raw_date = ""
        for text in texts:
            parsed_date = parse_turkish_date(text, "listing_page_nearby_date", "Orta")
            if parsed_date["normalized_date"]:
                raw_date = text
                continue
            if not title and 20 <= len(text) <= 180:
                title = text
        if not title:
            title = title_from_slug(url)
        candidates.append(
            CandidateLink(
                title=title,
                url=url,
                score=22,
                reason="yapi_kredi_press_download",
                raw_date_text=raw_date,
                date_source_hint="listing_page_nearby_date" if raw_date else "",
            )
        )
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def extract_candidate_links_from_soup(soup: BeautifulSoup, base_url: str) -> tuple[list[CandidateLink], int]:
    candidates = []
    seen_urls = set()
    total_links = 0
    for anchor in soup.find_all("a"):
        total_links += 1
        href = normalize_text(anchor.get("href") or "")
        if not href:
            continue
        url = urljoin(base_url, href)
        title = best_link_title(anchor.get_text(" ", strip=True), url)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if not is_same_or_subdomain(base_url, url):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        if is_negative_link(title, url):
            continue
        if not title and DETAIL_PATH_RE.search(parsed.path):
            title = title_from_slug(url)
        score, reason = score_link(title, url)
        if score <= 0:
            continue
        if not (20 <= len(title) <= 180) and not DETAIL_PATH_RE.search(parsed.path):
            continue
        date_match = DATE_RE.search(title)
        candidates.append(
            CandidateLink(
                title=title,
                url=url,
                score=score,
                reason=reason,
                raw_date_text=date_match.group(0) if date_match else "",
                date_source_hint="listing_page_nearby_date" if date_match else "",
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates, total_links


def fetch_html(url: str) -> str:
    response = get_with_source_ssl_fallback(url, timeout=20)
    response.raise_for_status()
    return response.text


def fetch_detail_text(url: str) -> tuple[str, str]:
    response = get_with_source_ssl_fallback(url, timeout=25)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").casefold()
    content = response.content
    if "application/pdf" in content_type or content.startswith(b"%PDF"):
        return "", extract_pdf_text(content)
    return clean_html_text(response.text)


def should_fetch_detail_for_candidate(row: pd.Series, args: argparse.Namespace) -> bool:
    source_id = str(row.get("source_id", ""))
    source_url = str(row.get("url", "") or "")
    if args.fetch_detail_pages:
        return True
    if source_id in ENPARA_WEEKLY_SOURCE_IDS:
        return True
    if "turkticaretbankasi.com.tr/icerikler/" in source_url:
        return True
    return False


def extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError(f"PDF extraction unavailable: {exc}") from exc

    reader = PdfReader(io.BytesIO(content))
    lines = []
    for page in reader.pages[:8]:
        page_text = page.extract_text() or ""
        for raw_line in page_text.splitlines():
            line = normalize_text(raw_line)
            if len(line) >= 3:
                lines.append(line)
    return "\n".join(lines).strip()


def clean_html_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = normalize_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "svg", "header", "nav", "footer"]):
        tag.decompose()
    noisy = re.compile(r"(cookie|çerez|kvkk|menu|menü|footer|header|social|sosyal|breadcrumb)", re.I)
    for tag in list(soup.find_all(True)):
        attrs_dict = getattr(tag, "attrs", None) or {}
        classes = attrs_dict.get("class", "")
        if isinstance(classes, list):
            classes = " ".join(str(value) for value in classes)
        attrs = " ".join(
            str(value)
            for value in [
                attrs_dict.get("id", ""),
                classes,
                attrs_dict.get("role", ""),
                attrs_dict.get("aria-label", ""),
            ]
            if value
        )
        if noisy.search(attrs):
            tag.decompose()
    candidates = []
    for selector in ["main", "article", "[role='main']", ".search-content", ".left-colm", ".detail-wrap", ".content", ".page-content", "#content", "body"]:
        candidates.extend(soup.select(selector))
    if not candidates:
        candidates = [soup]
    best = max(candidates, key=lambda node: len(node.get_text(" ", strip=True)))
    lines = []
    seen = set()
    for raw_line in best.get_text("\n", strip=True).splitlines():
        line = normalize_text(raw_line)
        if len(line) < 3 or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return title, "\n".join(lines).strip()


def detect_date(*texts: str) -> str:
    for text in texts:
        match = DATE_RE.search(str(text or ""))
        if match:
            return match.group(0)
    return ""


def visa_us_date_semantics(*texts: str) -> dict[str, str]:
    for text in texts:
        match = US_SLASH_DATE_RE.search(str(text or ""))
        if not match:
            continue
        month = int(match.group("month"))
        day = int(match.group("day"))
        year = int(match.group("year"))
        try:
            normalized = datetime(year, month, day).date().isoformat()
        except ValueError:
            continue
        raw = match.group(0)
        result = {
            "publication_date": "",
            "announcement_date": normalized,
            "campaign_start_date": "",
            "campaign_end_date": "",
            "event_date_type": "Duyuru Tarihi",
            "recency_basis_date": normalized,
            "recency_basis_reason": "Visa US press release date interpreted as MM/DD/YYYY",
            "date_confidence": "Yüksek",
            "raw_date_text": raw,
            "normalized_date": normalized,
            "date_source": "visa_us_press_date",
        }
        return result
    return {}


def english_publication_date_semantics(*texts: str) -> dict[str, str]:
    for text in texts:
        normalized = english_date_to_iso(str(text or ""))
        if not normalized:
            continue
        raw_match = ENGLISH_MDY_DATE_RE.search(str(text or "")) or ENGLISH_DMY_DATE_RE.search(str(text or ""))
        raw = raw_match.group(0) if raw_match else normalized
        return {
            "publication_date": normalized,
            "announcement_date": "",
            "campaign_start_date": "",
            "campaign_end_date": "",
            "event_date_type": "Yayın Tarihi",
            "recency_basis_date": normalized,
            "recency_basis_reason": "English publication date extracted from listing/detail text",
            "date_confidence": "Yüksek",
            "raw_date_text": raw,
            "normalized_date": normalized,
            "date_source": "english_publication_date",
        }
    return {}


def title_from_detail(detail_title: str, link_title: str, url: str) -> str:
    cleaned_detail_title = re.sub(r"\s*\|\s*Garanti BBVA\s*$", "", detail_title or "").strip()
    cleaned_detail_title = re.sub(
        r"\s*\|\s*(Wise Newsroom|Checkout\\.com|The Paypers|Payments Dive|Banking Dive|PYMNTS(?:\\.com)?)\s*$",
        "",
        cleaned_detail_title,
    ).strip()
    generic_detail_re = re.compile(
        r"^(basın bültenleri ve duyurular|basın bültenleri|basın odası|kampanyalar|"
        r"duyuru detay|duyuru listesi|duyuru kategorileri)"
        r"(\s*\|\s*[^|]+)?$",
        re.IGNORECASE,
    )
    if cleaned_detail_title and generic_detail_re.match(cleaned_detail_title) and link_title:
        title = link_title
    else:
        title = cleaned_detail_title or link_title
    title = re.sub(
        r"\s*\|\s*(Garanti BBVA|Wise Newsroom|Checkout\\.com|The Paypers|Payments Dive|Banking Dive|PYMNTS(?:\\.com)?)\s*$",
        "",
        title,
    ).strip()
    if not title or is_generic_link_title(title):
        title = title_from_url_filename(url) if urlparse(url).path.casefold().endswith(".pdf") else title_from_slug(url)
    return title


def is_listing_url(url: str) -> bool:
    parsed = urlparse(url)
    if LISTING_PATH_RE.search(parsed.path):
        return True
    if parsed.path.startswith("/kampanyalar/") and "v=ticari" in parsed.query.casefold():
        return True
    return False


def discover_links_for_document(row: pd.Series, debug: bool = False) -> tuple[list[CandidateLink], dict[str, int]]:
    source_candidates, total_links = extract_candidate_links_from_html(
        row.get("raw_html_path", ""), row.get("url", ""), row.get("source_id", "")
    )
    all_candidates = list(source_candidates)
    detail_pages_fetched = 0

    for candidate in source_candidates:
        if row.get("source_id", "") in QNB_SOURCE_IDS:
            continue
        if not is_listing_url(candidate.url):
            continue
        try:
            html = fetch_html(candidate.url)
            detail_pages_fetched += 1
            soup = BeautifulSoup(html, "html.parser")
            nested, nested_total = extract_candidate_links_from_soup(soup, candidate.url)
            total_links += nested_total
            all_candidates.extend(nested)
        except Exception as exc:
            logging.warning("Listing fetch failed %s: %s", candidate.url, exc)

    dedup = {}
    for candidate in all_candidates:
        existing = dedup.get(candidate.url)
        if existing is None or candidate.score > existing.score:
            dedup[candidate.url] = candidate
    candidates = sorted(dedup.values(), key=lambda item: item.score, reverse=True)
    if debug:
        print_candidate_report(row, total_links, candidates)
    return candidates, {"total_links": total_links, "candidate_links": len(candidates), "detail_pages_fetched": detail_pages_fetched}


def print_candidate_report(row: pd.Series, total_links: int, candidates: list[CandidateLink]) -> None:
    print("\nCANDIDATE REPORT")
    print(f"source_id: {row.get('source_id', '')}")
    print(f"source_name: {row.get('source_name', '')}")
    print(f"source_url: {row.get('url', '')}")
    print(f"total links found: {total_links}")
    print(f"candidate links found: {len(candidates)}")
    for candidate in candidates[:20]:
        print(f"- score={candidate.score} | title={candidate.title[:120]} | url={candidate.url} | reason={candidate.reason}")


def quality_for_item(title: str, text: str, item_url: str, source_url: str, method: str, allow_fallback: bool) -> tuple[str, str]:
    if len(title) < 20:
        return "Poor", "title_too_short"
    if BAD_TITLE_RE.search(title):
        return "Poor", "bad_fallback_title"
    if item_url == source_url and not allow_fallback:
        return "Poor", "item_url_equals_source_url"
    if method == "detail_page_fetch" and len(text) < 300:
        return "Poor", "detail_text_too_short"
    if len(text) >= 900:
        return "Good", "detail_text_rich"
    return "Medium", "acceptable"


def recency_basis_type_for(date_source: str, event_date_type: str = "") -> str:
    source = str(date_source or "").strip()
    event = str(event_date_type or "").strip()
    if source == "publication_date" or event == "Yayın Tarihi":
        return "publication_date"
    if source == "campaign_start_date" or event == "Kampanya Başlangıç Tarihi":
        return "campaign_start_date"
    if source == "announcement_date" or event == "Duyuru Tarihi":
        return "publication_date"
    if source in {"material_revision_date", "event_date"}:
        return source
    return "unknown"


def build_item_row(
    row: pd.Series,
    title: str,
    item_url: str,
    item_text: str,
    item_date: str,
    method: str,
    quality: str,
    date_meta: dict[str, str],
    recency: dict[str, object],
    classification: dict[str, object],
) -> dict[str, str]:
    canonical_item_url = canonicalize_url(item_url, row.get("url", ""))
    normalized_title = normalize_title_for_dedupe(title)
    recency_basis_date = str(recency.get("recency_basis_date", date_meta.get("recency_basis_date", "")) or "")
    content_fingerprint = content_fingerprint_for(row.get("institution_name", ""), canonical_item_url, normalized_title, recency_basis_date)
    item_hash = content_fingerprint
    recency_basis_type = recency_basis_type_for(date_meta.get("date_source", ""), date_meta.get("event_date_type", ""))
    return {
        "recent_item_id": recent_item_id_for(content_fingerprint),
        "document_id": row["document_id"],
        "source_id": row["source_id"],
        "tier": row.get("tier", ""),
        "institution_id": row.get("institution_id", ""),
        "institution_name": row.get("institution_name", ""),
        "source_name": row.get("source_name", ""),
        "source_type": to_tr(row.get("source_type", "")),
        "source_url": row.get("url", ""),
        "item_title": title,
        "item_date": item_date,
        "item_url": item_url,
        "item_text": item_text,
        "item_hash": item_hash,
        "canonical_item_url": canonical_item_url,
        "normalized_title": normalized_title,
        "content_fingerprint": content_fingerprint,
        "detected_at": now_iso(),
        "extraction_method": method,
        "relevance_status": "Beklemede",
        "content_role": classification.get("content_role", "Bağımsız Gelişme"),
        "item_quality": quality,
        "publication_date": date_meta.get("publication_date", ""),
        "announcement_date": date_meta.get("announcement_date", ""),
        "campaign_start_date": date_meta.get("campaign_start_date", ""),
        "campaign_end_date": date_meta.get("campaign_end_date", ""),
        "event_date_type": date_meta.get("event_date_type", "Belirsiz"),
        "recency_basis_date": recency.get("recency_basis_date", date_meta.get("recency_basis_date", "")),
        "recency_basis_type": recency_basis_type,
        "recency_basis_reason": recency.get("recency_basis_reason", date_meta.get("recency_basis_reason", "")),
        "is_active_campaign": bool(recency.get("is_active_campaign", False)),
        "active_campaign_reason": recency.get("active_campaign_reason", ""),
        "cluster_published": False,
        "cluster_id": "",
        "normalized_item_date": date_meta.get("normalized_date", ""),
        "date_confidence": date_meta.get("date_confidence", "Yok"),
        "date_source": date_meta.get("date_source", "missing"),
        "is_recent": bool(recency.get("is_recent", False)),
        "recency_cutoff": recency.get("recency_cutoff", ""),
        "recency_reason": recency.get("recency_reason", ""),
        "development_candidate_type": classification.get("development_candidate_type", "Belirsiz"),
        "is_actual_development": bool(classification.get("is_actual_development", False)),
        "actual_development_reason": classification.get("actual_development_reason", ""),
    }


def build_audit_row(
    run_id_value: str,
    row: pd.Series,
    candidate_title: str,
    candidate_url: str,
    date_meta: dict[str, str],
    recency: dict[str, object],
    classification: dict[str, object],
    item_quality: str,
    saved: bool,
    rejected_reason: str,
    duplicate_of_recent_item_id: str = "",
) -> dict[str, str]:
    canonical_item_url = canonicalize_url(candidate_url, row.get("url", ""))
    normalized_title = normalize_title_for_dedupe(candidate_title)
    recency_basis_date = str(recency.get("recency_basis_date", date_meta.get("recency_basis_date", "")) or "")
    content_fingerprint = content_fingerprint_for(row.get("institution_name", ""), canonical_item_url, normalized_title, recency_basis_date)
    recency_basis_type = recency_basis_type_for(date_meta.get("date_source", ""), date_meta.get("event_date_type", ""))
    return {
        "audit_id": audit_id_for(run_id_value, str(row.get("source_id", "")), candidate_url),
        "run_id": run_id_value,
        "institution_name": row.get("institution_name", ""),
        "source_id": row.get("source_id", ""),
        "source_name": row.get("source_name", ""),
        "candidate_title": candidate_title,
        "candidate_url": candidate_url,
        "canonical_item_url": canonical_item_url,
        "normalized_title": normalized_title,
        "content_fingerprint": content_fingerprint,
        "raw_date_text": date_meta.get("raw_date_text", ""),
        "publication_date": date_meta.get("publication_date", ""),
        "announcement_date": date_meta.get("announcement_date", ""),
        "campaign_start_date": date_meta.get("campaign_start_date", ""),
        "campaign_end_date": date_meta.get("campaign_end_date", ""),
        "event_date_type": date_meta.get("event_date_type", "Belirsiz"),
        "recency_basis_date": recency.get("recency_basis_date", date_meta.get("recency_basis_date", "")),
        "recency_basis_type": recency_basis_type,
        "recency_basis_reason": recency.get("recency_basis_reason", date_meta.get("recency_basis_reason", "")),
        "is_active_campaign": bool(recency.get("is_active_campaign", False)),
        "active_campaign_reason": recency.get("active_campaign_reason", ""),
        "normalized_item_date": date_meta.get("normalized_date", ""),
        "date_confidence": date_meta.get("date_confidence", "Yok"),
        "date_source": date_meta.get("date_source", "missing"),
        "is_recent": bool(recency.get("is_recent", False)),
        "recency_cutoff": recency.get("recency_cutoff", ""),
        "recency_reason": recency.get("recency_reason", ""),
        "development_candidate_type": classification.get("development_candidate_type", "Belirsiz"),
        "is_actual_development": bool(classification.get("is_actual_development", False)),
        "actual_development_reason": classification.get("actual_development_reason", ""),
        "content_role": classification.get("content_role", "Bağımsız Gelişme"),
        "content_role_reason": classification.get("content_role_reason", ""),
        "item_quality": item_quality,
        "saved_to_recent_items": bool(saved),
        "rejected_reason": rejected_reason,
        "duplicate_of_recent_item_id": duplicate_of_recent_item_id,
        "checked_at": now_iso(),
    }


def rejection_reason(
    quality: str,
    quality_reason: str,
    recency: dict[str, object],
    classification: dict[str, object],
    save_non_recent: bool,
    save_non_developments: bool,
) -> str:
    if quality not in {"Good", "Medium"}:
        return quality_reason
    if not bool(recency.get("is_recent")) and not save_non_recent:
        return str(recency.get("recency_reason", "recent değil"))
    if not bool(classification.get("is_actual_development")) and not save_non_developments:
        return str(classification.get("actual_development_reason", "actual development değil"))
    return ""


def date_meta_for_candidate(candidate: CandidateLink, detail_title: str, detail_text: str, item_date: str, row: pd.Series) -> dict[str, str]:
    if str(row.get("source_id", "")) in VISA_RECENT_SOURCE_IDS:
        visa_result = visa_us_date_semantics(item_date, detail_title, detail_text, candidate.title)
        if visa_result:
            return visa_result
    if str(row.get("source_id", "")) in GLOBAL_PAYMENTS_SOURCE_IDS:
        english_result = english_publication_date_semantics(
            candidate.raw_date_text,
            item_date,
            detail_title,
            detail_text[:2500],
            candidate.title,
        )
        if english_result:
            return english_result
    listing_text = candidate.raw_date_text or candidate.title
    if candidate.raw_date_text:
        result = parse_turkish_date(candidate.raw_date_text, candidate.date_source_hint or "listing_page_nearby_date", "Orta")
        if result["normalized_date"]:
            listing_text = candidate.raw_date_text
    return extract_date_semantics(
        visible_text=item_date or f"{detail_title}\n{detail_text[:1200]}",
        url=candidate.url,
        listing_text=listing_text,
        metadata_text="",
        inferred_text=f"{candidate.title}\n{detail_title}\n{detail_text[:2000]}",
        source_type=row.get("source_type", ""),
    )


def filter_documents(metadata: pd.DataFrame, registry: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    registry_cols = ["source_id", "source_type", "extraction_mode", "url", "source_name", "institution_id", "institution_name", "tier"]
    merged = metadata.merge(registry[registry_cols], on="source_id", how="left", suffixes=("", "_registry"))
    for column in ["tier", "institution_id", "institution_name", "source_name", "url"]:
        registry_column = f"{column}_registry"
        if registry_column in merged.columns:
            merged[column] = merged[column].fillna(merged[registry_column])
    if "change_status" not in merged.columns:
        merged["change_status"] = merged.get("status", "")
    merged["source_type_tr"] = merged["source_type"].apply(to_tr)
    if args.force or (args.dry_run and args.debug_candidates):
        freshness_mask = merged.get("status", "").astype(str).eq("fetched")
    else:
        freshness_mask = merged["change_status"].isin(["new_source", "changed"])
    candidates = merged[
        freshness_mask
        & merged["extraction_mode"].isin(["weekly_development", "both"])
        & (merged["source_type"].isin(WEEKLY_SOURCE_TYPES) | merged["source_type_tr"].isin(WEEKLY_SOURCE_TYPES))
    ].copy()
    if args.institution:
        token = args.institution.strip().casefold()
        candidates = candidates[
            candidates["institution_name"].astype(str).str.casefold().eq(token)
            | candidates["institution_id"].astype(str).str.casefold().eq(token)
        ]
    if args.source_id:
        candidates = candidates[candidates["source_id"].astype(str).eq(args.source_id)]
    candidates = candidates.sort_values("fetched_at", ascending=False)
    candidates = candidates.drop_duplicates("source_id", keep="first")
    if args.limit is not None:
        candidates = candidates.head(args.limit)
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Tekil haber/kampanya/duyuru linklerini çıkar.")
    parser.add_argument("--institution", default=None, help='Kurum adı veya id filtresi, örn. "Garanti BBVA".')
    parser.add_argument("--source-id", default=None, help="Belirli source_id filtresi.")
    parser.add_argument("--limit", type=int, default=None, help="İlk N uygun dokümanı işle.")
    parser.add_argument("--force", action="store_true", help="İşlenen kaynaklar için eski recent item satırlarını değiştir.")
    parser.add_argument("--dry-run", action="store_true", help="Adayları yazmadan logla.")
    parser.add_argument("--debug-candidates", action="store_true", help="Kaynak bazında aday link raporu yazdır.")
    parser.add_argument("--fetch-detail-pages", action="store_true", help="Aday link detay sayfalarını çek ve item_text üret.")
    parser.add_argument("--allow-fallback", action="store_true", help="Açıkça istenirse kaynak sayfasından fallback item oluştur.")
    parser.add_argument("--save-poor", action="store_true", help="Poor kalite satırlarını da kaydet.")
    parser.add_argument("--start-date", default=None, help="Recent-development kesim tarihi, örn. 2026-05-01.")
    parser.add_argument("--allow-undated", action="store_true", help="Tarihsiz adayları manuel izinle geçir.")
    parser.add_argument("--allow-low-date-confidence", action="store_true", help="Düşük tarih güvenli adayları geçir.")
    parser.add_argument("--allow-end-date-recency", action="store_true", help="Sadece kampanya bitiş tarihi bulunan adayları manuel izinle geçir.")
    parser.add_argument("--save-non-recent", action="store_true", help="Recent olmayan adayları da recent_items.csv içine kaydet.")
    parser.add_argument("--save-non-developments", action="store_true", help="Actual development olmayan adayları da recent_items.csv içine kaydet.")
    args = parser.parse_args()

    start_date = resolve_start_date(args.start_date)
    allow_undated = args.allow_undated or bool_from_env("ALLOW_UNDATED_RECENT_ITEMS", False)
    allow_low_date_confidence = args.allow_low_date_confidence or bool_from_env("ALLOW_LOW_DATE_CONFIDENCE", False)
    allow_end_date_recency = args.allow_end_date_recency or bool_from_env("ALLOW_END_DATE_RECENCY", False)
    run_id_value = run_id()

    metadata = pd.read_csv(METADATA_PATH, encoding="utf-8-sig")
    registry = pd.read_csv(REGISTRY_PATH, encoding="utf-8-sig")
    documents = filter_documents(metadata, registry, args)
    existing = read_recent_items()
    if args.force and not documents.empty:
        processed_sources = set(documents["source_id"].dropna().astype(str))
        existing_for_dedupe = existing[~existing["source_id"].astype(str).isin(processed_sources)].copy()
    else:
        existing_for_dedupe = existing.copy()
    dedupe_index = duplicate_index(existing_for_dedupe)

    logging.info("Documents considered: %s", len(documents))
    logging.info("Recency cutoff: %s", start_date)
    logging.info("Allow undated: %s", allow_undated)
    logging.info("Allow low date confidence: %s", allow_low_date_confidence)
    logging.info("Allow end-date recency: %s", allow_end_date_recency)
    stats = {
        "total_links": 0,
        "candidate_links": 0,
        "detail_pages_fetched": 0,
        "created": 0,
        "poor": 0,
        "duplicates": 0,
        "errors": 0,
        "rejected_old": 0,
        "rejected_undated": 0,
        "rejected_low_confidence": 0,
        "rejected_non_developments": 0,
        "saved_by_publication_date": 0,
        "saved_by_announcement_date": 0,
        "saved_by_campaign_start_date": 0,
        "passed_by_end_date_manual_override": 0,
        "rejected_only_campaign_end_date": 0,
        "active_old_campaigns": 0,
        "content_role_bagimsiz": 0,
        "content_role_context_only": 0,
        "content_role_awareness": 0,
        "content_role_scope_out": 0,
    }
    new_rows = []
    audit_rows = []
    saved_examples = []
    rejected_examples = []

    for _, row in documents.iterrows():
        try:
            candidates, doc_stats = discover_links_for_document(row, debug=args.debug_candidates)
            stats["total_links"] += doc_stats["total_links"]
            stats["candidate_links"] += doc_stats["candidate_links"]
            stats["detail_pages_fetched"] += doc_stats["detail_pages_fetched"]

            for candidate in candidates[:50]:
                if is_listing_url(candidate.url):
                    continue
                method = "link_discovery"
                item_title = candidate.title
                item_text = candidate.title
                item_date = ""
                detail_title = ""
                detail_text = ""

                if should_fetch_detail_for_candidate(row, args):
                    try:
                        stats["detail_pages_fetched"] += 1
                        detail_title, detail_text = fetch_detail_text(candidate.url)
                        item_title = title_from_detail(detail_title, candidate.title, candidate.url)
                        item_text = detail_text
                        item_date = detect_date(detail_title, detail_text)
                        method = "detail_page_fetch"
                    except Exception as exc:
                        logging.warning("Detail fetch failed %s: %s", candidate.url, exc)
                        continue

                quality, reason = quality_for_item(item_title, item_text, candidate.url, row.get("url", ""), method, args.allow_fallback)
                date_meta = date_meta_for_candidate(candidate, detail_title, detail_text, item_date, row)
                if date_meta.get("normalized_date") and not item_date:
                    item_date = date_meta["raw_date_text"]
                recency = evaluate_recency(
                    {**date_meta, "date_confidence": date_meta.get("date_confidence", "Yok")},
                    start_date,
                    allow_undated=allow_undated,
                    allow_low_confidence=allow_low_date_confidence,
                    allow_end_date_recency=allow_end_date_recency,
                )
                classification = classify_actual_development(item_title, item_text, candidate.url, row.get("source_type", ""))
                content_role, content_role_reason = classify_content_role_for_candidate(row, item_title, candidate.url, item_text)
                classification["content_role"] = content_role
                classification["content_role_reason"] = content_role_reason
                if content_role == "Bağımsız Gelişme":
                    stats["content_role_bagimsiz"] += 1
                elif content_role == "Bağlamsal Veri":
                    stats["content_role_context_only"] += 1
                    classification["is_actual_development"] = False
                    classification["development_candidate_type"] = content_role
                    classification["actual_development_reason"] = content_role_reason
                elif content_role == "Yönetici Bilgilendirme":
                    stats["content_role_awareness"] += 1
                    classification["is_actual_development"] = True
                    classification["development_candidate_type"] = content_role
                    classification["actual_development_reason"] = content_role_reason
                elif content_role in {"Benchmark Bilgisi", "Kapsam Dışı"}:
                    stats["content_role_scope_out"] += 1
                    classification["is_actual_development"] = False
                    classification["development_candidate_type"] = content_role
                    classification["actual_development_reason"] = content_role_reason
                reject_reason = rejection_reason(
                    quality,
                    reason,
                    recency,
                    classification,
                    args.save_non_recent,
                    args.save_non_developments,
                )
                if quality == "Poor":
                    stats["poor"] += 1
                    logging.info("Poor item skipped | %s | %s | %s", reason, item_title[:100], candidate.url)
                if reject_reason:
                    recency_reason = str(recency.get("recency_reason", ""))
                    if "eski" in recency_reason:
                        stats["rejected_old"] += 1
                    elif "Tarih yok" in recency_reason:
                        stats["rejected_undated"] += 1
                    elif "tarih güveni" in recency_reason:
                        stats["rejected_low_confidence"] += 1
                    elif "kampanya bitiş tarihi" in recency_reason:
                        stats["rejected_only_campaign_end_date"] += 1
                    elif not bool(classification.get("is_actual_development")):
                        stats["rejected_non_developments"] += 1
                    if bool(recency.get("is_active_campaign")) and not bool(recency.get("is_recent")):
                        stats["active_old_campaigns"] += 1
                    if len(rejected_examples) < 10:
                        rejected_examples.append((item_title, candidate.url, reject_reason))
                    logging.info("Rejected candidate | %s | %s | %s", reject_reason, item_title[:100], candidate.url)
                    audit_rows.append(
                        build_audit_row(
                            run_id_value,
                            row,
                            item_title,
                            candidate.url,
                            date_meta,
                            recency,
                            classification,
                            quality,
                            False,
                            reject_reason,
                        )
                    )
                    should_continue = False
                    if quality not in {"Good", "Medium"} and not args.save_poor:
                        should_continue = True
                    if not bool(recency.get("is_recent")) and not args.save_non_recent:
                        should_continue = True
                    if not bool(classification.get("is_actual_development")) and not args.save_non_developments:
                        should_continue = True
                    if should_continue:
                        continue

                item_row = build_item_row(row, item_title, candidate.url, item_text, item_date, method, quality, date_meta, recency, classification)
                duplicate, duplicate_reason, duplicate_of = find_duplicate(
                    dedupe_index,
                    item_row["institution_name"],
                    item_row["canonical_item_url"],
                    item_row["content_fingerprint"],
                    item_row["normalized_title"],
                    item_row["recency_basis_date"],
                )
                if duplicate:
                    stats["duplicates"] += 1
                    if len(rejected_examples) < 10:
                        rejected_examples.append((item_title, candidate.url, duplicate_reason))
                    logging.info("Duplicate candidate | %s | duplicate_of=%s | %s", duplicate_reason, duplicate_of, item_title[:100])
                    audit_rows.append(
                        build_audit_row(
                            run_id_value,
                            row,
                            item_title,
                            candidate.url,
                            date_meta,
                            recency,
                            classification,
                            quality,
                            False,
                            duplicate_reason,
                            duplicate_of,
                        )
                    )
                    continue
                new_rows.append(item_row)
                add_to_duplicate_index(dedupe_index, item_row)
                stats["created"] += 1
                event_type = date_meta.get("event_date_type", "")
                if event_type == "Yayın Tarihi":
                    stats["saved_by_publication_date"] += 1
                elif event_type == "Duyuru Tarihi":
                    stats["saved_by_announcement_date"] += 1
                elif event_type == "Kampanya Başlangıç Tarihi":
                    stats["saved_by_campaign_start_date"] += 1
                elif event_type == "Kampanya Bitiş Tarihi" and allow_end_date_recency:
                    stats["passed_by_end_date_manual_override"] += 1
                if len(saved_examples) < 10:
                    saved_examples.append((item_title, date_meta.get("normalized_date", ""), candidate.url))
                audit_rows.append(
                    build_audit_row(
                        run_id_value,
                        row,
                        item_title,
                        candidate.url,
                        date_meta,
                        recency,
                        classification,
                        quality,
                        True,
                        "",
                    )
                )
                logging.info("Extracted item %s | %s | %s", item_row["recent_item_id"], quality, item_title)
        except Exception as exc:
            stats["errors"] += 1
            logging.warning("Error processing %s: %s", row.get("document_id"), exc)

    if args.dry_run:
        logging.info("Dry run: %s items would be written", len(new_rows))
    else:
        if args.force:
            processed_sources = set(documents["source_id"].dropna().astype(str))
            existing = existing[~existing["source_id"].astype(str).isin(processed_sources)]
        updated = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
        updated = updated.reindex(columns=RECENT_ITEM_COLUMNS)
        updated.to_csv(RECENT_ITEMS_PATH, index=False, encoding="utf-8-sig")
    if audit_rows:
        audit = read_audit()
        updated_audit = pd.concat([audit, pd.DataFrame(audit_rows)], ignore_index=True).reindex(columns=AUDIT_COLUMNS)
        updated_audit.to_csv(AUDIT_PATH, index=False, encoding="utf-8-sig")

    logging.info("Total links found: %s", stats["total_links"])
    logging.info("Candidate links found: %s", stats["candidate_links"])
    logging.info("Detail pages fetched: %s", stats["detail_pages_fetched"])
    logging.info("Recent items created: %s", stats["created"])
    logging.info("Saved recent developments: %s", stats["created"])
    logging.info("Rejected old items: %s", stats["rejected_old"])
    logging.info("Rejected undated items: %s", stats["rejected_undated"])
    logging.info("Rejected low-confidence dates: %s", stats["rejected_low_confidence"])
    logging.info("Rejected non-developments: %s", stats["rejected_non_developments"])
    logging.info("Saved by publication_date: %s", stats["saved_by_publication_date"])
    logging.info("Saved by announcement_date: %s", stats["saved_by_announcement_date"])
    logging.info("Saved by campaign_start_date: %s", stats["saved_by_campaign_start_date"])
    logging.info("Rejected because only campaign_end_date existed: %s", stats["rejected_only_campaign_end_date"])
    logging.info("passed_by_publication_date_count: %s", stats["saved_by_publication_date"])
    logging.info("passed_by_announcement_date_count: %s", stats["saved_by_announcement_date"])
    logging.info("passed_by_campaign_start_date_count: %s", stats["saved_by_campaign_start_date"])
    logging.info("passed_by_end_date_manual_override_count: %s", stats["passed_by_end_date_manual_override"])
    logging.info("rejected_only_campaign_end_date_count: %s", stats["rejected_only_campaign_end_date"])
    logging.info("Active old campaigns detected: %s", stats["active_old_campaigns"])
    logging.info("Content role Bağımsız Gelişme: %s", stats["content_role_bagimsiz"])
    logging.info("Content role Bağlamsal Veri: %s", stats["content_role_context_only"])
    logging.info("Content role Yönetici Bilgilendirme: %s", stats["content_role_awareness"])
    logging.info("Content role Kapsam Dışı/Benchmark: %s", stats["content_role_scope_out"])
    logging.info("Poor items skipped: %s", stats["poor"])
    logging.info("Duplicates skipped: %s", stats["duplicates"])
    logging.info("Errors: %s", stats["errors"])
    if saved_examples:
        logging.info("First saved items: %s", " | ".join(f"{title} [{date}] {url}" for title, date, url in saved_examples[:10]))
    if rejected_examples:
        logging.info("First rejected items: %s", " | ".join(f"{title} :: {reason} :: {url}" for title, url, reason in rejected_examples[:10]))


if __name__ == "__main__":
    main()
