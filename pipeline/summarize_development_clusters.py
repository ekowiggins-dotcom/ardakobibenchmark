from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(ROOT_DIR))

from utils.llm_client import MissingApiKeyError, get_llm_config, summarize_with_anthropic
from utils.language_lint import lint_llm_language
from utils.recent_mvp import parse_json_list

CLUSTERS_PATH = DATA_DIR / "development_clusters.csv"
ITEMS_PATH = DATA_DIR / "recent_items.csv"
SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"

SYNTHESIS_COLUMNS = [
    "why_it_matters",
    "competitor_intent",
    "management_takeaway",
    "extracted_facts_json",
    "llm_model",
    "error_message",
    "language_lint_score",
    "language_lint_warnings",
    "needs_language_review",
]

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

PROMPT_TEMPLATE = """Sen Akbank KOBİ için çalışan kıdemli bir rekabet istihbaratı analistisin.

Aşağıda aynı kurumdan gelen ve muhtemelen aynı stratejik paterne ait birkaç gelişme var.

Görevin:
Tek tek haberleri tekrar etmek yerine, bu gelişmelerin birlikte ne anlattığını yaz.
Bu bir rakip stratejisi sinyali mi, yoksa tesadüfi/dağınık PR mı?
Kısa, net ve yöneticiye uygun yaz.

Kurum:
{institution_name}

Gelişmeler:
{cluster_items}

Kurallar:

* Türkçe yaz.
* Basit ve doğrudan yaz.
* PR dili kullanma.
* Kurumsal rapor dili kullanma.
* Danışmanlık dili kullanma.
* Cümleleri kısa tut.
* Aktif fiil kullan.
* "-maktadır/-mektedir" kullanma.
* "gereklidir", "edilmelidir", "değerlendirilmelidir" kullanma.
* "bulunmamaktadır", "sunmaktadır", "göstermektedir", "yansıtmaktadır" kullanma.
* "teşkil etmektedir", "önem arz etmektedir" gibi ifadeler kullanma.
* "açısından" ve "kapsamında" kelimelerini mümkünse kullanma.
* "doğrudan rakip hamle" gibi kalıplardan kaçın.
* Tekil kampanyaları abartma.
* Birden fazla küçük kampanya birlikte anlamlı bir patern oluşturuyorsa bunu açıkça söyle.
* Eğer patern zayıfsa “tekil/taktik kampanyalar; güçlü stratejik sinyal değil” de.
* Akbank için pratik sonucu açık söyle.
* Sadece JSON döndür.

JSON şeması:
{{
"cluster_title": "",
"cluster_summary": "",
"cluster_core_assessment": "",
"why_it_matters": "",
"competitor_intent": "",
"recommended_action": "",
"impact_on_us": "",
"importance_level": "",
"confidence_level": "",
"management_takeaway": "",
"extracted_facts": []
}}
"""

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def read_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame()


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
    repair_prompt = "Aşağıdaki metni geçerli JSON formatına çevir. Sadece JSON döndür.\n\n" f"{raw_text}"
    return summarize_with_anthropic(repair_prompt, model=model, max_tokens=1200)


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
    raw = summarize_with_anthropic(rewrite_prompt, model=model, max_tokens=1200)
    try:
        return parse_json_response(raw), raw
    except json.JSONDecodeError:
        repaired = repair_json_response(raw, model)
        return parse_json_response(repaired), repaired


def coerce(value, allowed: set[str], fallback: str) -> str:
    raw = str(value or "").strip()
    return raw if raw in allowed else fallback


def clean_text(value: str, max_chars: int = 800) -> str:
    text = " ".join(str(value or "").split())
    return text[:max_chars]


def build_cluster_items(row: pd.Series, items: pd.DataFrame, summaries: pd.DataFrame) -> str:
    item_ids = parse_json_list(row.get("item_ids", ""))
    if not item_ids:
        return str(row.get("item_titles", ""))
    selected = items[items["recent_item_id"].astype(str).isin(item_ids)].copy()
    selected = selected.merge(
        summaries[["recent_item_id", "headline", "summary", "core_assessment", "strategic_theme", "product_area", "development_type"]],
        on="recent_item_id",
        how="left",
    )
    lines = []
    for _, item in selected.iterrows():
        lines.append(
            "\n".join(
                [
                    f"- Başlık: {clean_text(item.get('item_title', ''))}",
                    f"  Tarih: {clean_text(item.get('recency_basis_date', item.get('normalized_item_date', '')))}",
                    f"  Tema/ürün: {clean_text(item.get('strategic_theme', ''))} / {clean_text(item.get('product_area', ''))}",
                    f"  Özet: {clean_text(item.get('summary', ''))}",
                    f"  Kısa değerlendirme: {clean_text(item.get('core_assessment', ''))}",
                    f"  URL: {clean_text(item.get('item_url', ''))}",
                ]
            )
        )
    return "\n".join(lines)


def fallback_payload(row: pd.Series, reason: str) -> dict:
    return {
        "cluster_title": row.get("cluster_title", ""),
        "cluster_summary": row.get("cluster_summary", ""),
        "cluster_core_assessment": row.get("cluster_core_assessment", ""),
        "why_it_matters": "Küme sentezi için analist kontrolü gerekli.",
        "competitor_intent": "Henüz model tarafından sentezlenmedi.",
        "recommended_action": row.get("recommended_action", "İzle"),
        "impact_on_us": row.get("impact_on_us", "Orta"),
        "importance_level": row.get("importance_level", "Orta"),
        "confidence_level": row.get("confidence_level", "Düşük"),
        "management_takeaway": row.get("cluster_core_assessment", ""),
        "extracted_facts": parse_json_list(row.get("item_titles", "")),
        "error_message": reason,
    }


def normalize_payload(payload: dict, fallback: dict) -> dict:
    return {
        "cluster_title": clean_text(payload.get("cluster_title") or fallback["cluster_title"], 140),
        "cluster_summary": clean_text(payload.get("cluster_summary") or fallback["cluster_summary"], 400),
        "cluster_core_assessment": clean_text(payload.get("cluster_core_assessment") or fallback["cluster_core_assessment"], 420),
        "why_it_matters": clean_text(payload.get("why_it_matters") or fallback["why_it_matters"], 500),
        "competitor_intent": clean_text(payload.get("competitor_intent") or fallback["competitor_intent"], 400),
        "recommended_action": coerce(payload.get("recommended_action"), ALLOWED_ACTIONS, fallback["recommended_action"]),
        "impact_on_us": coerce(payload.get("impact_on_us"), ALLOWED_LEVELS, fallback["impact_on_us"]),
        "importance_level": coerce(payload.get("importance_level"), ALLOWED_LEVELS, fallback["importance_level"]),
        "confidence_level": coerce(payload.get("confidence_level"), ALLOWED_LEVELS, fallback["confidence_level"]),
        "management_takeaway": clean_text(payload.get("management_takeaway") or fallback["management_takeaway"], 400),
        "extracted_facts": payload.get("extracted_facts") if isinstance(payload.get("extracted_facts"), list) else fallback["extracted_facts"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster-level Claude synthesis.")
    parser.add_argument("--include-singletons", action="store_true", help="item_count=1 kümeleri de sentezle.")
    parser.add_argument("--force", action="store_true", help="Mevcut küme sentezlerini tekrar oluştur.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
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
    args = parser.parse_args()

    clusters = read_csv(CLUSTERS_PATH)
    items = read_csv(ITEMS_PATH)
    summaries = read_csv(SUMMARIES_PATH)
    if clusters.empty:
        logging.info("Clusters read: 0")
        logging.info("Cluster summaries created: 0")
        return
    for column in SYNTHESIS_COLUMNS:
        if column not in clusters.columns:
            clusters[column] = ""
        clusters[column] = clusters[column].astype("object")

    config = get_llm_config()
    dry_run = args.dry_run or not config.has_api_key or config.provider != "anthropic"
    candidates = clusters.copy()
    if not args.include_singletons:
        candidates = candidates[pd.to_numeric(candidates["item_count"], errors="coerce").fillna(0) >= 2]
    if not args.force:
        candidates = candidates[candidates["why_it_matters"].astype(str).str.strip().eq("")]
    if args.limit is not None:
        candidates = candidates.head(args.limit)

    created = 0
    parse_failures = 0
    deterministic_fallbacks = 0
    rewrite_attempts = 0
    rewrite_failures = 0
    for idx, row in candidates.iterrows():
        fallback = fallback_payload(row, "Kuru çalışma veya eksik Claude kimlik bilgisi nedeniyle sentez oluşturulmadı.")
        payload = fallback
        model = "dry-run"
        error_message = fallback["error_message"]
        if not dry_run:
            try:
                prompt = PROMPT_TEMPLATE.format(
                    institution_name=row.get("institution_name", ""),
                    cluster_items=build_cluster_items(row, items, summaries),
                )
                raw = summarize_with_anthropic(prompt, model=config.model, max_tokens=1400)
                try:
                    parsed = parse_json_response(raw)
                except json.JSONDecodeError:
                    repaired = repair_json_response(raw, config.model)
                    parsed = parse_json_response(repaired)
                payload = normalize_payload(parsed, fallback)
                model = config.model
                error_message = ""
            except json.JSONDecodeError:
                deterministic_fallbacks += 1
                fallback = fallback_payload(row, "Claude JSON çıktısı onarılamadı; deterministik küme sentezi kullanıldı.")
                payload = normalize_payload(fallback, fallback)
                model = "deterministic-fallback-after-json-parse"
                error_message = ""
            except MissingApiKeyError:
                payload = normalize_payload(fallback, fallback)
            except Exception as exc:
                payload = normalize_payload(fallback, fallback)
                model = "llm-error-dry-run"
                error_message = str(exc)[:500]
        else:
            payload = normalize_payload(fallback, fallback)

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
                rewritten_payload, _ = rewrite_artificial_language(payload, config.model)
                payload = normalize_payload(rewritten_payload, payload)
                lint_result = lint_llm_language(payload)
            except Exception as exc:
                rewrite_failures += 1
                logging.warning("Cluster language rewrite failed for %s: %s", row.get("cluster_id", ""), type(exc).__name__)
                break

        for column in ["cluster_title", "cluster_summary", "cluster_core_assessment", "recommended_action", "impact_on_us", "importance_level", "confidence_level"]:
            clusters.at[idx, column] = payload[column]
        clusters.at[idx, "why_it_matters"] = payload["why_it_matters"]
        clusters.at[idx, "competitor_intent"] = payload["competitor_intent"]
        clusters.at[idx, "management_takeaway"] = payload["management_takeaway"]
        clusters.at[idx, "extracted_facts_json"] = json.dumps(payload["extracted_facts"], ensure_ascii=False)
        clusters.at[idx, "llm_model"] = model
        clusters.at[idx, "error_message"] = error_message
        clusters.at[idx, "language_lint_score"] = int(lint_result.get("language_lint_score", 0))
        clusters.at[idx, "language_lint_warnings"] = json.dumps(lint_result.get("language_lint_warnings", []), ensure_ascii=False)
        clusters.at[idx, "needs_language_review"] = bool(lint_result.get("needs_language_review", False))
        created += 1

    clusters.to_csv(CLUSTERS_PATH, index=False, encoding="utf-8-sig")
    logging.info("Clusters read: %s", len(clusters))
    logging.info("Cluster summaries created: %s", created)
    logging.info("JSON parse failures: %s", parse_failures)
    logging.info("Deterministic cluster fallbacks used: %s", deterministic_fallbacks)
    logging.info("Language rewrite attempts: %s", rewrite_attempts)
    logging.info("Language rewrite failures: %s", rewrite_failures)


if __name__ == "__main__":
    main()
