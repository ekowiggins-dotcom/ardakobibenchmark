from __future__ import annotations

import pandas as pd


TRIAGE_REVIEW = "İncelemeye Gönder"
TRIAGE_ARCHIVE = "Düşük Öncelik / Arşiv"
TRIAGE_RESEARCH = "Ek Araştırma Gerekli"
TRIAGE_MANAGEMENT_AWARENESS = "Yönetici Bilgilendirme"

REVIEW_ACTIONS = {
    "Yanıt Geliştir",
    "İş Birliği Fırsatını İncele",
    "Uyarlama Fırsatını Değerlendir",
    "Yönetime Eskale Et",
    "BD Konuşma Notlarına Ekle",
    "Yönetici Bilgilendirme Notuna Ekle",
}

REVIEW_THEMES = {
    "KOBİ Mevduat",
    "Gömülü Finans",
    "Ödemeler ve POS",
    "Dijital KOBİ Yolculuğu",
    "KOBİ Kredileri",
    "Nakit Yönetimi",
    "Ekosistem İş Birlikleri",
    "Kampanyalar",
    "Regülasyon",
    "Kurumsal Konumlandırma",
}

MAJOR_REPUTATION_SIGNALS = {
    "türkiye’nin en iyi bankası",
    "türkiye'nin en iyi bankası",
    "en iyi banka",
    "global finance",
    "euromoney",
    "the banker",
    "brand finance",
    "lider",
    "birinci",
    "en güçlü banka",
    "ödül",
    "ranking",
    "sıralama",
}

LOW_PRIORITY_KEYWORDS = {
    "ödül",
    "award",
    "öğrenci",
    "finansal okuryazarlık",
    "sosyal sorumluluk",
    "kültür",
    "sanat",
    "sponsorluk",
    "genel görünüm",
    "yatırım bankası ödülü",
    "kurumsal hafıza",
    "kurumsal tarih",
    "müze",
}

STRONG_RELEVANCE_KEYWORDS = {
    "kobi",
    "esnaf",
    "pos",
    "üye işyeri",
    "odeme",
    "ödeme",
    "tahsilat",
    "api",
    "açık bankacılık",
    "mevduat",
    "ticari kredi",
    "nakit yönetimi",
    "kampanya",
    "iş birliği",
    "regülasyon",
    "tcmb",
    "bddk",
    "rekabet kurumu",
}


def _clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _contains_any(text: str, keywords: set[str]) -> bool:
    lower = text.casefold()
    return any(keyword.casefold() in lower for keyword in keywords)


def management_awareness_reason(row) -> str:
    action = _clean(row.get("recommended_action", ""))
    theme = _clean(row.get("strategic_theme", ""))
    importance = _clean(row.get("importance_level", ""))
    content_role = _clean(row.get("content_role", ""))
    relevance_status = _clean(row.get("relevance_status", ""))
    text = " ".join(_clean(row.get(column, "")) for column in ["headline", "item_title", "summary", "core_assessment"])
    has_reputation = _contains_any(text, MAJOR_REPUTATION_SIGNALS)
    has_weak_pr = _contains_any(text, LOW_PRIORITY_KEYWORDS) and not has_reputation

    if content_role == "Yönetici Bilgilendirme" and relevance_status != "İlgisiz":
        return "Gelişme doğrudan BD aksiyonu değil; yönetici farkındalığı için izlenmeli."
    if has_weak_pr:
        return ""
    if action == "Yönetici Bilgilendirme Notuna Ekle":
        return "Aksiyon önerisi yönetici bilgilendirme notuna ekleme."
    if theme == "Kurumsal Konumlandırma" and importance in {"Orta", "Yüksek"}:
        return "Kurumsal konumlandırma sinyali orta/yüksek önem taşıyor."
    if has_reputation:
        return "Majör ödül, ranking veya itibar sinyali yönetici farkındalığı gerektiriyor."
    return ""


def triage_recent_item_summary(row) -> dict:
    relevance_status = _clean(row.get("relevance_status", "")) or "Belirsiz"
    impact = _clean(row.get("impact_on_us", ""))
    importance = _clean(row.get("importance_level", ""))
    action = _clean(row.get("recommended_action", ""))
    theme = _clean(row.get("strategic_theme", ""))
    development_type = _clean(row.get("development_type", ""))
    confidence = _clean(row.get("confidence_level", ""))

    primary_text = " ".join(
        _clean(row.get(column, ""))
        for column in ["headline", "item_title", "summary"]
    )
    has_low_keyword = _contains_any(primary_text, LOW_PRIORITY_KEYWORDS)
    has_strong_keyword = _contains_any(primary_text, STRONG_RELEVANCE_KEYWORDS)
    awareness_reason = management_awareness_reason(row)

    if awareness_reason:
        return {
            "triage_status": TRIAGE_MANAGEMENT_AWARENESS,
            "triage_reason": awareness_reason,
            "awareness_reason": awareness_reason,
            "should_queue_for_review": False,
            "should_queue_for_management_awareness": True,
        }

    review_reasons = []
    if relevance_status == "İlgili":
        review_reasons.append("LLM gelişmeyi ilgili işaretledi")
    if impact in {"Orta", "Yüksek"}:
        review_reasons.append(f"Etki seviyesi {impact}")
    if importance in {"Orta", "Yüksek"}:
        review_reasons.append(f"Önem seviyesi {importance}")
    if action in REVIEW_ACTIONS:
        review_reasons.append(f"Aksiyon önerisi: {action}")
    if theme in REVIEW_THEMES and impact != "Düşük":
        review_reasons.append(f"{theme} teması düşük olmayan etkiyle geldi")
    if theme == "Kurumsal Konumlandırma" and importance in {"Orta", "Yüksek"}:
        review_reasons.append("Kurumsal konumlandırma sinyali orta/yüksek önem taşıyor")
    if _contains_any(primary_text, MAJOR_REPUTATION_SIGNALS) and importance in {"Orta", "Yüksek"}:
        review_reasons.append("Majör itibar/rakip konumlandırma sinyali")

    if review_reasons:
        return {
            "triage_status": TRIAGE_REVIEW,
            "triage_reason": "; ".join(review_reasons),
            "should_queue_for_review": True,
            "should_queue_for_management_awareness": False,
        }

    archive_reasons = []
    low_rule = (
        impact == "Düşük"
        and importance == "Düşük"
        and (relevance_status in {"İlgisiz", "Belirsiz", ""} or development_type == "İlgili Gelişme Yok")
    )
    if low_rule:
        archive_reasons.append("Düşük etki/önem ve ilgisiz-belirsiz gelişme")
    if has_low_keyword and not has_strong_keyword:
        archive_reasons.append("Düşük öncelikli PR anahtar kelimeleri içeriyor")

    if archive_reasons:
        return {
            "triage_status": TRIAGE_ARCHIVE,
            "triage_reason": "; ".join(archive_reasons),
            "should_queue_for_review": False,
            "should_queue_for_management_awareness": False,
        }

    research_reason = "Triage kuralları net karar veremedi"
    if confidence == "Düşük":
        research_reason = "Güven seviyesi düşük; analist kontrolü gerekli"
    return {
        "triage_status": TRIAGE_RESEARCH,
        "triage_reason": research_reason,
        "should_queue_for_review": True,
        "should_queue_for_management_awareness": False,
    }
