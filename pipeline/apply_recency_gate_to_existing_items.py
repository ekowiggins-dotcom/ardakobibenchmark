from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARCHIVE_DIR = DATA_DIR / "archive"
sys.path.insert(0, str(ROOT_DIR))

from utils.date_utils import extract_date_semantics
from utils.development_classifier import classify_actual_development
from utils.recency import bool_from_env, evaluate_recency, resolve_start_date

ITEMS_PATH = DATA_DIR / "recent_items.csv"
SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"
QUEUE_PATH = DATA_DIR / "recent_item_review_queue.csv"
RECENT_ARCHIVE_PATH = DATA_DIR / "recent_item_archive.csv"
WEEKLY_PATH = DATA_DIR / "weekly_developments.csv"

GATE_COLUMNS = [
    "publication_date",
    "announcement_date",
    "campaign_start_date",
    "campaign_end_date",
    "event_date_type",
    "recency_basis_date",
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def read_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame()


def write_archive(df: pd.DataFrame, prefix: str, timestamp: str) -> str:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    path = ARCHIVE_DIR / f"{prefix}_{timestamp}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path.relative_to(ROOT_DIR))


def truthy(value) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "evet"}


def enrich_items(
    items: pd.DataFrame,
    start_date: str,
    allow_undated: bool,
    allow_low_date_confidence: bool,
    allow_end_date_recency: bool,
) -> pd.DataFrame:
    out = items.copy()
    for column in GATE_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    for column in ["item_title", "item_text", "item_url", "item_date", "detected_at", "source_type", "item_quality", "source_url", "extraction_method"]:
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

        if not str(row.get("development_candidate_type", "") or "").strip():
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


def valid_mask(
    items: pd.DataFrame,
    start_date: str,
    allow_undated: bool,
    allow_low_date_confidence: bool,
    allow_end_date_recency: bool,
) -> pd.Series:
    mask = []
    for _, row in items.iterrows():
        recency = evaluate_recency(
            row,
            start_date,
            allow_undated=allow_undated,
            allow_low_confidence=allow_low_date_confidence,
            allow_end_date_recency=allow_end_date_recency,
        )
        quality_ok = str(row.get("item_quality", "")).strip() in {"Good", "Medium"}
        actual_ok = truthy(row.get("is_actual_development", ""))
        url_ok = str(row.get("item_url", "")).strip() != str(row.get("source_url", "")).strip()
        method_ok = str(row.get("extraction_method", "")).strip() != "fallback_source_page"
        mask.append(bool(recency["is_recent"]) and quality_ok and actual_ok and url_ok and method_ok)
    return pd.Series(mask, index=items.index)


def remove_linked_rows(df: pd.DataFrame, invalid_item_ids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty or "recent_item_id" not in df.columns:
        return df, pd.DataFrame(columns=df.columns)
    mask = df["recent_item_id"].astype(str).isin(invalid_item_ids)
    return df[~mask].copy(), df[mask].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply recency/accuracy gate to existing recent item files.")
    parser.add_argument("--start-date", default=None, help="Recent-development kesim tarihi, örn. 2026-05-01.")
    parser.add_argument("--allow-undated", action="store_true", help="Tarihsiz adayları manuel izinle geçir.")
    parser.add_argument("--allow-low-date-confidence", action="store_true", help="Düşük tarih güvenli adayları geçir.")
    parser.add_argument("--allow-end-date-recency", action="store_true", help="Sadece kampanya bitiş tarihi bulunan adayları manuel izinle geçir.")
    parser.add_argument("--include-published", action="store_true", help="weekly_developments içinde yayınlanmış maddelere bağlı aktif satırları da arşivle.")
    args = parser.parse_args()

    start_date = resolve_start_date(args.start_date)
    allow_undated = args.allow_undated or bool_from_env("ALLOW_UNDATED_RECENT_ITEMS", False)
    allow_low_date_confidence = args.allow_low_date_confidence or bool_from_env("ALLOW_LOW_DATE_CONFIDENCE", False)
    allow_end_date_recency = args.allow_end_date_recency or bool_from_env("ALLOW_END_DATE_RECENCY", False)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    items = read_csv(ITEMS_PATH)
    if items.empty:
        logging.info("recent_items.csv empty or missing.")
        return

    items = enrich_items(items, start_date, allow_undated, allow_low_date_confidence, allow_end_date_recency)
    valid = valid_mask(items, start_date, allow_undated, allow_low_date_confidence, allow_end_date_recency)

    published_ids: set[str] = set()
    weekly = read_csv(WEEKLY_PATH)
    if not weekly.empty and "recent_item_id" in weekly.columns and not args.include_published:
        published_ids = set(weekly["recent_item_id"].dropna().astype(str))

    invalid = items[~valid].copy()
    if published_ids:
        published_invalid_mask = invalid["recent_item_id"].astype(str).isin(published_ids)
        preserved_published = invalid[published_invalid_mask].copy()
        invalid = invalid[~published_invalid_mask].copy()
        active_items = pd.concat([items[valid].copy(), preserved_published], ignore_index=True)
    else:
        active_items = items[valid].copy()

    invalid_ids = set(invalid["recent_item_id"].dropna().astype(str))

    archived_paths = []
    if not invalid.empty:
        archived_paths.append(write_archive(invalid, "non_recent_recent_items", timestamp))
    active_items.to_csv(ITEMS_PATH, index=False, encoding="utf-8-sig")

    for path, prefix in [
        (SUMMARIES_PATH, "non_recent_recent_item_summaries"),
        (QUEUE_PATH, "non_recent_recent_item_review_queue"),
        (RECENT_ARCHIVE_PATH, "non_recent_recent_item_archive"),
    ]:
        df = read_csv(path)
        active_df, removed_df = remove_linked_rows(df, invalid_ids)
        if not removed_df.empty:
            archived_paths.append(write_archive(removed_df, prefix, timestamp))
        if path.exists() or not active_df.empty:
            active_df.to_csv(path, index=False, encoding="utf-8-sig")

    logging.info("Recency cutoff: %s", start_date)
    logging.info("Active items retained: %s", len(active_items))
    logging.info("Invalid items archived: %s", len(invalid))
    only_end_date = invalid[
        invalid.get("campaign_end_date", pd.Series("", index=invalid.index)).astype(str).str.strip().ne("")
        & invalid.get("publication_date", pd.Series("", index=invalid.index)).astype(str).str.strip().eq("")
        & invalid.get("announcement_date", pd.Series("", index=invalid.index)).astype(str).str.strip().eq("")
        & invalid.get("campaign_start_date", pd.Series("", index=invalid.index)).astype(str).str.strip().eq("")
    ]
    logging.info("Rejected because only campaign_end_date existed: %s", len(only_end_date))
    logging.info("Active old campaigns detected: %s", int(items.get("is_active_campaign", pd.Series(False, index=items.index)).astype(str).str.casefold().isin(["true", "1", "yes", "evet"]).sum()))
    logging.info("Published invalid items preserved: %s", len(published_ids & set(items['recent_item_id'].astype(str))) if published_ids else 0)
    for archived_path in archived_paths:
        logging.info("Archived file: %s", archived_path)


if __name__ == "__main__":
    main()
