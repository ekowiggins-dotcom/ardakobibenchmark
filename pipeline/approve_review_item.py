from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
EXTRACTIONS_PATH = DATA_DIR / "llm_extractions.csv"
REVIEW_QUEUE_PATH = DATA_DIR / "review_queue.csv"
ALLOWED_STATUSES = {"Approved", "Rejected", "Needs More Research", "Pending"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update a review queue item status.")
    parser.add_argument("review_id")
    parser.add_argument("--status", required=True, choices=sorted(ALLOWED_STATUSES))
    parser.add_argument("--reviewer", default="analyst")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    queue = pd.read_csv(REVIEW_QUEUE_PATH, encoding="utf-8-sig")
    extractions = pd.read_csv(EXTRACTIONS_PATH, encoding="utf-8-sig")
    mask = queue["review_id"].eq(args.review_id)
    if not mask.any():
        raise ValueError(f"Onay maddesi bulunamadı: {args.review_id}")

    approved_at = datetime.now(timezone.utc).isoformat() if args.status == "Approved" else ""
    queue.loc[mask, "review_status"] = args.status
    queue.loc[mask, "reviewer"] = args.reviewer
    queue.loc[mask, "review_notes"] = args.notes
    queue.loc[mask, "approved_at"] = approved_at

    extraction_ids = queue.loc[mask, "extraction_id"].tolist()
    extractions.loc[extractions["extraction_id"].isin(extraction_ids), "review_status"] = args.status

    queue.to_csv(REVIEW_QUEUE_PATH, index=False, encoding="utf-8-sig")
    extractions.to_csv(EXTRACTIONS_PATH, index=False, encoding="utf-8-sig")
    logging.info("Updated %s to %s", args.review_id, args.status)


if __name__ == "__main__":
    main()
