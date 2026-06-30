from __future__ import annotations

import hashlib
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:  # Optional in runtime, required in requirements for normal use.
    load_dotenv = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(ROOT_DIR))

from clean_text import read_cleaned_text, truncate_for_llm
from utils.translations import to_tr
METADATA_PATH = DATA_DIR / "raw_documents_metadata.csv"
REGISTRY_PATH = DATA_DIR / "source_registry.csv"
EXTRACTIONS_PATH = DATA_DIR / "llm_extractions.csv"
MIN_TEXT_CHARS = 250
DEFAULT_MODEL = "gpt-4.1-mini"

EXTRACTION_COLUMNS = [
    "extraction_id",
    "document_id",
    "source_id",
    "tier",
    "institution_id",
    "institution_name",
    "strategic_theme",
    "product_area",
    "development_type",
    "headline",
    "summary",
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
]

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
}
ALLOWED_LEVELS = {"Yüksek", "Orta", "Düşük"}
WEEKLY_SOURCE_TYPES = {
    "Official Campaign Page",
    "Official Press Release Page",
    "Regulator",
    "Industry Association",
    "News Site",
    "Fintech News",
    "Business News",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


PROMPT_TEMPLATE = """Sen bir KOBİ bankacılığı rekabet istihbaratı analistisin.

Aşağıda onaylı ve kürate edilmiş bir Tier 1 veya Tier 2 kaynaktan temizlenmiş metin verilecek.

Kaynak seviyesi:
{tier}

Kurum:
{institution_name}

Kaynak adı:
{source_name}

Kaynak tipi:
{source_type}

Kaynak URL:
{url}

Görevin:
Kaynak metinde açıkça desteklenen haftalık gelişme, kampanya, iş birliği, regülasyon, ürün güncellemesi veya pazar sinyalini çıkarmak.

Odak alanları:

* KOBİ mevduat
* gömülü finans
* ödemeler ve POS
* üye işyeri edinimi
* dijital KOBİ yolculuğu
* nakit yönetimi
* KOBİ kredileri
* kampanyalar
* iş birlikleri
* regülasyon
* KOBİ bankacılığı için global iyi uygulamalar

Kurallar:

* Yanıtın tamamı Türkçe olmalıdır. İngilizce çıktı verme. Sadece marka adları, URL’ler, kaynak başlıkları ve resmi ürün adları İngilizce kalabilir.
* Kaynakta açıkça yazmayan hiçbir şeyi uydurma.
* Bir ürünün yeni çıktığını sadece metin bunu açıkça söylüyorsa belirt.
* Eğer kaynak genel bir ürün sayfasıysa ve gerçek bir yeni gelişme görünmüyorsa development_type alanını "İlgili Gelişme Yok" yap.
* Eğer metin KOBİ bankacılığı veya ödeme ekosistemi açısından ilgisizse impact_on_us alanını "Düşük", recommended_action alanını "Önceliklendirme" yap.
* Kaynak yalnızca eski/stabil ürün bilgisi içeriyorsa bunu haftalık gelişme gibi yazma.
* Yöneticiye gidecek metin kısa ve net olmalı.

Sadece geçerli JSON döndür.
Markdown, açıklama veya kod bloğu ekleme.

Şema:

{{
\"strategic_theme\": \"\",
\"product_area\": \"\",
\"development_type\": \"\",
\"headline\": \"\",
\"summary\": \"\",
\"strategic_relevance\": \"\",
\"impact_on_us\": \"\",
\"recommended_action\": \"\",
\"importance_level\": \"\",
\"confidence_level\": \"\",
\"extracted_facts\": [],
\"open_questions\": []
}}

Alan kuralları:

* strategic_theme şu değerlerden biri olmalı:
  "KOBİ Mevduat", "Gömülü Finans", "Ödemeler ve POS", "Dijital KOBİ Yolculuğu", "KOBİ Kredileri", "Nakit Yönetimi", "Ekosistem İş Birlikleri", "Kampanyalar", "Regülasyon", "Global İyi Uygulama"
* development_type şu değerlerden biri olmalı:
  "Ürün Lansmanı", "Kampanya", "İş Birliği", "Fiyat Değişikliği", "Regülasyon", "Rapor / Araştırma", "Teknoloji Güncellemesi", "Pazar Sinyali", "Yönetim Açıklaması", "Ürün Sayfası Değişikliği", "İlgili Gelişme Yok"
* impact_on_us şu değerlerden biri olmalı:
  "Yüksek", "Orta", "Düşük"
* recommended_action şu değerlerden biri olmalı:
  "İzle", "Yanıt Geliştir", "İş Birliği Fırsatını İncele", "Uyarlama Fırsatını Değerlendir", "Önceliklendirme", "Yönetime Eskale Et", "BD Konuşma Notlarına Ekle"
* importance_level şu değerlerden biri olmalı:
  "Yüksek", "Orta", "Düşük"
* confidence_level şu değerlerden biri olmalı:
  "Yüksek", "Orta", "Düşük"
* headline en fazla 120 karakter olmalı.
* summary en fazla 3 cümle olmalı.
* strategic_relevance, gelişmenin Akbank KOBİ stratejisi, mevduat, gömülü finans, ödemeler/POS veya BD açısından neden önemli olduğunu açıklamalı.
* extracted_facts kısa, kaynağa dayalı maddeler olmalı.
* open_questions analistin kontrol etmesi gereken belirsizlikleri içermeli.

Temizlenmiş kaynak metni:
{cleaned_text}
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extraction_id_for(document_id: str) -> str:
    digest = hashlib.sha1(document_id.encode("utf-8")).hexdigest()[:10]
    return f"EXT-{digest}"


def read_extractions() -> pd.DataFrame:
    if EXTRACTIONS_PATH.exists():
        return pd.read_csv(EXTRACTIONS_PATH, encoding="utf-8-sig")
    return pd.DataFrame(columns=EXTRACTION_COLUMNS)


def coerce_value(value: str, allowed: set[str], fallback: str) -> str:
    return value if value in allowed else fallback


def normalize_payload(payload: dict, fallback: dict) -> dict:
    headline = str(payload.get("headline") or fallback["headline"])[:120]
    return {
        "strategic_theme": coerce_value(
            to_tr(payload.get("strategic_theme", "")), ALLOWED_THEMES, fallback["strategic_theme"]
        ),
        "product_area": to_tr(str(payload.get("product_area") or fallback["product_area"]))[:120],
        "development_type": coerce_value(
            to_tr(payload.get("development_type", "")),
            ALLOWED_DEVELOPMENT_TYPES,
            fallback["development_type"],
        ),
        "headline": to_tr(headline),
        "summary": to_tr(str(payload.get("summary") or fallback["summary"])),
        "strategic_relevance": to_tr(str(payload.get("strategic_relevance") or fallback["strategic_relevance"])),
        "impact_on_us": coerce_value(
            to_tr(payload.get("impact_on_us", "")), ALLOWED_IMPACTS, fallback["impact_on_us"]
        ),
        "recommended_action": coerce_value(
            to_tr(payload.get("recommended_action", "")), ALLOWED_ACTIONS, fallback["recommended_action"]
        ),
        "importance_level": coerce_value(
            to_tr(payload.get("importance_level", "")), ALLOWED_LEVELS, fallback["importance_level"]
        ),
        "confidence_level": coerce_value(
            to_tr(payload.get("confidence_level", "")), ALLOWED_LEVELS, fallback["confidence_level"]
        ),
        "extracted_facts": to_tr(payload.get("extracted_facts") or fallback["extracted_facts"]),
        "open_questions": to_tr(payload.get("open_questions") or fallback["open_questions"]),
    }


def fallback_payload(row: pd.Series, reason: str) -> dict:
    theme = str(row.get("source_name", "Kaynak"))
    return {
        "strategic_theme": "Global İyi Uygulama" if row["tier"] == "Tier 2" else "Ödemeler ve POS",
        "product_area": row.get("source_name", "Curated source"),
        "development_type": "İlgili Gelişme Yok" if reason == "too_short" else "Ürün Sayfası Değişikliği",
        "headline": f"{theme} için analist incelemesi gerekli"[:120],
        "summary": (
            "LLM kimlik bilgisi tanımlı olmadığı için dry-run yer tutucusu oluşturuldu."
            if reason == "dry_run"
            else "Temizlenmiş metin güvenilir çıkarım için çok kısa."
        ),
        "strategic_relevance": "Analist bu kürate edilmiş kaynağın KOBİ açısından anlamlı gelişme içerip içermediğini doğrulamalıdır.",
        "impact_on_us": "Düşük",
        "recommended_action": "Önceliklendirme" if reason == "too_short" else "İzle",
        "importance_level": "Düşük",
        "confidence_level": "Düşük",
        "extracted_facts": [f"Kaynak toplandı: {row.get('url', '')}"],
        "open_questions": ["Maddi bir ürün, kampanya, fiyatlama veya iş birliği değişikliği var mı?"],
    }


def call_llm(row: pd.Series, cleaned_text: str, api_key: str, model: str) -> dict:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    client = OpenAI(api_key=api_key)
    prompt = PROMPT_TEMPLATE.format(
        tier=row["tier"],
        institution_name=row["institution_name"],
        source_name=row["source_name"],
        source_type=row["source_type"],
        url=row["url"],
        cleaned_text=truncate_for_llm(cleaned_text),
    )
    last_error = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )
            content = response.choices[0].message.content
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return json.loads(content[content.find("{") : content.rfind("}") + 1])
        except Exception as exc:
            last_error = exc
            logging.warning("Haftalık gelişme çıkarımı denemesi %s başarısız: %s", attempt + 1, exc)
    error_dir = DATA_DIR / "llm_errors"
    error_dir.mkdir(exist_ok=True)
    (error_dir / f"{row['document_id']}_weekly_error.txt").write_text(str(last_error), encoding="utf-8")
    raise last_error


def build_row(row: pd.Series, payload: dict, model: str) -> dict:
    extraction_id = extraction_id_for(row["document_id"])
    return {
        "extraction_id": extraction_id,
        "document_id": row["document_id"],
        "source_id": row["source_id"],
        "tier": row["tier"],
        "institution_id": row["institution_id"],
        "institution_name": row["institution_name"],
        "strategic_theme": payload["strategic_theme"],
        "product_area": payload["product_area"],
        "development_type": payload["development_type"],
        "headline": payload["headline"],
        "summary": payload["summary"],
        "strategic_relevance": payload["strategic_relevance"],
        "impact_on_us": payload["impact_on_us"],
        "recommended_action": payload["recommended_action"],
        "importance_level": payload["importance_level"],
        "confidence_level": payload["confidence_level"],
        "extracted_facts_json": json.dumps(payload["extracted_facts"], ensure_ascii=False),
        "open_questions_json": json.dumps(payload["open_questions"], ensure_ascii=False),
        "created_at": now_iso(),
        "llm_model": model,
        "review_status": "Pending",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Haftalık gelişme çıkarımı")
    parser.add_argument("--force", action="store_true", help="Aynı document_id için tekrar çıkarım yap.")
    args = parser.parse_args()

    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")

    if not METADATA_PATH.exists():
        raise FileNotFoundError("Run collect_static_pages.py and detect_changes.py first")

    api_key = os.getenv("LEGACY_LLM_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    dry_run = not api_key

    metadata = pd.read_csv(METADATA_PATH, encoding="utf-8-sig")
    registry = pd.read_csv(REGISTRY_PATH, encoding="utf-8-sig")[
        ["source_id", "source_type", "extraction_mode"]
    ]
    metadata = metadata.merge(registry, on="source_id", how="left")
    if "change_status" not in metadata.columns:
        metadata["change_status"] = metadata["status"]
    candidates = metadata[
        metadata["change_status"].isin(["new_source", "changed"])
        & metadata["extraction_mode"].isin(["weekly_development", "both"])
        & metadata["source_type"].isin(WEEKLY_SOURCE_TYPES)
    ].copy()
    logging.info("Haftalık gelişme çıkarımı aday doküman sayısı: %s", len(candidates))
    existing = read_extractions()
    already_extracted = set(existing["document_id"].dropna()) if not existing.empty else set()
    new_rows = []

    for _, row in candidates.iterrows():
        if not args.force and row["document_id"] in already_extracted:
            continue

        cleaned_text = read_cleaned_text(ROOT_DIR, row.get("cleaned_text_path", ""))
        reason = "dry_run"
        payload = fallback_payload(row, reason)
        llm_model = "dry-run"

        if len(cleaned_text) < MIN_TEXT_CHARS:
            reason = "too_short"
            payload = fallback_payload(row, reason)
            llm_model = "skipped-too-short"
            logging.info("Skipping short document %s", row["document_id"])
        elif not dry_run:
            try:
                raw_payload = call_llm(row, cleaned_text, api_key, model)
                payload = normalize_payload(raw_payload, fallback_payload(row, "dry_run"))
                llm_model = model
            except Exception as exc:
                logging.warning("LLM extraction failed for %s: %s", row["document_id"], exc)
                payload = fallback_payload(row, "dry_run")
                llm_model = "llm-error-dry-run"
        else:
            logging.info("Dry-run extraction for %s", row["document_id"])

        payload = normalize_payload(payload, fallback_payload(row, reason))
        new_rows.append(build_row(row, payload, llm_model))

    if new_rows:
        updated = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    else:
        updated = existing
    updated = updated.reindex(columns=EXTRACTION_COLUMNS)
    updated.to_csv(EXTRACTIONS_PATH, index=False, encoding="utf-8-sig")
    logging.info("Haftalık gelişme çıkarımı toplam satır sayısı: %s", len(updated))


if __name__ == "__main__":
    main()
