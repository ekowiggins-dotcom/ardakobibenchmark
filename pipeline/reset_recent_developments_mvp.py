from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARCHIVE_DIR = DATA_DIR / "archive"
sys.path.insert(0, str(ROOT_DIR))

from pipeline.collect_static_pages import METADATA_COLUMNS
from pipeline.extract_recent_items import AUDIT_COLUMNS, RECENT_ITEM_COLUMNS
from pipeline.summarize_recent_items import SUMMARY_COLUMNS
from utils.development_clustering import CLUSTER_COLUMNS
from utils.recent_mvp import ARCHIVE_COLUMNS, CLUSTER_QUEUE_COLUMNS, MANAGEMENT_AWARENESS_COLUMNS, QUEUE_COLUMNS, WEEKLY_COLUMNS

RESET_FILES = {
    "recent_items.csv": RECENT_ITEM_COLUMNS,
    "recent_item_summaries.csv": SUMMARY_COLUMNS,
    "recent_item_review_queue.csv": QUEUE_COLUMNS,
    "management_awareness_queue.csv": MANAGEMENT_AWARENESS_COLUMNS,
    "recent_item_archive.csv": ARCHIVE_COLUMNS,
    "recent_item_extraction_audit.csv": AUDIT_COLUMNS,
    "development_clusters.csv": [
        *CLUSTER_COLUMNS,
        "why_it_matters",
        "competitor_intent",
        "management_takeaway",
        "extracted_facts_json",
        "llm_model",
        "error_message",
        "language_lint_score",
        "language_lint_warnings",
        "needs_language_review",
    ],
    "development_cluster_review_queue.csv": CLUSTER_QUEUE_COLUMNS,
    "weekly_developments.csv": WEEKLY_COLUMNS,
    "raw_documents_metadata.csv": METADATA_COLUMNS,
}

RELATED_DEBUG_PATHS = [
    DATA_DIR / "llm_errors",
]

RAW_DIRS = [
    DATA_DIR / "raw_documents" / "raw_html",
    DATA_DIR / "raw_documents" / "cleaned_text",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_institutions(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def archive_path(path: Path, reset_dir: Path, dry_run: bool) -> None:
    if not path.exists():
        return
    target = reset_dir / path.relative_to(ROOT_DIR)
    logging.info("Archive %s -> %s", path.relative_to(ROOT_DIR), target.relative_to(ROOT_DIR))
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(target))


def recreate_csv(filename: str, columns: list[str], dry_run: bool) -> None:
    path = DATA_DIR / filename
    logging.info("Recreate empty %s", path.relative_to(ROOT_DIR))
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=columns).to_csv(path, index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive and reset recent-development MVP outputs.")
    parser.add_argument(
        "--institutions",
        default="Garanti BBVA,İş Bankası,Yapı Kredi,QNB Finansbank",
        help="Comma-separated institutions for audit context.",
    )
    parser.add_argument(
        "--include-weekly-developments",
        action="store_true",
        default=True,
        help="Archive and reset weekly_developments.csv. Default is enabled for full MVP rehearsal.",
    )
    parser.add_argument("--include-raw-files", action="store_true", help="Also archive raw HTML and cleaned text files.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without moving or recreating files.")
    args = parser.parse_args()

    institutions = parse_institutions(args.institutions)
    reset_dir = ARCHIVE_DIR / f"reset_{timestamp()}"
    logging.info("Reset archive folder: %s", reset_dir.relative_to(ROOT_DIR))
    logging.info("Institutions in rehearsal scope: %s", ", ".join(institutions))
    if not args.dry_run:
        reset_dir.mkdir(parents=True, exist_ok=True)

    for filename, columns in RESET_FILES.items():
        if filename == "weekly_developments.csv" and not args.include_weekly_developments:
            continue
        archive_path(DATA_DIR / filename, reset_dir, args.dry_run)
        recreate_csv(filename, columns, args.dry_run)

    for debug_path in RELATED_DEBUG_PATHS:
        archive_path(debug_path, reset_dir, args.dry_run)
        if debug_path.suffix == "" and not args.dry_run:
            debug_path.mkdir(parents=True, exist_ok=True)

    if args.include_raw_files:
        for raw_dir in RAW_DIRS:
            archive_path(raw_dir, reset_dir, args.dry_run)
            if not args.dry_run:
                raw_dir.mkdir(parents=True, exist_ok=True)
    else:
        logging.info("Raw HTML/text files preserved. Use --include-raw-files to archive them too.")

    marker = reset_dir / "RESET_SCOPE.txt"
    if not args.dry_run:
        marker.write_text(
            "\n".join(
                [
                    "Akbank KOBİ Rekabet Gelişmeleri Radarı MVP reset",
                    f"institutions={','.join(institutions)}",
                    f"include_weekly_developments={args.include_weekly_developments}",
                    f"include_raw_files={args.include_raw_files}",
                ]
            ),
            encoding="utf-8",
        )
    logging.info("Reset complete: %s", reset_dir.relative_to(ROOT_DIR))


if __name__ == "__main__":
    main()
