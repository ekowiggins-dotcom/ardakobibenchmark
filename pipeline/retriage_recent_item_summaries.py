from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(ROOT_DIR))

from pipeline.update_recent_item_review_queue import (
    ARCHIVE_COLUMNS,
    ARCHIVE_PATH,
    AWARENESS_PATH,
    MANAGEMENT_AWARENESS_COLUMNS,
    PRESERVED_STATUSES,
    QUEUE_COLUMNS,
    QUEUE_PATH,
    SUMMARIES_PATH,
    enrich_summaries,
    merge_destination,
    read_csv,
    route_summaries,
    merge_archive,
    write_csv_if_changed,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    queue = read_csv(QUEUE_PATH, QUEUE_COLUMNS)
    awareness = read_csv(AWARENESS_PATH, MANAGEMENT_AWARENESS_COLUMNS)
    archive = read_csv(ARCHIVE_PATH, ARCHIVE_COLUMNS)

    if not SUMMARIES_PATH.exists():
        queue.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
        awareness.to_csv(AWARENESS_PATH, index=False, encoding="utf-8-sig")
        archive.to_csv(ARCHIVE_PATH, index=False, encoding="utf-8-sig")
        logging.info("Total summaries: 0")
        logging.info("Sent to review queue: 0")
        logging.info("Sent to management awareness queue: 0")
        logging.info("Archived low priority: 0")
        logging.info("Suppressed individual review items: 0")
        logging.info("Existing approved/rejected/manual decisions preserved: 0")
        logging.info("Skipped duplicates: 0")
        return

    summaries = pd.read_csv(SUMMARIES_PATH, encoding="utf-8-sig")
    if summaries.empty:
        summaries.to_csv(SUMMARIES_PATH, index=False, encoding="utf-8-sig")
        queue.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
        awareness.to_csv(AWARENESS_PATH, index=False, encoding="utf-8-sig")
        archive.to_csv(ARCHIVE_PATH, index=False, encoding="utf-8-sig")
        logging.info("Total summaries: 0")
        logging.info("Sent to review queue: 0")
        logging.info("Sent to management awareness queue: 0")
        logging.info("Archived low priority: 0")
        logging.info("Suppressed individual review items: 0")
        logging.info("Existing approved/rejected/manual decisions preserved: 0")
        logging.info("Skipped duplicates: 0")
        return

    summaries = enrich_summaries(summaries)
    updated_summaries, queue_rows, awareness_rows, archive_rows, suppressed = route_summaries(summaries)

    rebuilt_queue, new_queue, updated_queue = merge_destination(queue, queue_rows, "summary_id", QUEUE_COLUMNS)
    rebuilt_awareness, new_awareness, updated_awareness = merge_destination(
        awareness, awareness_rows, "summary_id", MANAGEMENT_AWARENESS_COLUMNS
    )

    preserved_review_ids = set()
    if not queue.empty:
        preserved_review_ids.update(queue[queue["review_status"].astype(str).isin(PRESERVED_STATUSES)]["summary_id"].dropna().astype(str))
    if not awareness.empty:
        preserved_review_ids.update(
            awareness[awareness["review_status"].astype(str).isin(PRESERVED_STATUSES)]["summary_id"].dropna().astype(str)
        )

    archive_rows = [row for row in archive_rows if str(row.get("summary_id", "")) not in preserved_review_ids]
    rebuilt_archive, new_archive, updated_archive = merge_archive(archive, archive_rows)

    write_csv_if_changed(SUMMARIES_PATH, updated_summaries, list(updated_summaries.columns))
    write_csv_if_changed(QUEUE_PATH, rebuilt_queue, QUEUE_COLUMNS)
    write_csv_if_changed(AWARENESS_PATH, rebuilt_awareness, MANAGEMENT_AWARENESS_COLUMNS)
    write_csv_if_changed(ARCHIVE_PATH, rebuilt_archive, ARCHIVE_COLUMNS)

    preserved_count = len(preserved_review_ids)
    skipped_duplicates = updated_queue + updated_awareness
    logging.info("Total summaries: %s", len(updated_summaries))
    logging.info("Sent to review queue: %s", new_queue + updated_queue)
    logging.info("Sent to management awareness queue: %s", new_awareness + updated_awareness)
    logging.info("Archived low priority: %s", new_archive + updated_archive)
    logging.info("Suppressed individual review items: %s", suppressed)
    logging.info("Existing approved/rejected/manual decisions preserved: %s", preserved_count)
    logging.info("Skipped duplicates: %s", skipped_duplicates)

    if not rebuilt_archive.empty:
        logging.info("Archived item titles: %s", " | ".join(str(value) for value in rebuilt_archive["item_title"].head(5)))
    if not rebuilt_queue.empty:
        logging.info("Review queue item titles: %s", " | ".join(str(value) for value in rebuilt_queue["item_title"].head(5)))
    if not rebuilt_awareness.empty:
        logging.info("Management awareness titles: %s", " | ".join(str(value) for value in rebuilt_awareness["item_title"].head(5)))


if __name__ == "__main__":
    main()
