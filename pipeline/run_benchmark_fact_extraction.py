from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:
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
FACTS_PATH = DATA_DIR / "benchmark_facts.csv"
MIN_TEXT_CHARS = 250
DEFAULT_MODEL = "gpt-4.1-mini"

FACT_COLUMNS = [
    "fact_id",
    "document_id",
    "source_id",
    "tier",
    "institution_id",
    "institution_name",
    "source_type",
    "product_area",
    "benchmark_dimension",
    "fact_type",
    "fact_text",
    "strategic_relevance",
    "confidence_level",
    "extracted_facts_json",
    "open_questions_json",
    "source_url",
    "extracted_at",
    "llm_model",
    "review_status",
]

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
ALLOWED_DIMENSIONS = {
    "KOBİ Mevduat Önermesi",
    "Gömülü Finans Olgunluğu",
    "Ödemeler ve Üye İşyeri Edinimi",
    "Dijital KOBİ Yolculuğu",
    "Nakit Yönetimi",
    "KOBİ Kredi Bağlantısı",
    "Ekosistem İş Birlikleri",
    "Fiyatlama Şeffaflığı",
    "BD Kullanılabilirliği",
    "Stratejik Tehdit Seviyesi",
}
ALLOWED_FACT_TYPES = {
    "Ürün Özelliği",
    "Ürün Gereksinimi",
    "Fiyat / Ücret Sinyali",
    "Kanal Erişilebilirliği",
    "Dijital Yetkinlik",
    "Kart Şeması / Ağ Desteği",
    "Mutabakat / Raporlama",
    "Kampanya Avantajı",
    "İş Birliği",
    "API / Geliştirici Yetkinliği",
    "Açık Soru",
    "Diğer",
}
ALLOWED_CONFIDENCE = {"Yüksek", "Orta", "Düşük"}
ERROR_DIR = DATA_DIR / "llm_errors"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


PROMPT_TEMPLATE = """Sen bir KOBİ bankacılığı benchmark analistisin.

Aşağıda, onaylı ve kürate edilmiş bir kamu kaynağından temizlenmiş metin verilecek.

Kaynak seviyesi:
{tier}

Kurum:
{institution_name}

Kaynak tipi:
{source_type}

Kaynak URL:
{url}

Görevin:
Yalnızca kaynak metinde açıkça desteklenen benchmark bulgularını çıkarmak.

Odak alanları:

* KOBİ mevduat / mevduat ürünleri
* vadesiz hesap
* vadeli hesap
* POS ve üye işyeri hizmetleri
* Sanal POS
* Cep POS / SoftPOS
* ödeme linki
* QR ödeme
* kart kabul kapsamı
* taksit / ön provizyon / yabancı kart kabulü
* mutabakat ve raporlama
* gömülü finans
* API / geliştirici yetkinlikleri
* açık bankacılık
* dijital KOBİ yolculuğu
* KOBİ kredileri
* nakit yönetimi
* kampanyalar
* fiyat / ücret / komisyon sinyalleri
* KOBİ’lerle ilgili iş birlikleri

Kurallar:

* Yanıtın tamamı Türkçe olmalıdır. İngilizce çıktı verme. Sadece marka adları, URL’ler, kaynak başlıkları ve resmi ürün adları İngilizce kalabilir.
* Kaynakta açıkça yazmayan hiçbir şeyi uydurma.
* Özellikleri varsayma.
* Bir ürünün “yeni çıktığını” ancak metin bunu açıkça söylüyorsa yaz.
* Menü, navigasyon, footer veya tekrar eden kategori isimlerini benchmark bulgusu olarak alma.
* Aynı anlamdaki bulguları tekrar etme.
* Eğer metinde ilgili benchmark bulgusu yoksa boş facts listesi döndür.

Sadece geçerli JSON döndür.
Açıklama metni, markdown veya kod bloğu ekleme.

Şema:

{{
  "facts": [
    {{
      "product_area": "",
      "benchmark_dimension": "",
      "fact_type": "",
      "fact_text": "",
      "strategic_relevance": "",
      "confidence_level": "",
      "open_questions": []
    }}
  ]
}}

Alan kuralları:

* product_area şu değerlerden biri olmalı:
  "KOBİ Mevduat", "Ödemeler ve POS", "Gömülü Finans", "Dijital KOBİ Yolculuğu", "KOBİ Kredileri", "Nakit Yönetimi", "Ekosistem İş Birlikleri", "Fiyatlama Şeffaflığı", "Diğer"

* benchmark_dimension şu değerlerden biri olmalı:
  "KOBİ Mevduat Önermesi", "Gömülü Finans Olgunluğu", "Ödemeler ve Üye İşyeri Edinimi", "Dijital KOBİ Yolculuğu", "Nakit Yönetimi", "KOBİ Kredi Bağlantısı", "Ekosistem İş Birlikleri", "Fiyatlama Şeffaflığı", "BD Kullanılabilirliği", "Stratejik Tehdit Seviyesi"

* fact_type şu değerlerden biri olmalı:
  "Ürün Özelliği", "Ürün Gereksinimi", "Fiyat / Ücret Sinyali", "Kanal Erişilebilirliği", "Dijital Yetkinlik", "Kart Şeması / Ağ Desteği", "Mutabakat / Raporlama", "Kampanya Avantajı", "İş Birliği", "API / Geliştirici Yetkinliği", "Açık Soru", "Diğer"

* confidence_level şu değerlerden biri olmalı:
  "Yüksek", "Orta", "Düşük"

* fact_text kısa, açık, doğrulanabilir ve kaynakla doğrudan desteklenmiş olmalı.
* strategic_relevance, bulgunun KOBİ stratejisi, BD, mevduat, gömülü finans, POS veya dijital yolculuk açısından neden önemli olduğunu açıklamalı.
* open_questions, analistin manuel kontrol etmesi gereken noktaları içermeli.

Temizlenmiş kaynak metni:
{cleaned_text}
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fact_id_for(document_id: str, index: int, fact_text: str) -> str:
    digest = hashlib.sha1(f"{document_id}|{index}|{fact_text}".encode("utf-8")).hexdigest()[:12]
    return f"FACT-{digest}"


def read_facts() -> pd.DataFrame:
    if FACTS_PATH.exists():
        facts = pd.read_csv(FACTS_PATH, encoding="utf-8-sig")
        for column in FACT_COLUMNS:
            if column not in facts.columns:
                facts[column] = ""
        return facts.reindex(columns=FACT_COLUMNS)
    return pd.DataFrame(columns=FACT_COLUMNS)


def coerce(value: str, allowed: set[str], fallback: str) -> str:
    return value if value in allowed else fallback


def infer_fact_from_sentence(sentence: str) -> dict | None:
    lower = sentence.lower()
    if any(term in lower for term in ["sanal pos", "pos", "kartlı ödeme", "ödeme"]):
        return {
            "product_area": "Ödemeler ve POS",
            "benchmark_dimension": "Ödemeler ve Üye İşyeri Edinimi",
            "fact_type": "Ürün Özelliği",
            "fact_text": sentence[:400],
            "strategic_relevance": (
                "Ödemeler ve POS yetkinlikleri üye işyeri edinimi, günlük KOBİ ilişki derinliği "
                "ve ödeme akışına dayalı mevduat fırsatları açısından önemlidir."
            ),
            "confidence_level": "Orta",
            "open_questions": ["Fiyatlama, valör/tahsilat süresi ve mutabakat detaylarını manuel kontrol et."],
        }
    if any(term in lower for term in ["kredi", "finansman", "limit"]):
        return {
            "product_area": "KOBİ Kredileri",
            "benchmark_dimension": "KOBİ Kredi Bağlantısı",
            "fact_type": "Ürün Özelliği",
            "fact_text": sentence[:400],
            "strategic_relevance": (
                "KOBİ kredi sinyalleri rakiplerin krediyi günlük bankacılık ve BD ihtiyaçlarıyla nasıl bağladığını gösterir."
            ),
            "confidence_level": "Orta",
            "open_questions": ["Uygunluk koşullarını ve teklifin kampanyaya özel olup olmadığını doğrula."],
        }
    if any(term in lower for term in ["mevduat", "hesap", "vadeli", "vadesiz"]):
        return {
            "product_area": "KOBİ Mevduat",
            "benchmark_dimension": "KOBİ Mevduat Önermesi",
            "fact_type": "Ürün Özelliği",
            "fact_text": sentence[:400],
            "strategic_relevance": (
                "Mevduat ve hesap özellikleri KOBİ işletme bakiyesi kazanımı ve ana banka olma hedefi açısından önemlidir."
            ),
            "confidence_level": "Orta",
            "open_questions": ["Faiz/oran, hesap ücreti ve dijital erişilebilirlik detaylarını doğrula."],
        }
    if any(term in lower for term in ["mobil", "internet", "dijital", "başvuru"]):
        return {
            "product_area": "Dijital KOBİ Yolculuğu",
            "benchmark_dimension": "Dijital KOBİ Yolculuğu",
            "fact_type": "Dijital Yetkinlik",
            "fact_text": sentence[:400],
            "strategic_relevance": (
                "Dijital başvuru ve servis yetkinlikleri KOBİ edinim sürtünmesini azaltır ve BD ölçeklenmesini destekler."
            ),
            "confidence_level": "Orta",
            "open_questions": ["Yolculuğun tamamen dijital mi yoksa şube tamamlaması gerektirip gerektirmediğini kontrol et."],
        }
    return None


def dry_run_facts(row: pd.Series, cleaned_text: str) -> list[dict]:
    sentences = []
    for raw in cleaned_text.replace("\n", ". ").split("."):
        sentence = " ".join(raw.split()).strip()
        if 45 <= len(sentence) <= 420:
            sentences.append(sentence)

    facts = []
    seen = set()
    for sentence in sentences:
        fact = infer_fact_from_sentence(sentence)
        if not fact:
            continue
        key = fact["fact_text"].lower()
        if key in seen:
            continue
        seen.add(key)
        if row.get("tier") == "Tier 1":
            fact["confidence_level"] = "Yüksek"
        facts.append(fact)
        if len(facts) >= 5:
            break

    if not facts and len(cleaned_text) >= MIN_TEXT_CHARS:
        facts.append(
            {
                "product_area": "Diğer",
                "benchmark_dimension": "BD Kullanılabilirliği",
                "fact_type": "Açık Soru",
                "fact_text": f"{row.get('source_name', row.get('source_id'))} için analist incelemesi gerekli.",
                "strategic_relevance": "Dry-run yer tutucusu; analist temizlenmiş kaynak metni incelemelidir.",
                "confidence_level": "Düşük",
                "open_questions": ["LLM olmadan deterministik benchmark bulgusu tespit edilemedi."],
            }
        )
    return facts


def normalize_payload(payload: dict) -> list[dict]:
    raw_facts = payload.get("facts", []) if isinstance(payload, dict) else []
    normalized = []
    seen = set()
    for fact in raw_facts:
        if not isinstance(fact, dict):
            continue
        fact_text = str(fact.get("fact_text", "")).strip()
        if not fact_text:
            continue
        key = fact_text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "product_area": coerce(
                    to_tr(fact.get("product_area", "")), ALLOWED_PRODUCT_AREAS, "Diğer"
                ),
                "benchmark_dimension": coerce(
                    to_tr(fact.get("benchmark_dimension", "")), ALLOWED_DIMENSIONS, "BD Kullanılabilirliği"
                ),
                "fact_type": coerce(to_tr(fact.get("fact_type", "")), ALLOWED_FACT_TYPES, "Diğer"),
                "fact_text": to_tr(fact_text)[:500],
                "strategic_relevance": to_tr(str(fact.get("strategic_relevance", "")).strip()),
                "confidence_level": coerce(
                    to_tr(fact.get("confidence_level", "")), ALLOWED_CONFIDENCE, "Düşük"
                ),
                "open_questions": to_tr(fact.get("open_questions", [])),
            }
        )
    return normalized


def parse_json_response(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start : end + 1])
        raise


def call_llm(row: pd.Series, cleaned_text: str, api_key: str, model: str) -> dict:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    client = OpenAI(api_key=api_key)
    prompt = PROMPT_TEMPLATE.format(
        tier=row["tier"],
        institution_name=row["institution_name"],
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
            return parse_json_response(response.choices[0].message.content)
        except Exception as exc:
            last_error = exc
            logging.warning("Benchmark fact LLM attempt %s failed for %s: %s", attempt + 1, row["document_id"], exc)
    ERROR_DIR.mkdir(exist_ok=True)
    (ERROR_DIR / f"{row['document_id']}_benchmark_fact_error.txt").write_text(str(last_error), encoding="utf-8")
    raise last_error


def build_fact_row(row: pd.Series, fact: dict, index: int) -> dict:
    return {
        "fact_id": fact_id_for(row["document_id"], index, fact["fact_text"]),
        "document_id": row["document_id"],
        "source_id": row["source_id"],
        "tier": row["tier"],
        "institution_id": row["institution_id"],
        "institution_name": row["institution_name"],
        "source_type": row["source_type"],
        "product_area": fact["product_area"],
        "benchmark_dimension": fact["benchmark_dimension"],
        "fact_type": fact["fact_type"],
        "fact_text": fact["fact_text"],
        "strategic_relevance": fact["strategic_relevance"],
        "confidence_level": fact["confidence_level"],
        "extracted_facts_json": json.dumps([fact["fact_text"]], ensure_ascii=False),
        "open_questions_json": json.dumps(fact.get("open_questions", []), ensure_ascii=False),
        "source_url": row["url"],
        "extracted_at": now_iso(),
        "llm_model": row.get("_llm_model", "dry-run"),
        "review_status": "Pending",
    }


def candidate_documents(source_ids: list[str] | None = None) -> pd.DataFrame:
    metadata = pd.read_csv(METADATA_PATH, encoding="utf-8-sig")
    registry = pd.read_csv(REGISTRY_PATH, encoding="utf-8-sig")[
        ["source_id", "source_type", "extraction_mode"]
    ]
    if "change_status" not in metadata.columns:
        metadata["change_status"] = metadata["status"]
    merged = metadata.merge(registry, on="source_id", how="left")
    candidates = merged[
        merged["status"].eq("fetched")
        & merged["change_status"].isin(["new_source", "changed"])
        & merged["extraction_mode"].isin(["benchmark_fact", "both"])
    ].copy()
    if source_ids:
        candidates = candidates[candidates["source_id"].isin(source_ids)]
    candidates = candidates.sort_values(["source_id", "fetched_at"])
    candidates = candidates.groupby("source_id", as_index=False).tail(1)
    if source_ids:
        order = {source_id: index for index, source_id in enumerate(source_ids)}
        candidates["_source_order"] = candidates["source_id"].map(order).fillna(999)
        candidates = candidates.sort_values(["_source_order", "source_id"]).drop(columns=["_source_order"])
    else:
        candidates = candidates.sort_values("source_id")
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract benchmark facts from changed curated sources.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Force local dry-run extraction.")
    parser.add_argument("--force", action="store_true", help="Reprocess already extracted document_id values.")
    parser.add_argument(
        "--source-ids",
        default="",
        help="Optional comma-separated source IDs for targeted testing, e.g. REG-005,REG-001.",
    )
    args = parser.parse_args()

    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")

    api_key = os.getenv("LEGACY_LLM_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    force_dry_run = args.dry_run or not api_key
    source_ids = [item.strip() for item in args.source_ids.split(",") if item.strip()]

    candidates = candidate_documents(source_ids or None)
    if args.limit is not None:
        candidates = candidates.head(args.limit)

    logging.info("Benchmark fact candidate documents: %s", len(candidates))
    logging.info("Extraction mode: %s", "dry-run" if force_dry_run else model)

    existing = read_facts()
    existing_fact_ids = set(existing["fact_id"].dropna()) if not existing.empty else set()
    existing_document_ids = set(existing["document_id"].dropna()) if not existing.empty else set()
    new_rows = []

    for _, row in candidates.iterrows():
        if not args.force and row["document_id"] in existing_document_ids:
            logging.info("Skipping already processed document %s", row["document_id"])
            continue
        cleaned_text = read_cleaned_text(ROOT_DIR, row.get("cleaned_text_path", ""))
        if len(cleaned_text) < MIN_TEXT_CHARS:
            logging.info("Skipping short document %s", row["document_id"])
            continue

        if force_dry_run:
            facts = dry_run_facts(row, cleaned_text)
            row["_llm_model"] = "dry-run"
        else:
            try:
                facts = normalize_payload(call_llm(row, cleaned_text, api_key, model))
                row["_llm_model"] = model
            except Exception as exc:
                logging.warning("LLM extraction failed for %s: %s", row["document_id"], exc)
                facts = dry_run_facts(row, cleaned_text)
                row["_llm_model"] = "llm-error-dry-run"

        for index, fact in enumerate(normalize_payload({"facts": facts}), start=1):
            fact_row = build_fact_row(row, fact, index)
            if fact_row["fact_id"] in existing_fact_ids:
                continue
            new_rows.append(fact_row)

    updated = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    updated = updated.reindex(columns=FACT_COLUMNS)
    updated.to_csv(FACTS_PATH, index=False, encoding="utf-8-sig")
    logging.info("Documents processed: %s", len(candidates))
    logging.info("New facts extracted: %s", len(new_rows))
    logging.info("Total facts stored: %s", len(updated))


if __name__ == "__main__":
    main()
