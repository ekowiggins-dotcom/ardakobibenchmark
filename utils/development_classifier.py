from __future__ import annotations

import re
from urllib.parse import urlparse


STATIC_RE = re.compile(
    r"(login|giriş|sube|şube|atm|yardim|yardım|iletisim|iletişim|hesaplama|hesapla|"
    r"urun-ve-hizmet-ucretleri|ürün-ve-hizmet-ücretleri|kvkk|gizlilik|cerez|çerez|"
    r"site-haritasi|site haritası|parola|başvuru merkezi|basvuru merkezi)",
    re.IGNORECASE,
)
STATIC_PRODUCT_PATH_RE = re.compile(
    r"/(?:bireysel-bankacilik|kobi|ticari|kurumsal)/(?:odemeler-ve-hizmetler|mevduat|krediler|kartlar|yatirim|sigorta|dijital-bankacilik)(?:/|$)",
    re.IGNORECASE,
)
CAMPAIGN_RE = re.compile(r"(kampanya|fırsat|avantaj|puan|hoş geldin|maxipuan|promosyon)", re.IGNORECASE)
PARTNERSHIP_RE = re.compile(r"(iş birliği|is birligi|partner|ortaklık|mutabakat|anlaşma|entegrasyon)", re.IGNORECASE)
PRODUCT_RE = re.compile(r"(lansman|yeni ürün|yeni hizmet|özellik|api|open banking|açık bankacılık|ödeme iste|tahsilat|pos|softpos|sanal pos|fast|nakit yönetimi)", re.IGNORECASE)
REGULATION_RE = re.compile(r"(regülasyon|yönetmelik|karar|tebliğ|tcmb|bddk|bkm|resmi gazete)", re.IGNORECASE)
REPORT_RE = re.compile(r"(rapor|araştırma|endeks|barometre|pazar araştırması)", re.IGNORECASE)
AWARD_RE = re.compile(r"(ödül|ödülleri|ranking|sıralama|en iyi|global finance|başarı)", re.IGNORECASE)
SUSTAINABILITY_FINANCE_RE = re.compile(r"(sürdürülebilir.*(finans|kredi|leasing|tahvil|swap)|yeşil.*(kredi|finans|tahvil))", re.IGNORECASE)
CSR_RE = re.compile(r"(kültür|sanat|sergi|sponsorluk|öğrenci|eğitim desteği|sosyal sorumluluk|konser|festival)", re.IGNORECASE)
SME_RE = re.compile(r"(kobi|kobİ|esnaf|ticari|işletme|üye işyeri|uye isyeri|merchant|firma|kurumsal müşteri)", re.IGNORECASE)


def classify_actual_development(item_title: str, item_text: str, item_url: str, source_type: str) -> dict[str, object]:
    title = str(item_title or "")
    text = str(item_text or "")
    url = str(item_url or "")
    source = str(source_type or "")
    blob = f"{title}\n{text[:5000]}\n{url}\n{source}"
    metadata_blob = f"{title}\n{url}\n{source}"
    path = urlparse(url).path
    is_press_context = "/kurumsal-iletisim/" in path or "basın" in source.casefold() or "press" in source.casefold()

    if (STATIC_RE.search(metadata_blob) and not is_press_context) or (
        STATIC_PRODUCT_PATH_RE.search(path) and not CAMPAIGN_RE.search(blob) and not PRODUCT_RE.search(blob)
    ):
        return {
            "is_actual_development": False,
            "development_candidate_type": "Statik Ürün Sayfası",
            "actual_development_reason": "Statik ürün, yardım, giriş veya navigasyon içeriği gibi görünüyor.",
        }

    if CSR_RE.search(blob) and not SME_RE.search(blob) and not (AWARD_RE.search(blob) or REPORT_RE.search(blob) or SUSTAINABILITY_FINANCE_RE.search(blob)):
        return {
            "is_actual_development": False,
            "development_candidate_type": "Sosyal Sorumluluk / PR",
            "actual_development_reason": "KOBİ stratejisine doğrudan bağlanmayan kültür, sanat veya sosyal sorumluluk PR içeriği.",
        }

    if CAMPAIGN_RE.search(blob):
        return {
            "is_actual_development": True,
            "development_candidate_type": "Kampanya",
            "actual_development_reason": "Kampanya veya müşteri teklifi sinyali içeriyor.",
        }
    if PARTNERSHIP_RE.search(blob):
        return {
            "is_actual_development": True,
            "development_candidate_type": "İş Birliği",
            "actual_development_reason": "İş birliği, mutabakat veya entegrasyon duyurusu içeriyor.",
        }
    if PRODUCT_RE.search(blob):
        return {
            "is_actual_development": True,
            "development_candidate_type": "Ürün / Özellik Gelişmesi",
            "actual_development_reason": "Ürün, API, POS, ödeme, tahsilat veya dijital özellik gelişmesi sinyali içeriyor.",
        }
    if REGULATION_RE.search(blob):
        return {
            "is_actual_development": True,
            "development_candidate_type": "Regülasyon",
            "actual_development_reason": "Regülasyon veya resmi karar sinyali içeriyor.",
        }
    if SUSTAINABILITY_FINANCE_RE.search(blob):
        return {
            "is_actual_development": True,
            "development_candidate_type": "Ürün / Özellik Gelişmesi",
            "actual_development_reason": "Sürdürülebilir finansman, kredi, leasing veya sermaye piyasası işlemi içeriyor.",
        }
    if REPORT_RE.search(blob):
        return {
            "is_actual_development": True,
            "development_candidate_type": "Rapor / Araştırma",
            "actual_development_reason": "Bankacılık veya pazar araştırması niteliğinde rapor/analiz sinyali içeriyor.",
        }
    if AWARD_RE.search(blob):
        return {
            "is_actual_development": True,
            "development_candidate_type": "Ödül / İtibar Sinyali",
            "actual_development_reason": "Dated, credible award/ranking or management-positioning signal olarak değerlendirilebilir.",
        }
    if "basın" in source.casefold() or "press" in source.casefold() or "haber" in source.casefold():
        return {
            "is_actual_development": True,
            "development_candidate_type": "Basın Bülteni",
            "actual_development_reason": "Basın/haber kaynağından gelen tekil ve tarihli duyuru adayı.",
        }
    if "duyuru" in blob.casefold() or "haber" in blob.casefold():
        return {
            "is_actual_development": True,
            "development_candidate_type": "Haber",
            "actual_development_reason": "Tekil haber veya duyuru adayı.",
        }

    return {
        "is_actual_development": False,
        "development_candidate_type": "Belirsiz",
        "actual_development_reason": "Yeni kampanya, ürün, iş birliği, regülasyon, rapor veya yönetim sinyali net değil.",
    }
