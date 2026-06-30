from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
EXTRACTIONS_PATH = DATA_DIR / "llm_extractions.csv"
REVIEW_QUEUE_PATH = DATA_DIR / "review_queue.csv"
WEEKLY_PATH = DATA_DIR / "weekly_developments.csv"

WEEKLY_COLUMNS = [
    "development_id",
    "date",
    "institution_id",
    "headline",
    "strategic_theme",
    "product_area",
    "development_type",
    "summary",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "source_id",
    "analyst_note",
    "tags",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    queue = pd.read_csv(REVIEW_QUEUE_PATH, encoding="utf-8-sig")
    extractions = pd.read_csv(EXTRACTIONS_PATH, encoding="utf-8-sig")
    weekly = pd.read_csv(WEEKLY_PATH, encoding="utf-8-sig")

    approved = queue[queue["review_status"].eq("Approved")]
    approved_extractions = approved.merge(extractions, on="extraction_id", how="left", suffixes=("_review", ""))

    existing_keys = set(weekly["development_id"].astype(str))
    existing_tags = ";".join(weekly.get("tags", pd.Series(dtype=str)).fillna("").astype(str).tolist())
    new_rows = []

    for _, row in approved_extractions.iterrows():
        if pd.isna(row.get("document_id")):
            continue
        development_id = f"AUTO-{row['extraction_id']}"
        duplicate_token = f"document_id:{row['document_id']}"
        if development_id in existing_keys or duplicate_token in existing_tags:
            continue
        if row.get("development_type") == "No Relevant Development":
            continue

        analyst_note = row.get("review_notes", "")
        if not analyst_note:
            analyst_note = "Onaylı LLM destekli taslak; analist doğrulaması için kaynak metni saklanmalıdır."

        new_rows.append(
            {
                "development_id": development_id,
                "date": datetime.now(timezone.utc).date().isoformat(),
                "institution_id": row["institution_id"],
                "headline": row["headline"],
                "strategic_theme": row["strategic_theme"],
                "product_area": row["product_area"],
                "development_type": row["development_type"],
                "summary": row["summary"],
                "strategic_relevance": row["strategic_relevance"],
                "impact_on_us": row["impact_on_us"],
                "recommended_action": row["recommended_action"],
                "importance_level": row["importance_level"],
                "source_id": row["source_id"],
                "analyst_note": analyst_note,
                "tags": (
                    f"auto_published;extraction_id:{row['extraction_id']};"
                    f"document_id:{row['document_id']};confidence:{row['confidence_level']}"
                ),
            }
        )

    if new_rows:
        updated = pd.concat([weekly, pd.DataFrame(new_rows)], ignore_index=True)
    else:
        updated = weekly
    updated = updated.reindex(columns=WEEKLY_COLUMNS)
    updated.to_csv(WEEKLY_PATH, index=False, encoding="utf-8-sig")
    logging.info("Published %s approved developments", len(new_rows))


if __name__ == "__main__":
    main()
