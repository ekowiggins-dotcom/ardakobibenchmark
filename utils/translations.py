from __future__ import annotations

import math
import re
from collections.abc import Iterable

import pandas as pd


CANONICAL_TRANSLATIONS = {
    # Institution and source names
    "Is Bankasi": "İş Bankası",
    "Is Bankasi Is Ticari": "İş Bankası İş Ticari",
    "Is Bankasi Sanal POS": "İş Bankası Sanal POS",
    "Turkiye Is Bankasi": "Türkiye İş Bankası",
    "Yapi Kredi": "Yapı Kredi",
    "Garanti BBVA Isim Icin": "Garanti BBVA İşim İçin",
    "Garanti BBVA Isim Icin / SME banking": "Garanti BBVA İşim İçin / KOBİ bankacılığı",
    "Kuveyt Turk": "Kuveyt Türk",
    "QNB Finansbank SME page": "QNB Finansbank KOBİ Sayfası",
    "SME banking": "KOBİ bankacılığı",
    "SME page": "KOBİ sayfası",
    "Business API": "İşletme API",
    # Page / UI labels
    "SME Benchmark Intelligence Platform": "KOBİ Rekabet Gelişmeleri Radarı",
    "Executive Overview": "Yönetici Özeti",
    "Deposit Benchmark": "Mevduat Benchmark’ı",
    "Embedded Finance Benchmark": "Gömülü Finans Benchmark’ı",
    "Payments POS Benchmark": "Ödemeler ve POS Benchmark’ı",
    "Payments & POS Benchmark": "Ödemeler ve POS Benchmark’ı",
    "Compare Institutions": "Kurum Karşılaştırma",
    "Battlecards": "Rakip Kartları",
    "Source Tracker": "Kaynak Takibi",
    "Weekly Developments Radar": "Haftalık Gelişmeler Radarı",
    "Review Queue": "Analist Onay Kuyruğu",
    "Benchmark Fact Review": "Benchmark Bulguları Onay Kuyruğu",
    "Overview": "Özet",
    "Dashboard": "Panel",
    "Filters": "Filtreler",
    "Institution": "Kurum",
    "Product Area": "Ürün Alanı",
    "Benchmark Dimension": "Benchmark Boyutu",
    "Source": "Kaynak",
    "Open Source": "Kaynağı Aç",
    "Review": "İncele",
    "Save": "Kaydet",
    "Strategic Relevance": "Stratejik Önem",
    # Product areas / themes
    "SME Deposits": "KOBİ Mevduat",
    "Deposit Products": "Mevduat Ürünleri",
    "Payments & POS": "Ödemeler ve POS",
    "Payments POS": "Ödemeler ve POS",
    "Embedded Finance": "Gömülü Finans",
    "Digital SME Journey": "Dijital KOBİ Yolculuğu",
    "SME Lending": "KOBİ Kredileri",
    "Cash Management": "Nakit Yönetimi",
    "Ecosystem Partnerships": "Ekosistem İş Birlikleri",
    "Pricing Transparency": "Fiyatlama Şeffaflığı",
    "Campaigns": "Kampanyalar",
    "Regulation": "Regülasyon",
    "Global Best Practice": "Global İyi Uygulama",
    "Corporate Positioning": "Kurumsal Konumlandırma",
    "Corporate Reputation": "Kurumsal Konumlandırma",
    "Other": "Diğer",
    # Benchmark dimensions
    "SME Deposit Proposition": "KOBİ Mevduat Önermesi",
    "Embedded Finance Maturity": "Gömülü Finans Olgunluğu",
    "Payments & Merchant Acquiring": "Ödemeler ve Üye İşyeri Edinimi",
    "Cash Management": "Nakit Yönetimi",
    "SME Lending Linkage": "KOBİ Kredi Bağlantısı",
    "BD Relevance": "BD Kullanılabilirliği",
    "Strategic Threat Level": "Stratejik Tehdit Seviyesi",
    # Fact types
    "Product Feature": "Ürün Özelliği",
    "Product Requirement": "Ürün Gereksinimi",
    "Pricing / Fee Signal": "Fiyat / Ücret Sinyali",
    "Channel Availability": "Kanal Erişilebilirliği",
    "Digital Capability": "Dijital Yetkinlik",
    "Card Scheme / Network Support": "Kart Şeması / Ağ Desteği",
    "Settlement / Reconciliation": "Mutabakat / Raporlama",
    "Campaign Benefit": "Kampanya Avantajı",
    "Partnership": "İş Birliği",
    "API / Developer Capability": "API / Geliştirici Yetkinliği",
    "Open Question": "Açık Soru",
    # Source types
    "Official SME Page": "Resmi KOBİ Sayfası",
    "Official POS Page": "Resmi POS Sayfası",
    "Official Campaign Page": "Resmi Kampanya Sayfası",
    "Official Pricing Page": "Resmi Fiyat/Ücret Sayfası",
    "Official Press Release Page": "Resmi Basın Bülteni Sayfası",
    "Official Developer/API Docs": "Resmi Geliştirici/API Dokümanı",
    "Official Product Page": "Resmi Ürün Sayfası",
    "Investor Relations": "Yatırımcı İlişkileri",
    "Industry Association": "Sektör Birliği",
    "Regulator": "Regülatör",
    "News Site": "Haber Sitesi",
    "Fintech News": "Fintech Haberi",
    "Business News": "İş/Ekonomi Haberi",
    # Status / confidence / action
    "Pending": "Beklemede",
    "Approved": "Onaylandı",
    "Rejected": "Reddedildi",
    "Needs More Research": "Ek Araştırma Gerekli",
    "High": "Yüksek",
    "Medium": "Orta",
    "Low": "Düşük",
    "Monitor": "İzle",
    "Respond": "Yanıt Geliştir",
    "Explore Partnership": "İş Birliği Fırsatını İncele",
    "Copy / Adapt": "Uyarlama Fırsatını Değerlendir",
    "Ignore": "Önceliklendirme",
    "Escalate to Leadership": "Yönetime Eskale Et",
    "Add to BD Talking Points": "BD Konuşma Notlarına Ekle",
    "Add to Executive Briefing": "Yönetici Bilgilendirme Notuna Ekle",
    "Add to Management Briefing": "Yönetici Bilgilendirme Notuna Ekle",
    # Institution types
    "Turkish Bank": "Türk Bankası",
    "Public Bank": "Kamu Bankası",
    "Participation Bank": "Katılım Bankası",
    "Payment Institution": "Ödeme Kuruluşu",
    "Card Scheme": "Kart Şeması",
    "Global Fintech": "Global Fintek",
    "Global Bank": "Global Banka",
    "Turkey": "Türkiye",
    "United States": "ABD",
    "United Kingdom": "Birleşik Krallık",
    "Netherlands": "Hollanda",
    "Canada": "Kanada",
    "Europe": "Avrupa",
    "Private": "Özel",
    "Public": "Halka Açık",
    "Public Company": "Halka Açık Şirket",
    "Corporate": "Kurumsal",
    "Domestic Scheme": "Yerli Şema",
    "Available": "Sunuluyor",
    "Partner-led": "İş ortağı üzerinden",
    "Partial": "Kısmi",
    "Yes": "Evet",
    "Advanced": "İleri",
    "Developing": "Gelişmekte",
    "Emerging": "Yeni Gelişen",
    "Very High": "Çok Yüksek",
    "Very Medium": "Çok Orta",
    "Very Low": "Çok Düşük",
    "Physical POS": "Fiziki POS",
    "Virtual POS": "Sanal POS",
    "API payments": "API ödemeleri",
    "QR payments": "QR ödemeleri",
    "Mobile POS": "Mobil POS",
    "E-commerce acquiring": "E-ticaret üye işyeri edinimi",
    "Omnichannel acquiring": "Çok kanallı üye işyeri edinimi",
    "SoftPOS and POS": "SoftPOS ve POS",
    "Digital application": "Dijital başvuru",
    "Digital SME hub": "Dijital KOBİ merkezi",
    "POS application": "POS başvurusu",
    "Platform onboarding": "Platform onboarding",
    "API and hosted onboarding": "API ve barındırılan onboarding",
    "App-first onboarding": "Uygulama öncelikli onboarding",
    "Embedded activation": "Gömülü aktivasyon",
    "Branch and digital": "Şube ve dijital",
    "Internet and mobile banking": "İnternet ve mobil bankacılık",
    "Digital banking": "Dijital bankacılık",
    "Platform Panel": "Platform paneli",
}


PHRASE_TRANSLATIONS = {
    "Payments and POS capabilities are relevant to merchant acquisition, daily SME relationship depth, and payment-flow based deposit opportunities.": (
        "Ödemeler ve POS yetkinlikleri, üye işyeri kazanımı, günlük KOBİ ilişkisinin derinleşmesi "
        "ve ödeme akışına dayalı mevduat fırsatları açısından önemlidir."
    ),
    "Digital SME journey capabilities are relevant to reducing onboarding friction and increasing self-service adoption.": (
        "Dijital KOBİ yolculuğu yetkinlikleri, başvuru/aktivasyon sürtünmesini azaltma ve self-servis "
        "kullanımını artırma açısından önemlidir."
    ),
    "Digital application and servicing capabilities reduce SME onboarding friction and support BD scale.": (
        "Dijital başvuru ve servis yetkinlikleri, KOBİ edinim sürtünmesini azaltır ve BD ölçeklenmesini destekler."
    ),
    "SME lending capabilities are relevant to cross-sell, working capital needs, and relationship depth.": (
        "KOBİ kredi yetkinlikleri, çapraz satış, işletme sermayesi ihtiyacı ve müşteri ilişkisinin derinleşmesi açısından önemlidir."
    ),
    "SME credit signals help benchmark how competitors connect lending with daily banking and BD needs.": (
        "KOBİ kredi sinyalleri, rakiplerin krediyi günlük bankacılık ve BD ihtiyaçlarıyla nasıl bağladığını gösterir."
    ),
    "Deposit and account features affect SME operating balance capture and relationship primacy.": (
        "Mevduat ve hesap özellikleri, KOBİ işletme bakiyesi kazanımı ve ana banka olma hedefi açısından önemlidir."
    ),
    "Verify pricing, settlement timing, and reconciliation details manually.": (
        "Fiyatlama, valör/tahsilat süresi ve mutabakat detaylarını manuel kontrol et."
    ),
    "Check whether the journey is fully digital or requires branch completion.": (
        "Yolculuğun tamamen dijital mi yoksa şube tamamlaması gerektirip gerektirmediğini kontrol et."
    ),
    "Confirm eligibility and whether the offer is campaign-specific.": (
        "Uygunluk koşullarını ve teklifin kampanyaya özel olup olmadığını doğrula."
    ),
}


NORMALIZED_TRANSLATIONS = {k.casefold().strip(): v for k, v in CANONICAL_TRANSLATIONS.items()}
LABELS = {
    "strategic_theme": CANONICAL_TRANSLATIONS,
    "impact_on_us": CANONICAL_TRANSLATIONS,
    "recommended_action": CANONICAL_TRANSLATIONS,
    "review_status": CANONICAL_TRANSLATIONS,
    "confidence_level": CANONICAL_TRANSLATIONS,
    "importance_level": CANONICAL_TRANSLATIONS,
    "institution_type": CANONICAL_TRANSLATIONS,
}

REPAIR_TRANSLATIONS = {
    "fDüşüks": "akışları",
    "fDüşük": "akışı",
    "workfDüşüks": "iş akışları",
    "workfDüşük": "iş akışı",
    "cash-fDüşük": "nakit akışı",
    "Düşüker": "daha düşük",
    "Yüksekly": "yüksek ölçüde",
    "Yükseklights": "öne çıkarıyor",
    "Yüksekest": "en yüksek",
    "Yüksek-priority": "yüksek öncelikli",
    "Very Yüksek": "Çok Yüksek",
    "Very Orta": "Çok Orta",
    "Very Düşük": "Çok Düşük",
    "İş Birliğis": "iş birlikleri",
    "Kamu Bankasıing": "kamu bankacılığı",
}


def _is_missing(value) -> bool:
    try:
        return value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value)
    except Exception:
        return False


def _translate_string(value: str) -> str:
    text = " ".join(str(value).strip().split())
    if not text:
        return ""
    for old, new in REPAIR_TRANSLATIONS.items():
        text = text.replace(old, new)
    exact = NORMALIZED_TRANSLATIONS.get(text.casefold())
    if exact:
        return exact
    for old, new in PHRASE_TRANSLATIONS.items():
        text = text.replace(old, new)
    # Long source names can contain mapped fragments; short status words must only
    # match as full tokens so words like "flows" do not become "fDüşüks".
    for old, new in sorted(CANONICAL_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        escaped = re.escape(old)
        if re.fullmatch(r"[\w /&.-]+", old):
            pattern = rf"(?<!\w){escaped}(?!\w)"
        else:
            pattern = escaped
        text = re.sub(pattern, new, text, flags=re.IGNORECASE)
    return text


def to_tr(value):
    if _is_missing(value):
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if ";" in stripped:
            return "; ".join(to_tr(part) for part in stripped.split(";") if part.strip())
        if "," in stripped and len(stripped) < 200:
            return ", ".join(to_tr(part) for part in stripped.split(",") if part.strip())
        return _translate_string(stripped)
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, dict)):
        return [to_tr(item) for item in value]
    return value


def tr_label(category: str, value):
    return to_tr(value)


def tr_columns(df: pd.DataFrame, column_mapping: dict[str, str]) -> pd.DataFrame:
    out = df.rename(columns=column_mapping).copy()
    for column in out.columns:
        if pd.api.types.is_object_dtype(out[column]):
            out[column] = out[column].map(to_tr)
    return out


def format_turkish_date(date_value) -> str:
    if _is_missing(date_value):
        return ""
    value = pd.to_datetime(date_value, errors="coerce")
    if pd.isna(value):
        return str(date_value)
    return value.strftime("%d.%m.%Y")


def add_display_columns(df: pd.DataFrame, columns: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column in out.columns:
            out[f"{column}_tr"] = out[column].apply(to_tr)
    return out
