from __future__ import annotations

import hashlib
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(ROOT_DIR))

from utils.triage import TRIAGE_MANAGEMENT_AWARENESS, triage_recent_item_summary

SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"
QUEUE_PATH = DATA_DIR / "recent_item_review_queue.csv"
AWARENESS_PATH = DATA_DIR / "management_awareness_queue.csv"
ARCHIVE_PATH = DATA_DIR / "recent_item_archive.csv"
ITEMS_PATH = DATA_DIR / "recent_items.csv"

QUEUE_COLUMNS = [
    "review_id",
    "summary_id",
    "recent_item_id",
    "document_id",
    "source_id",
    "institution_name",
    "item_title",
    "item_date",
    "strategic_theme",
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "confidence_level",
    "cluster_id",
    "cluster_status",
    "covered_by_cluster",
    "suppress_individual_review",
    "suppression_reason",
    "item_url",
    "source_url",
    "review_status",
    "reviewer",
    "review_notes",
    "approved_at",
    "analyst_note",
    "reviewed_at",
]

MANAGEMENT_AWARENESS_COLUMNS = [
    "awareness_id",
    "summary_id",
    "recent_item_id",
    "institution_name",
    "item_title",
    "item_date",
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "confidence_level",
    "strategic_theme",
    "product_area",
    "development_type",
    "awareness_reason",
    "source_url",
    "item_url",
    "review_status",
    "analyst_note",
    "reviewer",
    "reviewed_at",
    "created_at",
]

ARCHIVE_COLUMNS = [
    "archive_id",
    "summary_id",
    "recent_item_id",
    "document_id",
    "source_id",
    "institution_name",
    "item_title",
    "item_date",
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "confidence_level",
    "triage_status",
    "triage_reason",
    "archived_at",
]

SUMMARY_CLUSTER_COLUMNS = [
    "cluster_id",
    "cluster_status",
    "covered_by_cluster",
    "suppress_individual_review",
    "suppression_reason",
]

PRESERVED_STATUSES = {"Onaylandı", "Reddedildi", "Ek Araştırma Gerekli", "Arşivlendi"}
SUPPRESS_ACTIONS = {"İzle", "BD Konuşma Notlarına Ekle", "Önceliklendirme"}
ESCALATION_ACTIONS = {"Yönetime Eskale Et", "Yanıt Geliştir", "Uyarlama Fırsatını Değerlendir"}
TACTICAL_TEXT_KEYWORDS = {
    "maxipuan",
    "maximum",
    "ticari kart",
    "ticari kredi kart",
    "ticari bankamatik",
    "yurt dışı harcama",
    "yurt disi harcama",
    "harcama kampanyası",
}
HIGH_SIGNAL_KEYWORDS = {
    "api",
    "açık bankacılık",
    "open banking",
    "ödeme iste",
    "tahsilat",
    "pos",
    "ökc",
    "okc",
    "mobil ökc",
    "hugin",
    "paygo",
    "ingenico",
    "regülasyon",
    "tcmb",
    "bddk",
    "iş birliği",
    "is birligi",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def review_id_for(summary_id: str) -> str:
    digest = hashlib.sha1(summary_id.encode("utf-8")).hexdigest()[:12]
    return f"RIRQ-{digest}"


def awareness_id_for(summary_id: str) -> str:
    digest = hashlib.sha1(summary_id.encode("utf-8")).hexdigest()[:12]
    return f"MAQ-{digest}"


def archive_id_for(recent_item_id: str, summary_id: str = "") -> str:
    stable_key = str(recent_item_id or summary_id)
    digest = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()[:12]
    return f"RIA-{digest}"


def read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path, encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=columns)
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df.reindex(columns=columns)


def normalized_csv(df: pd.DataFrame, columns: list[str]) -> str:
    normalized = df.copy()
    for column in columns:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = normalized.reindex(columns=columns).fillna("")
    for column in normalized.columns:
        normalized[column] = normalized[column].astype(str)
    return normalized.to_csv(index=False, encoding="utf-8-sig")


def write_csv_if_changed(path: Path, df: pd.DataFrame, columns: list[str]) -> bool:
    existing = read_csv(path, columns)
    if normalized_csv(existing, columns) == normalized_csv(df, columns):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    df.reindex(columns=columns).to_csv(path, index=False, encoding="utf-8-sig")
    return True


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
    return clean(value).casefold() in {"true", "1", "yes", "evet"}


def contains_any(text: str, keywords: set[str]) -> bool:
    lower = text.casefold()
    return any(keyword.casefold() in lower for keyword in keywords)


def enrich_summaries(summaries: pd.DataFrame) -> pd.DataFrame:
    out = summaries.copy()
    out = out.loc[:, ~out.columns.duplicated()].copy()
    out = out.drop(columns=[column for column in ["source_url_item", "relevance_status_item"] if column in out.columns])
    for column in SUMMARY_CLUSTER_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    if ITEMS_PATH.exists():
        items = pd.read_csv(ITEMS_PATH, encoding="utf-8-sig")
        item_cols = [col for col in ["recent_item_id", "source_url", "relevance_status", "content_role"] if col in items.columns]
        if item_cols:
            out = out.merge(items[item_cols], on="recent_item_id", how="left", suffixes=("", "_item"))
            if "source_url_item" in out.columns:
                out["source_url"] = out.get("source_url", "").fillna("")
                out["source_url"] = out["source_url"].where(out["source_url"].astype(str).str.len() > 0, out["source_url_item"].fillna(""))
            if "relevance_status_item" in out.columns:
                out["relevance_status"] = out.get("relevance_status", "").fillna("")
                out["relevance_status"] = out["relevance_status"].where(
                    out["relevance_status"].astype(str).str.len() > 0,
                    out["relevance_status_item"].fillna(""),
                )
            if "content_role_item" in out.columns:
                out["content_role"] = out.get("content_role", "").fillna("")
                out["content_role"] = out["content_role"].where(
                    out["content_role"].astype(str).str.len() > 0,
                    out["content_role_item"].fillna(""),
                )
            out = out.drop(columns=[column for column in ["source_url_item", "relevance_status_item", "content_role_item"] if column in out.columns])
    if "source_url" not in out.columns:
        out["source_url"] = ""
    if "relevance_status" not in out.columns:
        out["relevance_status"] = "Belirsiz"
    out["relevance_status"] = out["relevance_status"].fillna("").replace("", "Belirsiz")
    if "content_role" not in out.columns:
        out["content_role"] = ""
    return out


def should_suppress_individual(row: pd.Series) -> tuple[bool, str]:
    if not truthy(row.get("covered_by_cluster", "")):
        return False, ""
    if clean(row.get("cluster_status", "")) not in {"Küme İncelemede", "Küme Yayınlandı"}:
        return False, ""
    if clean(row.get("impact_on_us", "")) == "Yüksek" or clean(row.get("importance_level", "")) == "Yüksek":
        return False, ""
    if clean(row.get("recommended_action", "")) in ESCALATION_ACTIONS:
        return False, ""

    blob = " ".join(clean(row.get(column, "")) for column in ["item_title", "headline", "summary", "strategic_theme", "product_area", "development_type"])
    if contains_any(blob, HIGH_SIGNAL_KEYWORDS) and not contains_any(blob, TACTICAL_TEXT_KEYWORDS):
        return False, ""

    tactical = (
        clean(row.get("development_type", "")) == "Kampanya"
        or clean(row.get("strategic_theme", "")) == "Kampanyalar"
        or contains_any(blob, TACTICAL_TEXT_KEYWORDS)
    )
    action_ok = clean(row.get("recommended_action", "")) in SUPPRESS_ACTIONS
    impact_ok = clean(row.get("impact_on_us", "")) in {"Düşük", "Orta"}
    if tactical and action_ok and impact_ok:
        return True, "Küme review kuyruğunda; tekil taktik kampanya ana kuyruğa alınmadı"
    return False, ""


def build_queue_row(row: pd.Series) -> dict[str, str]:
    return {
        "review_id": review_id_for(str(row.get("summary_id", ""))),
        "summary_id": row.get("summary_id", ""),
        "recent_item_id": row.get("recent_item_id", ""),
        "document_id": row.get("document_id", ""),
        "source_id": row.get("source_id", ""),
        "institution_name": row.get("institution_name", ""),
        "item_title": row.get("item_title", ""),
        "item_date": row.get("item_date", ""),
        "strategic_theme": row.get("strategic_theme", ""),
        "headline": row.get("headline", ""),
        "summary": row.get("summary", ""),
        "core_assessment": row.get("core_assessment", ""),
        "strategic_relevance": row.get("strategic_relevance", ""),
        "impact_on_us": row.get("impact_on_us", ""),
        "recommended_action": row.get("recommended_action", ""),
        "confidence_level": row.get("confidence_level", ""),
        "cluster_id": row.get("cluster_id", ""),
        "cluster_status": row.get("cluster_status", "Küme Yok"),
        "covered_by_cluster": bool(truthy(row.get("covered_by_cluster", ""))),
        "suppress_individual_review": bool(truthy(row.get("suppress_individual_review", ""))),
        "suppression_reason": row.get("suppression_reason", ""),
        "item_url": row.get("item_url", ""),
        "source_url": row.get("source_url", ""),
        "review_status": "Beklemede",
        "reviewer": "",
        "review_notes": "",
        "approved_at": "",
        "analyst_note": "",
        "reviewed_at": "",
    }


def build_awareness_row(row: pd.Series, triage: dict[str, object]) -> dict[str, str]:
    summary_id = str(row.get("summary_id", ""))
    return {
        "awareness_id": awareness_id_for(summary_id),
        "summary_id": summary_id,
        "recent_item_id": row.get("recent_item_id", ""),
        "institution_name": row.get("institution_name", ""),
        "item_title": row.get("item_title", ""),
        "item_date": row.get("item_date", ""),
        "headline": row.get("headline", ""),
        "summary": row.get("summary", ""),
        "core_assessment": row.get("core_assessment", ""),
        "strategic_relevance": row.get("strategic_relevance", ""),
        "impact_on_us": row.get("impact_on_us", ""),
        "recommended_action": row.get("recommended_action", ""),
        "importance_level": row.get("importance_level", ""),
        "confidence_level": row.get("confidence_level", ""),
        "strategic_theme": row.get("strategic_theme", ""),
        "product_area": row.get("product_area", ""),
        "development_type": row.get("development_type", ""),
        "awareness_reason": str(triage.get("awareness_reason", triage.get("triage_reason", ""))),
        "source_url": row.get("source_url", ""),
        "item_url": row.get("item_url", ""),
        "review_status": "Beklemede",
        "analyst_note": "",
        "reviewer": "",
        "reviewed_at": "",
        "created_at": now_iso(),
    }


def build_archive_row(row: pd.Series, triage: dict[str, object]) -> dict[str, str]:
    summary_id = str(row.get("summary_id", ""))
    recent_item_id = str(row.get("recent_item_id", ""))
    return {
        "archive_id": archive_id_for(recent_item_id, summary_id),
        "summary_id": summary_id,
        "recent_item_id": recent_item_id,
        "document_id": row.get("document_id", ""),
        "source_id": row.get("source_id", ""),
        "institution_name": row.get("institution_name", ""),
        "item_title": row.get("item_title", ""),
        "item_date": row.get("item_date", ""),
        "headline": row.get("headline", ""),
        "summary": row.get("summary", ""),
        "core_assessment": row.get("core_assessment", ""),
        "strategic_relevance": row.get("strategic_relevance", ""),
        "impact_on_us": row.get("impact_on_us", ""),
        "recommended_action": row.get("recommended_action", ""),
        "importance_level": row.get("importance_level", ""),
        "confidence_level": row.get("confidence_level", ""),
        "triage_status": str(triage["triage_status"]),
        "triage_reason": str(triage["triage_reason"]),
        "archived_at": now_iso(),
    }


def update_existing_row(df: pd.DataFrame, idx, row_data: dict[str, str], protected: set[str]) -> None:
    for column, value in row_data.items():
        if column in protected:
            continue
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].astype("object")
        df.at[idx, column] = value


def merge_destination(existing: pd.DataFrame, new_rows: list[dict[str, str]], key_column: str, columns: list[str]) -> tuple[pd.DataFrame, int, int]:
    existing = existing.copy()
    for column in columns:
        if column not in existing.columns:
            existing[column] = ""
    existing = existing.reindex(columns=columns)
    preserved_keys = set()
    if "review_status" in existing.columns and key_column in existing.columns:
        preserved_keys = set(
            existing[existing["review_status"].astype(str).isin(PRESERVED_STATUSES)][key_column]
            .dropna()
            .astype(str)
        )
    protected = {"review_status", "reviewer", "review_notes", "approved_at", "analyst_note", "reviewed_at", "created_at"}
    by_key = {str(row[key_column]): idx for idx, row in existing.iterrows()} if key_column in existing.columns else {}
    appended = []
    keep_indices = set()
    updated = 0
    for row in new_rows:
        key = str(row.get(key_column, ""))
        if key in by_key:
            idx = by_key[key]
            update_existing_row(existing, idx, row, protected)
            keep_indices.add(idx)
            updated += 1
        else:
            appended.append(row)
    for key in preserved_keys:
        if key in by_key:
            keep_indices.add(by_key[key])
    kept = existing.loc[sorted(keep_indices)].copy() if keep_indices else pd.DataFrame(columns=columns)
    out = pd.concat([kept, pd.DataFrame(appended)], ignore_index=True).reindex(columns=columns)
    return out, len(appended), updated


def merge_archive(existing: pd.DataFrame, new_rows: list[dict[str, str]]) -> tuple[pd.DataFrame, int, int]:
    existing = existing.copy()
    for column in ARCHIVE_COLUMNS:
        if column not in existing.columns:
            existing[column] = ""
    existing = existing.reindex(columns=ARCHIVE_COLUMNS)
    by_item = {
        str(row.get("recent_item_id", "")): idx
        for idx, row in existing.iterrows()
        if str(row.get("recent_item_id", ""))
    }
    appended: list[dict[str, str]] = []
    updated = 0
    for row in new_rows:
        item_id = str(row.get("recent_item_id", ""))
        row = dict(row)
        if item_id in by_item:
            idx = by_item[item_id]
            row["archive_id"] = existing.at[idx, "archive_id"]
            row["archived_at"] = existing.at[idx, "archived_at"]
            before = existing.loc[idx, ARCHIVE_COLUMNS].fillna("").astype(str).to_dict()
            after = {column: str(row.get(column, "")) for column in ARCHIVE_COLUMNS}
            if before != after:
                update_existing_row(existing, idx, row, protected={"archived_at"})
                updated += 1
        else:
            row["archive_id"] = archive_id_for(item_id, str(row.get("summary_id", "")))
            appended.append(row)
    out = pd.concat([existing, pd.DataFrame(appended)], ignore_index=True).reindex(columns=ARCHIVE_COLUMNS)
    return out, len(appended), updated


def route_summaries(summaries: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], int]:
    out = summaries.copy()
    for column in SUMMARY_CLUSTER_COLUMNS:
        if column not in out.columns:
            out[column] = ""

    queue_rows: list[dict[str, str]] = []
    awareness_rows: list[dict[str, str]] = []
    archive_rows: list[dict[str, str]] = []
    suppressed = 0

    for idx, row in out.iterrows():
        existing_review_status = clean(row.get("review_status", ""))
        if existing_review_status in {"Arşivlendi", "Reddedildi"}:
            archive_rows.append(
                build_archive_row(
                    out.loc[idx],
                    {
                        "triage_status": existing_review_status,
                        "triage_reason": clean(row.get("suppression_reason", ""))
                        or "Önceden arşivlenmiş/reddedilmiş summary tekrar review kuyruğuna alınmadı.",
                    },
                )
            )
            continue

        suppress, reason = should_suppress_individual(row)
        if suppress:
            out.at[idx, "suppress_individual_review"] = True
            out.at[idx, "suppression_reason"] = reason
            suppressed += 1
            continue
        out.at[idx, "suppress_individual_review"] = False
        if not clean(out.at[idx, "suppression_reason"]):
            out.at[idx, "suppression_reason"] = ""

        triage = triage_recent_item_summary(out.loc[idx])
        if triage.get("should_queue_for_management_awareness"):
            awareness_rows.append(build_awareness_row(out.loc[idx], triage))
        elif triage.get("should_queue_for_review"):
            queue_rows.append(build_queue_row(out.loc[idx]))
        else:
            archive_rows.append(build_archive_row(out.loc[idx], triage))

    return out, queue_rows, awareness_rows, archive_rows, suppressed


def main() -> None:
    queue = read_csv(QUEUE_PATH, QUEUE_COLUMNS)
    awareness = read_csv(AWARENESS_PATH, MANAGEMENT_AWARENESS_COLUMNS)
    archive = read_csv(ARCHIVE_PATH, ARCHIVE_COLUMNS)

    if not SUMMARIES_PATH.exists():
        queue.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
        awareness.to_csv(AWARENESS_PATH, index=False, encoding="utf-8-sig")
        archive.to_csv(ARCHIVE_PATH, index=False, encoding="utf-8-sig")
        logging.info("Summaries read: 0")
        logging.info("Sent to review queue: 0")
        logging.info("Sent to management awareness queue: 0")
        logging.info("Archived as low priority: 0")
        logging.info("Suppressed individual review items: 0")
        return

    summaries = pd.read_csv(SUMMARIES_PATH, encoding="utf-8-sig")
    for column in SUMMARY_CLUSTER_COLUMNS:
        if column not in summaries.columns:
            summaries[column] = ""
    if summaries.empty:
        summaries.to_csv(SUMMARIES_PATH, index=False, encoding="utf-8-sig")
        queue.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
        awareness.to_csv(AWARENESS_PATH, index=False, encoding="utf-8-sig")
        archive.to_csv(ARCHIVE_PATH, index=False, encoding="utf-8-sig")
        logging.info("Summaries read: 0")
        logging.info("Sent to review queue: 0")
        logging.info("Sent to management awareness queue: 0")
        logging.info("Archived as low priority: 0")
        logging.info("Suppressed individual review items: 0")
        return

    summaries = enrich_summaries(summaries)
    updated_summaries, queue_rows, awareness_rows, archive_rows, suppressed = route_summaries(summaries)

    updated_queue, new_queue, updated_queue_count = merge_destination(queue, queue_rows, "summary_id", QUEUE_COLUMNS)
    updated_awareness, new_awareness, updated_awareness_count = merge_destination(
        awareness, awareness_rows, "summary_id", MANAGEMENT_AWARENESS_COLUMNS
    )
    updated_archive, new_archive_count, updated_archive_count = merge_archive(archive, archive_rows)

    write_csv_if_changed(SUMMARIES_PATH, updated_summaries, list(updated_summaries.columns))
    write_csv_if_changed(QUEUE_PATH, updated_queue, QUEUE_COLUMNS)
    write_csv_if_changed(AWARENESS_PATH, updated_awareness, MANAGEMENT_AWARENESS_COLUMNS)
    write_csv_if_changed(ARCHIVE_PATH, updated_archive, ARCHIVE_COLUMNS)

    logging.info("Summaries read: %s", len(updated_summaries))
    logging.info("Sent to review queue: %s", new_queue + updated_queue_count)
    logging.info("Sent to management awareness queue: %s", new_awareness + updated_awareness_count)
    logging.info("Archived as low priority: %s", new_archive_count)
    logging.info("Suppressed individual review items: %s", suppressed)
    logging.info("Skipped duplicates: %s", updated_queue_count + updated_awareness_count + updated_archive_count)


if __name__ == "__main__":
    main()
