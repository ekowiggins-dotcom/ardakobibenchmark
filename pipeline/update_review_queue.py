from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
EXTRACTIONS_PATH = DATA_DIR / "llm_extractions.csv"
REVIEW_QUEUE_PATH = DATA_DIR / "review_queue.csv"

REVIEW_COLUMNS = [
    "review_id",
    "extraction_id",
    "document_id",
    "source_id",
    "institution_name",
    "headline",
    "strategic_theme",
    "impact_on_us",
    "recommended_action",
    "confidence_level",
    "review_status",
    "reviewer",
    "review_notes",
    "approved_at",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def review_id_for(extraction_id: str) -> str:
    digest = hashlib.sha1(extraction_id.encode("utf-8")).hexdigest()[:10]
    return f"REV-{digest}"


def read_queue() -> pd.DataFrame:
    if REVIEW_QUEUE_PATH.exists():
        return pd.read_csv(REVIEW_QUEUE_PATH, encoding="utf-8-sig")
    return pd.DataFrame(columns=REVIEW_COLUMNS)


def main() -> None:
    if not EXTRACTIONS_PATH.exists():
        raise FileNotFoundError("Run run_llm_extraction.py first")

    extractions = pd.read_csv(EXTRACTIONS_PATH, encoding="utf-8-sig")
    queue = read_queue()
    existing_extraction_ids = set(queue["extraction_id"].dropna()) if not queue.empty else set()
    pending = extractions[
        extractions["review_status"].fillna("").isin(["", "Pending"])
        & ~extractions["extraction_id"].isin(existing_extraction_ids)
    ]

    new_rows = []
    for _, row in pending.iterrows():
        new_rows.append(
            {
                "review_id": review_id_for(row["extraction_id"]),
                "extraction_id": row["extraction_id"],
                "document_id": row["document_id"],
                "source_id": row["source_id"],
                "institution_name": row["institution_name"],
                "headline": row["headline"],
                "strategic_theme": row["strategic_theme"],
                "impact_on_us": row["impact_on_us"],
                "recommended_action": row["recommended_action"],
                "confidence_level": row["confidence_level"],
                "review_status": "Pending",
                "reviewer": "",
                "review_notes": "",
                "approved_at": "",
            }
        )

    updated = pd.concat([queue, pd.DataFrame(new_rows)], ignore_index=True)
    updated = updated.reindex(columns=REVIEW_COLUMNS)
    updated.to_csv(REVIEW_QUEUE_PATH, index=False, encoding="utf-8-sig")
    logging.info("Added %s review queue rows", len(new_rows))


if __name__ == "__main__":
    main()
