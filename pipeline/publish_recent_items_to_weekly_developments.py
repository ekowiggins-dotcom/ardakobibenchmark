from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
QUEUE_PATH = DATA_DIR / "recent_item_review_queue.csv"
SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"
WEEKLY_PATH = DATA_DIR / "weekly_developments.csv"

WEEKLY_COLUMNS = [
    "development_id",
    "date",
    "institution_id",
    "institution_name",
    "headline",
    "strategic_theme",
    "product_area",
    "development_type",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "source_id",
    "analyst_note",
    "tags",
    "summary_id",
    "recent_item_id",
    "cluster_id",
    "related_item_ids",
    "source_urls",
    "source_url",
    "item_url",
    "section",
    "published_at",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def parse_item_date_to_iso(value: object, institution_name: object = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if slash_match:
        first, second, year = [int(part) for part in slash_match.groups()]
        institution = str(institution_name or "").strip().casefold()
        month_first = institution in {"visa", "mastercard"}
        if first > 12:
            day, month = first, second
        elif second > 12:
            month, day = first, second
        elif month_first:
            month, day = first, second
        else:
            day, month = first, second
        try:
            return pd.Timestamp(year=year, month=month, day=day).date().isoformat()
        except ValueError:
            return text
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.notna(parsed):
        return parsed.date().isoformat()
    return text


def read_weekly() -> pd.DataFrame:
    weekly = pd.read_csv(WEEKLY_PATH, encoding="utf-8-sig") if WEEKLY_PATH.exists() else pd.DataFrame()
    for column in WEEKLY_COLUMNS:
        if column not in weekly.columns:
            weekly[column] = ""
    return weekly.reindex(columns=WEEKLY_COLUMNS)


def best_date(row: pd.Series) -> str:
    item_date = str(row.get("item_date", "") or "").strip()
    if item_date:
        return parse_item_date_to_iso(item_date, row.get("institution_name", ""))
    created = pd.to_datetime(row.get("created_at", ""), errors="coerce")
    if pd.notna(created):
        return created.date().isoformat()
    return pd.Timestamp.utcnow().date().isoformat()


def publish_approved_recent_items() -> int:
    if not QUEUE_PATH.exists() or not SUMMARIES_PATH.exists():
        raise FileNotFoundError("Önce recent item summary ve review queue oluşturulmalı.")

    queue = pd.read_csv(QUEUE_PATH, encoding="utf-8-sig")
    summaries = pd.read_csv(SUMMARIES_PATH, encoding="utf-8-sig")
    weekly = read_weekly()

    approved = queue[queue["review_status"].eq("Onaylandı")].copy()
    approved = approved.merge(
        summaries,
        on=["summary_id", "recent_item_id", "document_id", "source_id", "institution_name", "item_title", "item_date", "item_url"],
        how="left",
        suffixes=("_review", ""),
    )

    existing_development_ids = set(weekly["development_id"].dropna().astype(str))
    existing_summary_ids = set(weekly["summary_id"].dropna().astype(str))
    existing_recent_item_ids = set(weekly["recent_item_id"].dropna().astype(str))
    new_rows = []
    published_at = pd.Timestamp.utcnow().isoformat()

    for _, row in approved.iterrows():
        if pd.isna(row.get("summary_id")):
            continue
        development_id = f"DEV-{row['summary_id']}"
        if (
            development_id in existing_development_ids
            or str(row["summary_id"]) in existing_summary_ids
            or str(row["recent_item_id"]) in existing_recent_item_ids
        ):
            continue

        analyst_note = str(row.get("review_notes", "") or "").strip()
        if not analyst_note:
            analyst_note = str(row.get("analyst_note", "") or "").strip()
        if not analyst_note:
            analyst_note = "Analist onayından geçmiş tekil gelişme özeti."

        new_rows.append(
            {
                "development_id": development_id,
                "date": best_date(row),
                "institution_id": row.get("institution_id", ""),
                "institution_name": row.get("institution_name", ""),
                "headline": row.get("headline", ""),
                "strategic_theme": row.get("strategic_theme", ""),
                "product_area": row.get("product_area", ""),
                "development_type": row.get("development_type", ""),
                "summary": row.get("summary", ""),
                "core_assessment": row.get("core_assessment", ""),
                "strategic_relevance": row.get("strategic_relevance", ""),
                "impact_on_us": row.get("impact_on_us", ""),
                "recommended_action": row.get("recommended_action", ""),
                "importance_level": row.get("importance_level", ""),
                "source_id": row.get("source_id", ""),
                "analyst_note": analyst_note,
                "tags": (
                    f"recent_item_flow;summary_id:{row['summary_id']};"
                    f"recent_item_id:{row['recent_item_id']};confidence:{row.get('confidence_level', '')}"
                ),
                "summary_id": row.get("summary_id", ""),
                "recent_item_id": row.get("recent_item_id", ""),
                "cluster_id": "",
                "related_item_ids": "",
                "source_urls": "",
                "source_url": row.get("source_url", ""),
                "item_url": row.get("item_url", ""),
                "section": "Stratejik / BD Gelişmeleri",
                "published_at": published_at,
            }
        )

    updated = pd.concat([weekly, pd.DataFrame(new_rows)], ignore_index=True)
    updated = updated.reindex(columns=WEEKLY_COLUMNS)
    updated.to_csv(WEEKLY_PATH, index=False, encoding="utf-8-sig")
    return len(new_rows)


def main() -> None:
    published_count = publish_approved_recent_items()
    queue = pd.read_csv(QUEUE_PATH, encoding="utf-8-sig") if QUEUE_PATH.exists() else pd.DataFrame()
    approved_count = int(queue["review_status"].eq("Onaylandı").sum()) if "review_status" in queue.columns else 0
    logging.info("Approved recent items found: %s", approved_count)
    logging.info("Published recent items: %s", published_count)


if __name__ == "__main__":
    main()
