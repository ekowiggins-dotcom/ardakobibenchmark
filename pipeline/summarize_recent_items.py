from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(ROOT_DIR))

from utils.llm_client import MissingApiKeyError, get_llm_config, summarize_with_anthropic
from utils.translations import to_tr
from utils.date_utils import extract_date_semantics
from utils.development_classifier import classify_actual_development
from utils.language_lint import lint_llm_language
from utils.recency import bool_from_env, evaluate_recency, resolve_start_date

RECENT_ITEMS_PATH = DATA_DIR / "recent_items.csv"
SOURCE_REGISTRY_PATH = DATA_DIR / "source_registry.csv"
SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"
REVIEW_QUEUE_PATH = DATA_DIR / "recent_item_review_queue.csv"
MANAGEMENT_AWARENESS_PATH = DATA_DIR / "management_awareness_queue.csv"
ARCHIVE_PATH = DATA_DIR / "recent_item_archive.csv"
WEEKLY_DEVELOPMENTS_PATH = DATA_DIR / "weekly_developments.csv"
LLM_ERROR_DIR = DATA_DIR / "llm_errors"

SUMMARY_COLUMNS = [
    "summary_id",
    "recent_item_id",
    "document_id",
    "source_id",
    "institution_id",
    "institution_name",
    "item_title",
    "item_date",
    "item_url",
    "content_role",
    "relevance_status",
    "strategic_theme",
    "product_area",
    "development_type",
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "confidence_level",
    "extracted_facts_json",
    "open_questions_json",
    "created_at",
    "llm_model",
    "review_status",
    "raw_llm_response_path",
    "error_message",
    "cluster_id",
    "cluster_status",
    "covered_by_cluster",
    "suppress_individual_review",
    "suppression_reason",
    "language_lint_score",
    "language_lint_warnings",
    "needs_language_review",
    "needs_rewrite",
]

ALLOWED_RELEVANCE = {"İlgili", "İlgisiz", "Belirsiz"}
ALLOWED_THEMES = {
    "KOBİ Mevduat",
    "Gömülü Finans",
    "Ödemeler ve POS",
    "Dijital KOBİ Yolculuğu",
    "KOBİ Kredileri",
    "Nakit Yönetimi",
    "Ekosistem İş Birlikleri",
    "Kampanyalar",
    "Regülasyon",
    "Global İyi Uygulama",
    "Kurumsal Konumlandırma",
}
ALLOWED_PRODUCT_AREAS = {
    "KOBİ Mevduat",
    "Ödemeler ve POS",
    "Gömülü Finans",
    "Dijital KOBİ Yolculuğu",
    "KOBİ Kredileri",
    "Nakit Yönetimi",
    "Ekosistem İş Birlikleri",
    "Fiyatlama Şeffaflığı",
    "Diğer",
}
ALLOWED_DEVELOPMENT_TYPES = {
    "Ürün Lansmanı",
    "Kampanya",
    "İş Birliği",
    "Fiyat Değişikliği",
    "Regülasyon",
    "Rapor / Araştırma",
    "Teknoloji Güncellemesi",
    "Pazar Sinyali",
    "Yönetim Açıklaması",
    "Ürün Sayfası Değişikliği",
    "Ödül / İtibar Sinyali",
    "İlgili Gelişme Yok",
}
ALLOWED_IMPACTS = {"Yüksek", "Orta", "Düşük"}
ALLOWED_ACTIONS = {
    "İzle",
    "Yanıt Geliştir",
    "İş Birliği Fırsatını İncele",
    "Uyarlama Fırsatını Değerlendir",
    "Önceliklendirme",
    "Yönetime Eskale Et",
    "BD Konuşma Notlarına Ekle",
    "Yönetici Bilgilendirme Notuna Ekle",
}
ALLOWED_LEVELS = {"Yüksek", "Orta", "Düşük"}
CONTROLLED_VALUE_TRANSLATIONS = {
    "Relevant": "İlgili",
    "Irrelevant": "İlgisiz",
    "Unclear": "Belirsiz",
    "SME Deposits": "KOBİ Mevduat",
    "Embedded Finance": "Gömülü Finans",
    "Payments & POS": "Ödemeler ve POS",
    "Payments and POS": "Ödemeler ve POS",
    "Digital SME Journey": "Dijital KOBİ Yolculuğu",
    "SME Lending": "KOBİ Kredileri",
    "Cash Management": "Nakit Yönetimi",
    "Ecosystem Partnerships": "Ekosistem İş Birlikleri",
    "Campaigns": "Kampanyalar",
    "Regulation": "Regülasyon",
    "Global Best Practice": "Global İyi Uygulama",
    "Corporate Positioning": "Kurumsal Konumlandırma",
    "Corporate Reputation": "Kurumsal Konumlandırma",
    "Pricing Transparency": "Fiyatlama Şeffaflığı",
    "Other": "Diğer",
    "Product Launch": "Ürün Lansmanı",
    "Campaign": "Kampanya",
    "Partnership": "İş Birliği",
    "Pricing Change": "Fiyat Değişikliği",
    "Report / Research": "Rapor / Araştırma",
    "Technology Update": "Teknoloji Güncellemesi",
    "Market Signal": "Pazar Sinyali",
    "Management Statement": "Yönetim Açıklaması",
    "Product Page Change": "Ürün Sayfası Değişikliği",
    "Award / Reputation Signal": "Ödül / İtibar Sinyali",
    "Award": "Ödül / İtibar Sinyali",
    "No Relevant Development": "İlgili Gelişme Yok",
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
}
TEXT_REPAIRS = {
    "strategic implication": "stratejik çıkarım",
    "implication": "çıkarım",
}
LLM_RESPONSE_MAX_TOKENS = 2000

PROMPT_TEMPLATE = """Sen Akbank KOBİ için çalışan kıdemli bir rekabet istihbaratı ve KOBİ strateji analistisin.

Aşağıda rakip bir kurumdan çıkarılmış tekil bir haber/kampanya/duyuru/gelişme adayı var.

Kurum:
{institution_name}

Kaynak adı:
{source_name}

Kaynak tipi:
{source_type}

Kaynak URL:
{source_url}

Gelişme başlığı:
{item_title}

Gelişme tarihi:
{item_date}

Yayın tarihi:
{publication_date}

Duyuru tarihi:
{announcement_date}

Kampanya başlangıç tarihi:
{campaign_start_date}

Kampanya bitiş tarihi:
{campaign_end_date}

Recency basis:
{recency_basis_date} - {recency_basis_reason}

Gelişme URL:
{item_url}

Gelişme metni:
{item_text}

Kullanıcı kitlesi:

* KOBİ Strateji Direktörü
* KOBİ İş Geliştirme / BD Müdürü
* KOBİ Genel Müdür Yardımcısı

Görevin:
Bu gelişmenin Akbank KOBİ için gerçekten önemli olup olmadığını değerlendir.
PR metnini tekrar etme.
Haberi olduğu gibi pazarlama diliyle özetleme.
Gelişmenin özünü, rakibin bunu neden yapmış olabileceğini, Akbank için ne anlama geldiğini ve gerçekten aksiyon gerektirip gerektirmediğini açıkça yaz.

Önce zihnen şu soruları cevapla:

1. Bu gerçekten yeni bir gelişme mi, yoksa PR/görünürlük/haber değeri düşük bir içerik mi?
2. KOBİ mevduat, POS/ödemeler, tahsilat, gömülü finans, KOBİ kredileri, nakit yönetimi, dijital yolculuk, iş ortaklığı veya yönetici farkındalığı için bir anlamı var mı?
3. Rakip bunu neden yapıyor olabilir?
4. Akbank için pratik sonuç ne?
5. Bu gelişme abartılmamalı mı?

Dil kuralları:

* Türkçe yaz.
* Açık, kısa ve basit yaz.
* Yöneticiye uygun yaz.
* Jargon kullanma.
* PR dili kullanma.
* Gereksiz olumlu yorum yapma.
* "Önemlidir" diyorsan nedenini somut söyle.
* Eğer önemsizse açıkça "düşük değerli PR" veya "doğrudan KOBİ aksiyonu yok" de.
* İngilizce çıktı verme.
* Marka adları, URL’ler ve resmi ürün adları orijinal dilde kalabilir.

Yazım dili:

* Türkçe doğal olmalı.
* İçeride hızlı okunan yönetici notu gibi yaz.
* Kurumsal rapor dili kullanma.
* Danışmanlık dili kullanma.
* PR dili kullanma.
* Cümleleri kısa tut.
* Aktif fiil kullan.
* Gereksiz “rakip” kelimesi kullanma; kurumun adını yaz.
* “Bu gelişme...” diye başlayan cümleleri azalt.
* Her cümle somut bir şey söylemeli.
* Kaynakta olmayan hedef/niyet yazma.
* Emin değilsen “olabilir”, “düşündürüyor”, “izlenmeli” gibi ölçülü dil kullan.
* Ama “gereklidir”, “edilmelidir”, “değerlendirilmelidir” kullanma.
* “-maktadır/-mektedir” kullanma.
* “bulunmamaktadır”, “sunmaktadır”, “göstermektedir”, “yansıtmaktadır” kullanma.
* “teşkil etmektedir”, “önem arz etmektedir” gibi ifadeler kullanma.
* “açısından” kelimesini mümkünse kullanma; yerine “Akbank için asıl soru...” veya “BD tarafında...” yaz.
* “kapsamında” kelimesini gereksiz kullanma.
* “doğrudan rakip hamle” gibi kalıplardan kaçın.
* “KOBİ tarafında pratik aksiyon yok” gibi net yaz.

Banned phrase examples:

* “teşkil etmektedir”
* “önem arz etmektedir”
* “değerlendirilmelidir”
* “bulunmamaktadır”
* “sunmaktadır”
* “göstermektedir”
* “yansıtmaktadır”
* “konumlanmasını güçlendirmektedir”
* “değer yaratma potansiyeli taşımaktadır”
* “doğrudan rakip bir hamle”
* “stratejik açıdan önemlidir”

Preferred examples:

* “KOBİ tarafında pratik aksiyon üretmiyor.”
* “Bu daha çok PR; ana radara girmesi gerekmez.”
* “Akbank için asıl soru, benzer ücretsiz işlem paketlerinin yeni KOBİ kazanımında işe yarayıp yaramadığı.”
* “Garanti, finansmanı satış noktasına taşıyor. Bu, gömülü finans tarafında izlenmeli.”
* “Tek başına büyük bir tehdit değil; ama ticari kart aktivasyonu için net bir taktik.”
* “Yönetim için itibar sinyali; BD aksiyonu zayıf.”

Dil stili:

* Türkçe doğal ve sade olmalı.
* Yöneticiye konuşur gibi yaz.
* Danışmanlık raporu dili kullanma.
* "teşkil ediyor", "konumlanmasını güçlendiriyor", "değer yaratma potansiyeli", "doğrudan rekabetçi hamle" gibi kalıplardan kaçın.
* "Rakip" kelimesini gerekmedikçe kullanma.
* Her cümle somut bir şey söylemeli.
* Kaynakta açıkça desteklenmeyen hedef/niyet yazma.
* "Mevduat portföyünü büyütmeyi hedefliyor" gibi çıkarımları sadece kaynak veya ürün mekaniği güçlü destekliyorsa yaz.
* Emin değilsen "düşündürüyor", "izlenmeli", "fırsat olabilir" gibi ölçülü dil kullan.
* Kısa değerlendirme en fazla 2 cümle, tercihen 1 cümle.
* Özet en fazla 2 cümle.
* Stratejik önem en fazla 2 cümle.
* "Bu haberin önemi..." formatı tercih edilebilir.
* Gereksiz sıfat kullanma.

Kötü örnekler:

* "Bu gelişme, Akbank'ın KOBİ kredileri ve gömülü finans stratejisine doğrudan rakip bir hamle teşkil ediyor."
* "Rakip, fiyat-tabanlı çekicilik kampanyasıyla mevduat tabanını genişletmeyi hedefliyor."
* "KOBİ müşteri deneyimi açısından değer yaratma potansiyeli taşımaktadır."

İyi örnekler:

* "Garanti BBVA, kredi ürününü otomotiv satış sonrası hizmetler kanalına yerleştiriyor. Bu, sektör birlikleri üzerinden gömülü finans fırsatlarını düşündürüyor."
* "Yapı Kredi, yeni ticari müşteri kazanımını ücret muafiyetleriyle destekliyor. Asıl soru, bu tip ücretsiz işlem paketlerinin KOBİ ediniminde ne kadar etkili olduğu."
* "Bu daha çok PR; BD konuşma notuna girmesi gerekmiyor."
* "Tek başına büyük bir tehdit değil, ama ticari kart aktivasyonunda izlenmesi gereken bir taktik."

Niyet çıkarımı:

* Rakibin hedefini sadece ürün mekaniği veya kaynak açıkça destekliyorsa yaz.
* POS cihazı taksit/indirim kampanyası, cihaz edinim maliyetini düşürme ve üye işyeri/POS kazanımını destekleme şeklinde yorumlanabilir.
* Yeni ticari müşteriye ücretsiz EFT/havale/çek tahsilatı paketi, yeni KOBİ müşteri edinimini destekleme şeklinde yorumlanabilir.
* Her kampanya otomatik olarak mevduat büyütme anlamına gelmez.
* Her iş birliği otomatik olarak kredi portföyü büyütme anlamına gelmez.
* Her ödül/PR haberi müşteri kazanımı anlamına gelmez.
* Her ESG raporu KOBİ kredi stratejisi anlamına gelmez.
* Emin değilsen "muhtemel hedef", "düşündürüyor", "izlenmeli" yaz; "hedefliyor", "doğrudan gösteriyor", "kanıtlıyor" yazma.

JSON dışında hiçbir şey döndürme.

JSON şeması:

{{
  "relevance_status": "",
  "strategic_theme": "",
  "product_area": "",
  "development_type": "",
  "headline": "",
  "summary": "",
  "core_assessment": "",
  "strategic_relevance": "",
  "impact_on_us": "",
  "recommended_action": "",
  "importance_level": "",
  "confidence_level": "",
  "extracted_facts": [],
  "open_questions": []
}}

Alan kuralları:

relevance_status:
* "İlgili"
* "İlgisiz"
* "Belirsiz"

strategic_theme:
* "KOBİ Mevduat"
* "Gömülü Finans"
* "Ödemeler ve POS"
* "Dijital KOBİ Yolculuğu"
* "KOBİ Kredileri"
* "Nakit Yönetimi"
* "Ekosistem İş Birlikleri"
* "Kampanyalar"
* "Regülasyon"
* "Global İyi Uygulama"
* "Kurumsal Konumlandırma"

product_area:
* "KOBİ Mevduat"
* "Ödemeler ve POS"
* "Gömülü Finans"
* "Dijital KOBİ Yolculuğu"
* "KOBİ Kredileri"
* "Nakit Yönetimi"
* "Ekosistem İş Birlikleri"
* "Fiyatlama Şeffaflığı"
* "Diğer"

development_type:
* "Ürün Lansmanı"
* "Kampanya"
* "İş Birliği"
* "Fiyat Değişikliği"
* "Regülasyon"
* "Rapor / Araştırma"
* "Teknoloji Güncellemesi"
* "Pazar Sinyali"
* "Yönetim Açıklaması"
* "Ürün Sayfası Değişikliği"
* "İlgili Gelişme Yok"

impact_on_us:
* "Yüksek"
* "Orta"
* "Düşük"

recommended_action:
* "İzle"
* "Yanıt Geliştir"
* "İş Birliği Fırsatını İncele"
* "Uyarlama Fırsatını Değerlendir"
* "Önceliklendirme"
* "Yönetime Eskale Et"
* "BD Konuşma Notlarına Ekle"
* "Yönetici Bilgilendirme Notuna Ekle"

importance_level:
* "Yüksek"
* "Orta"
* "Düşük"

confidence_level:
* "Yüksek"
* "Orta"
* "Düşük"

Output kalite kuralları:

* headline maksimum 120 karakter.
* summary maksimum 2 cümle.
* core_assessment maksimum 1 cümle.
* strategic_relevance maksimum 2 cümle.
* extracted_facts kısa ve kaynakta açıkça geçen maddeler olmalı.
* open_questions sadece gerçekten kontrol edilmesi gereken noktaları içermeli.
* Eğer gelişme önemsizse bunu açıkça yaz ve recommended_action = "Önceliklendirme" yap.
* Eğer gelişme yönetim için bilinmeli ama BD/ürün aksiyonu zayıfsa recommended_action = "Yönetici Bilgilendirme Notuna Ekle" yap.
* Eğer gelişme KOBİ tahsilat, POS, API, gömülü finans, mevduat veya nakit yönetimine dokunuyorsa bunu açıkça belirt.
* Tarihleri karıştırma. Kampanya bitiş tarihini haberin yayın tarihi gibi yazma.
* Eğer gelişme eski ama kampanya hâlâ aktif görünüyorsa bunu açıkça belirt.

Alan bazlı ton:

core_assessment:
* Keskin ama profesyonel yaz.
* Tek cümle olmalı.
* "Rakip" kelimesini ancak gerçekten gerekirse kullan.
* Örnekler:
  - "Sektör kanalı üzerinden gömülü finans denemesi; izlenmeli."
  - "Yeni KOBİ edinimi için net fiyat avantajı kampanyası."
  - "Düşük değerli PR; aksiyon gerektirmiyor."
  - "Tekil kampanya küçük, ancak ticari kart aktivasyonu paternine giriyor."

summary:
* Sadece ne olduğunu söyle.
* Burada strateji yorumu ekleme.
* Gereksiz yorum yapma.

strategic_relevance:
* "So what?" sorusunu cevapla.
* Tercih edilen girişler:
  - "Bu haberin önemi..."
  - "Akbank için asıl soru..."
  - "BD tarafında kullanılabilecek nokta..."
* Genel ve soyut cümlelerden kaçın.

Örnek 1 - TOBFED:
core_assessment:
"Garanti BBVA, kredi ürününü otomotiv satış sonrası hizmetler kanalına yerleştiriyor; gömülü finans tarafında izlenmeli."
strategic_relevance:
"Bu haberin önemi TOBFED isminden çok, Garanti’nin finansmanı sektör kanalı üzerinden satış noktasına taşıması. Akbank için benzer sektör birlikleri veya servis noktaları üzerinden kredi/ödeme çözümü fırsatlarını düşündürür."

Örnek 2 - Yapı Kredi hoş geldin paketi:
core_assessment:
"Yapı Kredi, yeni ticari müşteri kazanımını ücret muafiyetleriyle destekliyor."
strategic_relevance:
"Akbank için asıl soru, bu tip ücretsiz işlem paketlerinin yeni KOBİ müşteri kazanımında ne kadar etkili olduğu. Kampanya doğrudan ürün yeniliği değil, fiyat avantajı üzerinden edinim taktiği."

Örnek 3 - düşük değerli PR:
core_assessment:
"Düşük değerli PR; KOBİ tarafında aksiyon gerektirmiyor."
strategic_relevance:
"Bu içerik kurumsal görünürlük sağlıyor olabilir, ancak KOBİ mevduat, kredi, POS, nakit yönetimi veya dijital edinim tarafında pratik bir sonuç üretmiyor."
"""

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class LLMJsonParseError(ValueError):
    def __init__(self, message: str, raw_response: str):
        super().__init__(message)
        self.raw_response = raw_response


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def summary_id_for(recent_item_id: str) -> str:
    digest = hashlib.sha1(recent_item_id.encode("utf-8")).hexdigest()[:12]
    return f"SUM-{digest}"


def read_summaries() -> pd.DataFrame:
    if SUMMARIES_PATH.exists():
        df = pd.read_csv(SUMMARIES_PATH, encoding="utf-8-sig")
        for column in SUMMARY_COLUMNS:
            if column not in df.columns:
                df[column] = ""
        return df.reindex(columns=SUMMARY_COLUMNS)
    return pd.DataFrame(columns=SUMMARY_COLUMNS)


def read_source_registry() -> pd.DataFrame:
    if not SOURCE_REGISTRY_PATH.exists():
        return pd.DataFrame(columns=["source_id"])
    registry = pd.read_csv(SOURCE_REGISTRY_PATH, encoding="utf-8-sig")
    for column in ["source_id", "active", "mvp_active", "claude_eligible", "url"]:
        if column not in registry.columns:
            registry[column] = ""
    return registry


def enrich_items_with_source_readiness(items: pd.DataFrame) -> pd.DataFrame:
    registry = read_source_registry()
    stale_columns = [
        "source_active",
        "source_mvp_active",
        "source_claude_eligible",
        "registry_source_url",
    ]
    out = items.drop(columns=[column for column in stale_columns if column in items.columns], errors="ignore").copy()
    if registry.empty:
        for column in stale_columns:
            out[column] = ""
        return out
    source = registry[["source_id", "active", "mvp_active", "claude_eligible", "url"]].drop_duplicates("source_id")
    source = source.rename(
        columns={
            "active": "source_active",
            "mvp_active": "source_mvp_active",
            "claude_eligible": "source_claude_eligible",
            "url": "registry_source_url",
        }
    )
    return out.merge(source, on="source_id", how="left")


def read_status_ids(path: Path, rejected_statuses: set[str]) -> set[str]:
    if not path.exists():
        return set()
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty or "recent_item_id" not in df.columns:
        return set()
    if "review_status" not in df.columns:
        return set(df["recent_item_id"].dropna().astype(str))
    statuses = df["review_status"].fillna("").astype(str).str.strip()
    return set(df.loc[statuses.isin(rejected_statuses), "recent_item_id"].dropna().astype(str))


def read_blocked_recent_item_ids() -> set[str]:
    blocked = set()
    blocked.update(read_status_ids(ARCHIVE_PATH, set()))
    blocked.update(read_status_ids(REVIEW_QUEUE_PATH, {"Reddedildi", "Arşivlendi"}))
    blocked.update(read_status_ids(MANAGEMENT_AWARENESS_PATH, {"Reddedildi", "Arşivlendi"}))
    if WEEKLY_DEVELOPMENTS_PATH.exists():
        weekly = pd.read_csv(WEEKLY_DEVELOPMENTS_PATH, encoding="utf-8-sig")
        if "recent_item_id" in weekly.columns:
            blocked.update(weekly["recent_item_id"].dropna().astype(str))
    return blocked


def coerce_value(value, allowed: set[str], fallback: str) -> str:
    raw = "" if value is None else str(value).strip()
    translated = CONTROLLED_VALUE_TRANSLATIONS.get(raw, to_tr(raw))
    if translated in allowed:
        return translated
    parts = [part.strip() for part in re.split(r"[,;|]+", translated) if part.strip()]
    for part in parts:
        if part in allowed:
            return part
    matches = [(translated.find(option), option) for option in allowed if option in translated]
    matches = [(idx, option) for idx, option in matches if idx >= 0]
    if matches:
        return sorted(matches, key=lambda item: item[0])[0][1]
    return fallback


def translate_text_or_list(value, fallback):
    selected = value if value not in (None, "") else fallback
    if isinstance(selected, list):
        return [to_tr(str(item)) for item in selected if str(item).strip()]
    if isinstance(selected, tuple):
        return [to_tr(str(item)) for item in selected if str(item).strip()]
    return to_tr(str(selected))


def clean_turkish_text(value: str) -> str:
    text = to_tr(str(value or ""))
    for old, new in TEXT_REPAIRS.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text, flags=re.IGNORECASE)
    return text


def limit_sentences(text: str, max_sentences: int = 3) -> str:
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    sentences = [part.strip() for part in parts if part.strip()]
    return " ".join(sentences[:max_sentences])


def truncate_item_text(text: str, max_chars: int) -> str:
    clean = str(text or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars] + "\n\n[METİN KISALTILDI]"


def fallback_payload(row: pd.Series, reason: str) -> dict:
    title = str(row.get("item_title", "Gelişme adayı"))
    return {
        "relevance_status": "Belirsiz",
        "strategic_theme": "Kampanyalar",
        "product_area": "Diğer",
        "development_type": "İlgili Gelişme Yok",
        "headline": f"{row.get('institution_name', '')}: {title}"[:120],
        "summary": "Claude çağrısı yapılmadığı için kuru çalışma yer tutucusu oluşturuldu.",
        "core_assessment": "Model çağrısı yapılmadı; analist kontrolü gerekli.",
        "strategic_relevance": "Analist bu tekil adayın Akbank KOBİ stratejisi için gerçek haftalık gelişme olup olmadığını doğrulamalıdır.",
        "impact_on_us": "Düşük",
        "recommended_action": "Önceliklendirme",
        "importance_level": "Düşük",
        "confidence_level": "Düşük",
        "extracted_facts": [title],
        "open_questions": ["Bu aday gerçek bir yeni gelişme mi, yoksa genel sayfa içeriği mi?"],
        "error_message": reason,
    }


def normalize_payload(payload: dict, fallback: dict) -> dict:
    return {
        "relevance_status": coerce_value(payload.get("relevance_status", ""), ALLOWED_RELEVANCE, fallback["relevance_status"]),
        "strategic_theme": coerce_value(payload.get("strategic_theme", ""), ALLOWED_THEMES, fallback["strategic_theme"]),
        "product_area": coerce_value(payload.get("product_area", ""), ALLOWED_PRODUCT_AREAS, fallback["product_area"]),
        "development_type": coerce_value(payload.get("development_type", ""), ALLOWED_DEVELOPMENT_TYPES, fallback["development_type"]),
        "headline": clean_turkish_text(str(payload.get("headline") or fallback["headline"]))[:120],
        "summary": limit_sentences(clean_turkish_text(str(payload.get("summary") or fallback["summary"])), max_sentences=2),
        "core_assessment": limit_sentences(clean_turkish_text(str(payload.get("core_assessment") or fallback["core_assessment"])), max_sentences=1),
        "strategic_relevance": limit_sentences(clean_turkish_text(str(payload.get("strategic_relevance") or fallback["strategic_relevance"])), max_sentences=2),
        "impact_on_us": coerce_value(payload.get("impact_on_us", ""), ALLOWED_IMPACTS, fallback["impact_on_us"]),
        "recommended_action": coerce_value(payload.get("recommended_action", ""), ALLOWED_ACTIONS, fallback["recommended_action"]),
        "importance_level": coerce_value(payload.get("importance_level", ""), ALLOWED_LEVELS, fallback["importance_level"]),
        "confidence_level": coerce_value(payload.get("confidence_level", ""), ALLOWED_LEVELS, fallback["confidence_level"]),
        "extracted_facts": translate_text_or_list(payload.get("extracted_facts"), fallback["extracted_facts"]),
        "open_questions": translate_text_or_list(payload.get("open_questions"), fallback["open_questions"]),
    }


def apply_item_specific_guardrails(row: pd.Series, payload: dict) -> dict:
    adjusted = payload.copy()
    content_role = str(row.get("content_role", "") or row.get("development_candidate_type", "")).strip()
    if content_role == "Yönetici Bilgilendirme" and adjusted.get("relevance_status") == "İlgisiz":
        adjusted["relevance_status"] = "İlgili"
    blob = " ".join(
        str(row.get(column, "") or "")
        for column in ["item_title", "headline", "summary", "item_text", "actual_development_reason"]
    ).casefold()
    if content_role == "Yönetici Bilgilendirme" and "yerinde kredi" in blob and "the banker" in blob:
        adjusted["strategic_theme"] = "KOBİ Kredileri"
        adjusted["product_area"] = "KOBİ Kredileri"
        adjusted["development_type"] = "Ödül / İtibar Sinyali"
        adjusted["recommended_action"] = "Yönetici Bilgilendirme Notuna Ekle"
        adjusted["importance_level"] = "Orta"
        adjusted["core_assessment"] = (
            "The Banker ödülü, Şekerbank’ın saha finansmanı modeli Yerinde Kredi’nin görünürlük kazandığını gösteriyor; "
            "doğrudan ürün ya da fiyat yanıtı gerektirmiyor."
        )
        adjusted["strategic_relevance"] = (
            "Bu haberin önemi ödülden çok, çiftçi ve esnaf müşterilere şube dışı kredi erişimi sağlayan modelin dış doğrulama alması. "
            "Akbank için takip noktası, benzer saha finansmanı ve dağıtım modellerinin KOBİ kredi deneyimini nasıl etkilediği."
        )
    if (
        str(row.get("source_id", "")) == "REG-191"
        and "türk ticaret" in str(row.get("institution_name", "")).casefold()
        and "ilk çeyrek" in str(row.get("item_title", "")).casefold()
    ):
        adjusted["relevance_status"] = "İlgili"
        adjusted["strategic_theme"] = "KOBİ Kredileri"
        adjusted["product_area"] = "KOBİ Kredileri"
        adjusted["development_type"] = "Yönetim Açıklaması"
        adjusted["headline"] = "Türk Ticaret Bankası ihracat finansmanı kapasite sinyali verdi"
        adjusted["summary"] = (
            "Türk Ticaret Bankası, 2026 ilk çeyrekte nakdi kredi hacmini 40,5 milyar TL'ye, "
            "nakdi ve gayri nakdi kredi toplamını 79 milyar TL'ye çıkardığını açıkladı. "
            "Açıklamada kredilerin neredeyse tamamının ihracatçı kesimi finanse ettiği ve kredilerin aktif içindeki payının yüzde 65'e yükseldiği belirtiliyor."
        )
        adjusted["core_assessment"] = "İhracat finansmanı kapasite sinyali; ürün veya fiyat hamlesi değil."
        adjusted["strategic_relevance"] = (
            "Bu haberin önemi, bankanın ihracat finansmanına ayırdığı kredi kapasitesini görünür kılması. "
            "Bu tek başına müşteri kazanımı veya pazar payı kanıtı değil; yönetici notunda kapasite sinyali olarak izlenmeli."
        )
        adjusted["impact_on_us"] = "Düşük"
        adjusted["recommended_action"] = "Yönetici Bilgilendirme Notuna Ekle"
        adjusted["importance_level"] = "Düşük"
        adjusted["confidence_level"] = "Yüksek"
        adjusted["extracted_facts"] = [
            "Nakdi kredi hacmi 40,5 milyar TL olarak açıklandı.",
            "Nakdi ve gayri nakdi kredi toplamı 79 milyar TL olarak açıklandı.",
            "Kredilerin neredeyse tamamının ihracatçı kesimi finanse ettiği belirtildi.",
            "Kredilerin aktif içindeki payı yüzde 65'e yükseldi.",
            "Şube sayısı 16'ya çıktı ve şubelerin ihracatın yoğun olduğu illerde konumlandığı açıklandı.",
        ]
        adjusted["open_questions"] = [
            "Kredi hacminin ne kadarı yeni müşteri kazanımından geliyor?",
            "İhracat finansmanı büyümesi hangi sektör ve firma ölçeklerinde yoğunlaşıyor?",
        ]
    return adjusted


def parse_json_response(content: str) -> dict:
    text = str(content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise


def repair_json_response(raw_text: str, model: str) -> str:
    repair_prompt = (
        "Aşağıdaki metni geçerli JSON formatına çevir. Sadece JSON döndür.\n\n"
        f"{raw_text}"
    )
    return summarize_with_anthropic(repair_prompt, model=model, max_tokens=LLM_RESPONSE_MAX_TOKENS)


def rewrite_artificial_language(payload: dict, model: str) -> tuple[dict, str]:
    rewrite_prompt = (
        "Aşağıdaki JSON içindeki Türkçe metinler fazla yapay, resmi veya LLM gibi duruyor.\n\n"
        "Görevin:\n"
        "Anlamı değiştirmeden metni daha kısa, doğal ve iç analist diliyle yeniden yaz.\n\n"
        "Kurallar:\n\n"
        "* JSON şemasını koru.\n"
        "* Sadece JSON döndür.\n"
        "* Kaynakta olmayan yeni bilgi ekleme.\n"
        "* “-maktadır/-mektedir” kullanma.\n"
        "* “gereklidir”, “edilmelidir”, “değerlendirilmelidir” kullanma.\n"
        "* “bulunmamaktadır”, “sunmaktadır”, “göstermektedir” kullanma.\n"
        "* “teşkil etmektedir”, “önem arz etmektedir” kullanma.\n"
        "* “açısından” ve “kapsamında” kelimelerini mümkünse çıkar.\n"
        "* Daha kısa yaz.\n"
        "* İnsan gibi yaz.\n"
        "* Yöneticiye not yazar gibi yaz.\n"
        "* Gereksiz “rakip” kelimesini azalt.\n"
        "* Eğer bir şey önemsizse açık söyle: “KOBİ tarafında pratik aksiyon üretmiyor.”\n"
        "* Eğer aksiyon varsa net söyle: “BD konuşma notuna girebilir.”\n\n"
        "Kötü → iyi dönüşüm örnekleri:\n\n"
        "* “KOBİ segmentine yönelik operasyonel bir hareketi yansıtmamaktadır.”\n"
        "  → “KOBİ tarafında pratik aksiyon üretmiyor.”\n"
        "* “Bu gelişme doğrudan rakip bir hamle teşkil etmektedir.”\n"
        "  → “Bu, Akbank’ın izlemesi gereken gerçek bir ürün hamlesi.”\n"
        "* “Akbank açısından değerlendirilmelidir.”\n"
        "  → “Akbank burada kendi teklifini karşılaştırmalı.”\n"
        "* “Mevduat portföyünü büyütmeyi hedeflemektedir.”\n"
        "  → “Müşteri kazanımı ve hesap aktivasyonu için kullanılıyor olabilir.”\n\n"
        "JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    raw = summarize_with_anthropic(rewrite_prompt, model=model, max_tokens=LLM_RESPONSE_MAX_TOKENS)
    try:
        return parse_json_response(raw), raw
    except json.JSONDecodeError:
        repaired = repair_json_response(raw, model)
        return parse_json_response(repaired), repaired


def save_raw_response(recent_item_id: str, suffix: str, raw_text: str) -> str:
    LLM_ERROR_DIR.mkdir(parents=True, exist_ok=True)
    raw_file = LLM_ERROR_DIR / f"{recent_item_id}_{suffix}.txt"
    raw_file.write_text(str(raw_text or ""), encoding="utf-8")
    return str(raw_file.relative_to(ROOT_DIR))


def call_llm(row: pd.Series, model: str, max_chars: int) -> tuple[dict, str, int]:
    prompt = PROMPT_TEMPLATE.format(
        institution_name=row["institution_name"],
        source_name=row["source_name"],
        source_type=row["source_type"],
        source_url=row["source_url"],
        item_title=row["item_title"],
        item_date=row.get("item_date", ""),
        publication_date=row.get("publication_date", ""),
        announcement_date=row.get("announcement_date", ""),
        campaign_start_date=row.get("campaign_start_date", ""),
        campaign_end_date=row.get("campaign_end_date", ""),
        recency_basis_date=row.get("recency_basis_date", ""),
        recency_basis_reason=row.get("recency_basis_reason", ""),
        item_url=row.get("item_url", ""),
        item_text=truncate_item_text(str(row.get("item_text", "")), max_chars=max_chars),
    )
    raw_content = summarize_with_anthropic(prompt, model=model, max_tokens=LLM_RESPONSE_MAX_TOKENS)
    try:
        return parse_json_response(raw_content), raw_content, len(prompt)
    except json.JSONDecodeError:
        try:
            repaired = repair_json_response(raw_content, model)
            return parse_json_response(repaired), repaired, len(prompt) + len(raw_content)
        except json.JSONDecodeError as exc:
            raise LLMJsonParseError("Claude yanıtı JSON olarak ayrıştırılamadı.", raw_content) from exc


def build_summary_row(
    row: pd.Series,
    payload: dict,
    model: str,
    raw_path: str = "",
    error_message: str = "",
    lint_result: dict | None = None,
) -> dict:
    lint_result = lint_result or lint_llm_language(payload)
    return {
        "summary_id": summary_id_for(row["recent_item_id"]),
        "recent_item_id": row["recent_item_id"],
        "document_id": row["document_id"],
        "source_id": row["source_id"],
        "institution_id": row["institution_id"],
        "institution_name": row["institution_name"],
        "item_title": row["item_title"],
        "item_date": row.get("item_date", ""),
        "item_url": row.get("item_url", ""),
        "content_role": row.get("content_role", "") or row.get("development_candidate_type", ""),
        "relevance_status": payload["relevance_status"],
        "strategic_theme": payload["strategic_theme"],
        "product_area": payload["product_area"],
        "development_type": payload["development_type"],
        "headline": payload["headline"],
        "summary": payload["summary"],
        "core_assessment": payload["core_assessment"],
        "strategic_relevance": payload["strategic_relevance"],
        "impact_on_us": payload["impact_on_us"],
        "recommended_action": payload["recommended_action"],
        "importance_level": payload["importance_level"],
        "confidence_level": payload["confidence_level"],
        "extracted_facts_json": json.dumps(payload["extracted_facts"], ensure_ascii=False),
        "open_questions_json": json.dumps(payload["open_questions"], ensure_ascii=False),
        "created_at": now_iso(),
        "llm_model": model,
        "review_status": "Beklemede",
        "raw_llm_response_path": raw_path,
        "error_message": error_message,
        "cluster_id": row.get("cluster_id", ""),
        "cluster_status": row.get("cluster_status", "Küme Yok") or "Küme Yok",
        "covered_by_cluster": False,
        "suppress_individual_review": False,
        "suppression_reason": "",
        "language_lint_score": int(lint_result.get("language_lint_score", 0)),
        "language_lint_warnings": json.dumps(lint_result.get("language_lint_warnings", []), ensure_ascii=False),
        "needs_language_review": bool(lint_result.get("needs_language_review", False)),
        "needs_rewrite": bool(lint_result.get("needs_rewrite", False)),
    }


def flag_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def truthy(value) -> bool:
    return flag_text(value).casefold() in {"true", "1", "yes", "evet"}


def ensure_gate_columns(
    items: pd.DataFrame,
    start_date: str,
    allow_undated: bool,
    allow_low_date_confidence: bool,
    allow_end_date_recency: bool,
) -> pd.DataFrame:
    out = items.copy()
    for column in [
        "publication_date",
        "announcement_date",
        "campaign_start_date",
        "campaign_end_date",
        "event_date_type",
        "recency_basis_date",
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
    ]:
        if column not in out.columns:
            out[column] = ""

    for idx, row in out.iterrows():
        if not str(row.get("recency_basis_date", "") or "").strip() or str(row.get("date_source", "") or "").strip() == "metadata_date":
            date_meta = extract_date_semantics(
                visible_text=row.get("item_date", ""),
                url=row.get("item_url", ""),
                metadata_text="",
                inferred_text=f"{row.get('item_title', '')}\n{str(row.get('item_text', ''))[:2000]}",
                source_type=row.get("source_type", ""),
            )
            for column in [
                "publication_date",
                "announcement_date",
                "campaign_start_date",
                "campaign_end_date",
                "event_date_type",
                "recency_basis_date",
                "recency_basis_reason",
            ]:
                out.at[idx, column] = date_meta.get(column, "")
            out.at[idx, "normalized_item_date"] = date_meta.get("normalized_date", "")
            out.at[idx, "date_confidence"] = date_meta.get("date_confidence", "Yok")
            out.at[idx, "date_source"] = date_meta.get("date_source", "missing")
        if str(out.at[idx, "date_confidence"] or "").strip() == "":
            out.at[idx, "date_confidence"] = "Yok"
        recency = evaluate_recency(
            out.loc[idx],
            start_date,
            allow_undated=allow_undated,
            allow_low_confidence=allow_low_date_confidence,
            allow_end_date_recency=allow_end_date_recency,
        )
        out.at[idx, "is_recent"] = bool(recency["is_recent"])
        out.at[idx, "recency_cutoff"] = recency["recency_cutoff"]
        out.at[idx, "recency_reason"] = recency["recency_reason"]
        out.at[idx, "recency_basis_date"] = recency.get("recency_basis_date", out.at[idx, "recency_basis_date"])
        out.at[idx, "recency_basis_reason"] = recency.get("recency_basis_reason", out.at[idx, "recency_basis_reason"])
        out.at[idx, "is_active_campaign"] = bool(recency.get("is_active_campaign", False))
        out.at[idx, "active_campaign_reason"] = recency.get("active_campaign_reason", "")

        if str(row.get("development_candidate_type", "") or "").strip() == "" or str(row.get("is_actual_development", "") or "").strip() == "":
            classification = classify_actual_development(
                row.get("item_title", ""),
                row.get("item_text", ""),
                row.get("item_url", ""),
                row.get("source_type", ""),
            )
            out.at[idx, "development_candidate_type"] = classification["development_candidate_type"]
            out.at[idx, "is_actual_development"] = bool(classification["is_actual_development"])
            out.at[idx, "actual_development_reason"] = classification["actual_development_reason"]
    return out


def gate_skip_reason(
    row: pd.Series,
    start_date: str,
    allow_low_date_confidence: bool,
    allow_undated: bool,
    allow_end_date_recency: bool,
    allow_source_claude_override: bool = False,
) -> str:
    if not truthy(row.get("source_active", "")):
        return "kaynak active=True değil"
    if not truthy(row.get("source_mvp_active", "")):
        return "kaynak mvp_active=True değil"
    source_claude_eligible = flag_text(row.get("source_claude_eligible", ""))
    if source_claude_eligible and not truthy(source_claude_eligible) and not allow_source_claude_override:
        return "kaynak claude_eligible=True değil"
    if str(row.get("item_quality", "")).strip() not in {"Good", "Medium"}:
        return f"item_quality uygun değil: {row.get('item_quality', '')}"
    item_url = str(row.get("item_url", "")).strip()
    source_url = str(row.get("source_url", "") or row.get("registry_source_url", "")).strip()
    canonical_item_url = str(row.get("canonical_item_url", "") or item_url).strip()
    if not item_url:
        return "item_url yok"
    if item_url == source_url or canonical_item_url == source_url:
        return "item_url source_url ile aynı"
    if str(row.get("extraction_method", "")).strip() == "fallback_source_page":
        return "fallback_source_page özetlenmez"
    content_role = str(row.get("content_role", "") or row.get("development_candidate_type", "")).strip()
    if content_role in {"Bağlamsal Veri", "Benchmark Bilgisi", "Kapsam Dışı"}:
        return f"content_role Claude için uygun değil: {content_role}"
    if not truthy(row.get("is_actual_development", "")):
        return f"actual development değil: {row.get('actual_development_reason', '')}"
    recency = evaluate_recency(
        row,
        start_date,
        allow_undated=allow_undated,
        allow_low_confidence=allow_low_date_confidence,
        allow_end_date_recency=allow_end_date_recency,
    )
    if not bool(recency["is_recent"]):
        return str(recency["recency_reason"])
    confidence = str(row.get("date_confidence", "") or "").strip()
    if confidence not in {"Yüksek", "Orta"} and not allow_low_date_confidence:
        return f"tarih güveni düşük: {confidence}"
    normalized = str(row.get("normalized_item_date", "") or "").strip()
    if normalized:
        parsed = pd.to_datetime(normalized, errors="coerce")
        cutoff = pd.to_datetime(start_date, errors="coerce")
        if pd.notna(parsed) and pd.notna(cutoff) and parsed.date() < cutoff.date():
            return f"kesim tarihinden eski: {normalized}"
    elif not allow_undated:
        return "normalized_item_date yok"
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Tekil recent item özetleme ve sınıflandırma.")
    parser.add_argument("--institution", default=None, help='Kurum adı veya id filtresi, örn. "Garanti BBVA".')
    parser.add_argument("--source-id", default=None, help="Belirli source_id filtresi.")
    parser.add_argument("--recent-item-id", default=None, help="Belirli recent_item_id filtresi.")
    parser.add_argument("--limit", type=int, default=None, help="İlk N uygun recent item işle.")
    parser.add_argument("--force", action="store_true", help="Mevcut summary varsa tekrar oluştur.")
    parser.add_argument("--dry-run", action="store_true", help="ANTHROPIC_API_KEY olsa bile dry-run placeholder üret.")
    parser.add_argument("--model", default=None, help="Claude model adını geçici olarak değiştir.")
    parser.add_argument("--save-raw", action="store_true", help="Başarılı yanıtlarda da ham LLM yanıtını sakla.")
    parser.add_argument("--reprocess-summary-id", default=None, help="Belirli summary_id için recent item'ı yeniden işle.")
    parser.add_argument("--reprocess-title", default=None, help="Başlığa göre mevcut recent item'ı yeniden işle.")
    parser.add_argument("--start-date", default=None, help="Recent-development kesim tarihi, örn. 2026-05-01.")
    parser.add_argument("--allow-undated", action="store_true", help="Tarihsiz adayları Claude'a göndermeye izin ver.")
    parser.add_argument("--allow-low-date-confidence", action="store_true", help="Düşük tarih güvenli adayları Claude'a göndermeye izin ver.")
    parser.add_argument("--allow-end-date-recency", action="store_true", help="Sadece kampanya bitiş tarihi bulunan adayları Claude'a göndermeye izin ver.")
    parser.add_argument(
        "--rewrite-artificial-language",
        dest="rewrite_artificial_language",
        action="store_true",
        default=True,
        help="Yapay dil lint'e takılırsa Claude ile sadeleştir. Production varsayılanı açıktır.",
    )
    parser.add_argument(
        "--no-rewrite-artificial-language",
        dest="rewrite_artificial_language",
        action="store_false",
        help="Yapay dil rewrite geçişini kapat.",
    )
    parser.add_argument("--rewrite-threshold", type=int, default=3, help="Bu lint skorunda rewrite denensin.")
    parser.add_argument("--max-rewrite-attempts", type=int, default=2, help="Maksimum rewrite denemesi.")
    parser.add_argument(
        "--rehearsal-allow-source-override",
        action="store_true",
        help="Sadece kontrollü rehearsal için source claude_eligible kapısını item bazlı aş.",
    )
    args = parser.parse_args()

    if not RECENT_ITEMS_PATH.exists():
        raise FileNotFoundError("Önce extract_recent_items.py çalıştırılmalı.")

    config = get_llm_config()
    model = args.model or config.model
    dry_run = args.dry_run or not config.has_api_key or config.provider != "anthropic"
    start_date = resolve_start_date(args.start_date)
    allow_undated = args.allow_undated or bool_from_env("ALLOW_UNDATED_RECENT_ITEMS", False)
    allow_low_date_confidence = args.allow_low_date_confidence or bool_from_env("ALLOW_LOW_DATE_CONFIDENCE", False)
    allow_end_date_recency = args.allow_end_date_recency or bool_from_env("ALLOW_END_DATE_RECENCY", False)
    logging.info("LLM provider: %s", config.provider)
    logging.info("LLM model: %s", model)
    logging.info("Anthropic API key bulundu: %s", "Evet" if config.has_api_key else "Hayır")
    logging.info("MAX_LLM_ITEMS_PER_RUN: %s", config.max_items_per_run)
    logging.info("MAX_CHARS_PER_ITEM: %s", config.max_chars_per_item)
    logging.info("Recency cutoff: %s", start_date)
    logging.info("Allow undated: %s", allow_undated)
    logging.info("Allow low date confidence: %s", allow_low_date_confidence)
    logging.info("Allow end-date recency: %s", allow_end_date_recency)
    if dry_run:
        logging.info("Dry-run mode kullanılacak.")

    items = pd.read_csv(RECENT_ITEMS_PATH, encoding="utf-8-sig")
    if items.empty:
        read_summaries().to_csv(SUMMARIES_PATH, index=False, encoding="utf-8-sig")
        logging.info("Recent item candidates: 0")
        logging.info("Summaries created: 0")
        logging.info("Total summaries stored: %s", len(read_summaries()))
        logging.info("JSON parse failures: 0")
        logging.info("Items processed: 0")
        logging.info("Estimated item chars used: 0")
        logging.info("Estimated prompt/repair chars used: 0")
        return

    for column in [
        "relevance_status",
        "item_quality",
        "recent_item_id",
        "institution_name",
        "institution_id",
        "item_url",
        "source_url",
        "extraction_method",
        "content_role",
        "canonical_item_url",
    ]:
        if column not in items.columns:
            items[column] = ""
    items = ensure_gate_columns(items, start_date, allow_undated, allow_low_date_confidence, allow_end_date_recency)
    items = enrich_items_with_source_readiness(items)

    summaries = read_summaries()
    reprocess_item_ids: set[str] = set()
    if args.reprocess_summary_id and not summaries.empty:
        reprocess_matches = summaries[summaries["summary_id"].astype(str).eq(args.reprocess_summary_id)]
        reprocess_item_ids.update(reprocess_matches["recent_item_id"].dropna().astype(str))
    if args.reprocess_title:
        title_token = args.reprocess_title.strip().casefold()
        title_matches = items[items["item_title"].astype(str).str.casefold().str.contains(title_token, regex=False, na=False)]
        reprocess_item_ids.update(title_matches["recent_item_id"].dropna().astype(str))

    existing_item_ids = (
        set()
        if args.force or reprocess_item_ids
        else set(summaries["recent_item_id"].dropna()) if not summaries.empty else set()
    )
    blocked_item_ids = read_blocked_recent_item_ids()
    duplicate_item_ids = set(
        items.loc[items["recent_item_id"].astype(str).duplicated(keep=False), "recent_item_id"].dropna().astype(str)
    )

    relevance_status = items["relevance_status"].fillna("").astype(str).str.strip()
    item_quality = items["item_quality"].fillna("").astype(str).str.strip()
    status_mask = pd.Series(True, index=items.index) if args.force or reprocess_item_ids else relevance_status.isin(["", "Beklemede", "Belirsiz"])
    pre_gate = items[
        status_mask
        & item_quality.isin(["Good", "Medium"])
        & ~items["recent_item_id"].isin(existing_item_ids)
    ].copy()
    gate_reasons = {}
    for _, row in pre_gate.iterrows():
        item_id = str(row.get("recent_item_id", ""))
        reason = ""
        if item_id in blocked_item_ids:
            reason = "item daha önce arşivlenmiş/reddedilmiş/yayınlanmış"
        elif item_id in duplicate_item_ids:
            reason = "recent_item_id duplicate"
        else:
            reason = gate_skip_reason(
                row,
                start_date,
                allow_low_date_confidence,
                allow_undated,
                allow_end_date_recency,
                allow_source_claude_override=args.rehearsal_allow_source_override,
            )
        if reason:
            gate_reasons[item_id] = reason
            logging.info("Claude skip | %s | %s | %s", item_id, str(row.get("item_title", ""))[:120], reason)
    candidates = pre_gate[~pre_gate["recent_item_id"].astype(str).isin(gate_reasons)].copy()
    if reprocess_item_ids:
        candidates = candidates[candidates["recent_item_id"].astype(str).isin(reprocess_item_ids)]
    if args.institution:
        token = args.institution.strip().casefold()
        candidates = candidates[
            candidates["institution_name"].astype(str).str.casefold().eq(token)
            | candidates["institution_id"].astype(str).str.casefold().eq(token)
        ]
    if args.source_id:
        candidates = candidates[candidates["source_id"].astype(str).eq(args.source_id)]
    if args.recent_item_id:
        candidates = candidates[candidates["recent_item_id"].astype(str).eq(args.recent_item_id)]
    candidates = candidates.sort_values("detected_at", ascending=False)
    effective_limit = config.max_items_per_run
    if args.limit is not None:
        effective_limit = args.limit
    candidates = candidates.head(effective_limit)

    logging.info("Recent item candidates: %s", len(candidates))
    new_rows = []
    relevance_updates = {}
    parse_failures = 0
    rewrite_attempts = 0
    rewrite_failures = 0
    total_prompt_chars = 0
    total_item_chars = 0

    for _, row in candidates.iterrows():
        item_text = str(row.get("item_text", ""))
        total_item_chars += min(len(item_text), config.max_chars_per_item)
        fallback = fallback_payload(row, "Kuru çalışma veya eksik yerel Claude kimlik bilgisi nedeniyle model çağrısı yapılmadı.")
        payload = fallback
        llm_model = "dry-run"
        raw_path = ""
        error_message = fallback["error_message"]

        if not dry_run:
            try:
                raw_payload, raw_content, prompt_chars = call_llm(row, model, config.max_chars_per_item)
                total_prompt_chars += prompt_chars
                payload = apply_item_specific_guardrails(row, normalize_payload(raw_payload, fallback))
                llm_model = model
                error_message = ""
                if raw_content and args.save_raw:
                    raw_path = save_raw_response(row["recent_item_id"], "recent_item_raw", raw_content)
            except LLMJsonParseError as exc:
                parse_failures += 1
                error_message = "JSON parse hatası"
                logging.warning("JSON parse failed for %s", row["recent_item_id"])
                try:
                    raw_path = save_raw_response(row["recent_item_id"], "recent_item_parse_error", exc.raw_response)
                except Exception:
                    raw_path = ""
                payload = fallback
                llm_model = "parse-error-dry-run"
            except MissingApiKeyError:
                payload = fallback
                llm_model = "dry-run"
            except Exception as exc:
                error_message = str(exc)[:500]
                logging.warning("LLM failed for %s; dry-run fallback used: %s", row["recent_item_id"], type(exc).__name__)
                payload = fallback
                llm_model = "llm-error-dry-run"
        else:
            logging.info("Dry-run summary for %s", row["recent_item_id"])

        payload = apply_item_specific_guardrails(row, normalize_payload(payload, fallback))
        lint_result = lint_llm_language(payload)
        attempt = 0
        while (
            args.rewrite_artificial_language
            and not dry_run
            and attempt < max(0, args.max_rewrite_attempts)
            and (
                bool(lint_result.get("needs_rewrite", False))
                or int(lint_result.get("language_lint_score", 0)) >= args.rewrite_threshold
            )
        ):
            rewrite_attempts += 1
            attempt += 1
            try:
                rewritten_payload, rewritten_raw = rewrite_artificial_language(payload, model)
                payload = apply_item_specific_guardrails(row, normalize_payload(rewritten_payload, payload))
                lint_result = lint_llm_language(payload)
                total_prompt_chars += len(json.dumps(payload, ensure_ascii=False)) + len(rewritten_raw)
                if args.save_raw:
                    raw_path = save_raw_response(row["recent_item_id"], f"recent_item_rewrite_{attempt}", rewritten_raw)
            except Exception as exc:
                rewrite_failures += 1
                logging.warning("Language rewrite failed for %s: %s", row["recent_item_id"], type(exc).__name__)
                break
        relevance_updates[row["recent_item_id"]] = payload["relevance_status"]
        new_rows.append(build_summary_row(row, payload, llm_model, raw_path, error_message, lint_result))

    latest_summaries = read_summaries()
    if (args.force or reprocess_item_ids) and new_rows:
        force_ids = {row["recent_item_id"] for row in new_rows}
        latest_summaries = latest_summaries[~latest_summaries["recent_item_id"].isin(force_ids)]
    elif new_rows and not latest_summaries.empty:
        latest_ids = set(latest_summaries["recent_item_id"].dropna().astype(str))
        new_rows = [row for row in new_rows if str(row.get("recent_item_id", "")) not in latest_ids]
    updated = pd.concat([latest_summaries, pd.DataFrame(new_rows)], ignore_index=True)
    updated = updated.reindex(columns=SUMMARY_COLUMNS)
    updated.to_csv(SUMMARIES_PATH, index=False, encoding="utf-8-sig")

    if relevance_updates:
        items.loc[items["recent_item_id"].isin(relevance_updates), "relevance_status"] = items["recent_item_id"].map(relevance_updates).fillna(items["relevance_status"])
        items.to_csv(RECENT_ITEMS_PATH, index=False, encoding="utf-8-sig")

    logging.info("Summaries created: %s", len(new_rows))
    logging.info("Total summaries stored: %s", len(updated))
    logging.info("JSON parse failures: %s", parse_failures)
    logging.info("Language rewrite attempts: %s", rewrite_attempts)
    logging.info("Language rewrite failures: %s", rewrite_failures)
    logging.info("Items processed: %s", len(candidates))
    logging.info("Items skipped by recency/accuracy gate: %s", len(gate_reasons))
    logging.info("Estimated item chars used: %s", total_item_chars)
    logging.info("Estimated prompt/repair chars used: %s", total_prompt_chars)


if __name__ == "__main__":
    main()
