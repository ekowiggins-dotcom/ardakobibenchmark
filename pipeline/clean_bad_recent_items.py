from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARCHIVE_DIR = DATA_DIR / "archive"

ITEMS_PATH = DATA_DIR / "recent_items.csv"
SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"
QUEUE_PATH = DATA_DIR / "recent_item_review_queue.csv"

BAD_RE = re.compile(
    r"(?:tekil gelişme kontrol|dry-run placeholder|LLM kimlik bilgisi bulunamadı|fallback|source page|communication / press releases için)",
    re.IGNORECASE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def archive_rows(df: pd.DataFrame, mask: pd.Series, archive_name: str, stamp: str) -> pd.DataFrame:
    removed = df[mask].copy()
    kept = df[~mask].copy()
    if not removed.empty:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archive_path = ARCHIVE_DIR / f"{archive_name}_{stamp}.csv"
        removed.to_csv(archive_path, index=False, encoding="utf-8-sig")
        logging.info("Archived %s rows to %s", len(removed), archive_path.relative_to(ROOT_DIR))
    else:
        logging.info("Archived 0 rows for %s", archive_name)
    return kept


def main() -> None:
    stamp = timestamp()
    items = read_csv(ITEMS_PATH)
    summaries = read_csv(SUMMARIES_PATH)
    queue = read_csv(QUEUE_PATH)

    bad_item_ids: set[str] = set()
    bad_summary_ids: set[str] = set()

    if not items.empty:
        item_mask = (
            items.get("extraction_method", pd.Series("", index=items.index)).astype(str).eq("fallback_source_page")
            | items.get("item_title", pd.Series("", index=items.index)).astype(str).str.contains(BAD_RE, na=False)
        )
        bad_item_ids = set(items.loc[item_mask, "recent_item_id"].dropna().astype(str))
        items_clean = archive_rows(items, item_mask, "bad_recent_items", stamp)
        items_clean.to_csv(ITEMS_PATH, index=False, encoding="utf-8-sig")
    else:
        items_clean = items

    if not summaries.empty:
        summary_mask = (
            summaries.get("recent_item_id", pd.Series("", index=summaries.index)).astype(str).isin(bad_item_ids)
            | summaries.get("summary", pd.Series("", index=summaries.index)).astype(str).str.contains(BAD_RE, na=False)
            | summaries.get("error_message", pd.Series("", index=summaries.index)).astype(str).str.contains(BAD_RE, na=False)
        )
        bad_summary_ids = set(summaries.loc[summary_mask, "summary_id"].dropna().astype(str))
        summaries_clean = archive_rows(summaries, summary_mask, "bad_recent_item_summaries", stamp)
        summaries_clean.to_csv(SUMMARIES_PATH, index=False, encoding="utf-8-sig")
    else:
        summaries_clean = summaries

    if not queue.empty:
        queue_mask = (
            queue.get("recent_item_id", pd.Series("", index=queue.index)).astype(str).isin(bad_item_ids)
            | queue.get("summary_id", pd.Series("", index=queue.index)).astype(str).isin(bad_summary_ids)
            | queue.get("summary", pd.Series("", index=queue.index)).astype(str).str.contains(BAD_RE, na=False)
        )
        queue_clean = archive_rows(queue, queue_mask, "bad_recent_item_review_queue", stamp)
        queue_clean.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
    else:
        queue_clean = queue

    logging.info("Active recent_items rows: %s", len(items_clean))
    logging.info("Active recent_item_summaries rows: %s", len(summaries_clean))
    logging.info("Active recent_item_review_queue rows: %s", len(queue_clean))


if __name__ == "__main__":
    main()
