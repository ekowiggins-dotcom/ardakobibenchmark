from __future__ import annotations

import argparse
import logging
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

REGISTRY_PATH = DATA_DIR / "source_registry.csv"
RECENT_ITEMS_PATH = DATA_DIR / "recent_items.csv"
SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"
QUEUE_PATH = DATA_DIR / "recent_item_review_queue.csv"
ARCHIVE_PATH = DATA_DIR / "recent_item_archive.csv"

WEEKLY_SOURCE_TYPES = {
    "Official Press Release Page",
    "Official Campaign Page",
    "Regulator",
    "Industry Association",
    "News Site",
    "Fintech News",
    "Business News",
    "Resmi Basın Bülteni Sayfası",
    "Resmi Kampanya Sayfası",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def run_step(args: list[str], capture: bool = False) -> str:
    logging.info("Running: %s", " ".join(args))
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT_DIR,
        check=True,
        text=True,
        capture_output=capture,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if capture and output:
        print(output, end="")
    return output


def metric_from_log(text: str, label: str) -> int:
    matches = re.findall(rf"{re.escape(label)}:\s*(\d+)", text)
    return int(matches[-1]) if matches else 0


def institution_sources(registry: pd.DataFrame, institution: str) -> pd.DataFrame:
    token = institution.strip().casefold()
    sources = registry[
        registry["institution_name"].astype(str).str.casefold().eq(token)
        | registry["institution_id"].astype(str).str.casefold().eq(token)
    ].copy()
    return sources[
        sources["extraction_mode"].astype(str).isin(["weekly_development", "both"])
        & sources["source_type"].astype(str).isin(WEEKLY_SOURCE_TYPES)
    ].copy()


def institution_rows(df: pd.DataFrame, institution: str) -> pd.DataFrame:
    if df.empty or "institution_name" not in df.columns:
        return pd.DataFrame()
    token = institution.strip().casefold()
    return df[df["institution_name"].astype(str).str.casefold().eq(token)].copy()


def run_institution(
    institution: str,
    summarize_limit: int | None = None,
    start_date: str = "2026-05-01",
    allow_end_date_recency: bool = False,
) -> None:
    registry = read_csv(REGISTRY_PATH)
    eligible_sources = institution_sources(registry, institution)

    print(f"\n=== {institution} recent-development flow ===")
    print(f"sources considered: {len(eligible_sources)}")
    if eligible_sources.empty:
        print("No proper weekly-development source found; skipping collection/extraction/summarization.")
        return

    for _, row in eligible_sources.iterrows():
        print(
            "source | "
            f"{row.get('institution_name', '')} | {row.get('source_id', '')} | "
            f"{row.get('source_name', '')} | {row.get('source_type', '')} | "
            f"{row.get('url', '')} | {row.get('extraction_mode', '')}"
        )

    before_items = institution_rows(read_csv(RECENT_ITEMS_PATH), institution)
    before_summaries = institution_rows(read_csv(SUMMARIES_PATH), institution)
    before_queue = institution_rows(read_csv(QUEUE_PATH), institution)
    before_archive = institution_rows(read_csv(ARCHIVE_PATH), institution)

    run_step(["pipeline/collect_static_pages.py", "--institution", institution])
    run_step(["pipeline/detect_changes.py"])

    debug_args = ["pipeline/extract_recent_items.py", "--institution", institution, "--debug-candidates", "--limit", "10", "--start-date", start_date]
    extract_args = [
        "pipeline/extract_recent_items.py",
        "--institution",
        institution,
        "--fetch-detail-pages",
        "--limit",
        "20",
        "--force",
        "--start-date",
        start_date,
    ]
    summarize_args = ["pipeline/summarize_recent_items.py", "--institution", institution, "--start-date", start_date]
    if allow_end_date_recency:
        debug_args.append("--allow-end-date-recency")
        extract_args.append("--allow-end-date-recency")
        summarize_args.append("--allow-end-date-recency")
    debug_output = run_step(debug_args, capture=True)
    extract_output = run_step(extract_args, capture=True)

    if summarize_limit is not None:
        summarize_args.extend(["--limit", str(summarize_limit)])
    else:
        summarize_args.extend(["--limit", "10"])
    summarize_output = run_step(summarize_args, capture=True)

    run_step(["pipeline/update_recent_item_review_queue.py"], capture=True)
    triage_output = run_step(["pipeline/retriage_recent_item_summaries.py"], capture=True)

    after_items = institution_rows(read_csv(RECENT_ITEMS_PATH), institution)
    after_summaries = institution_rows(read_csv(SUMMARIES_PATH), institution)
    after_queue = institution_rows(read_csv(QUEUE_PATH), institution)
    after_archive = institution_rows(read_csv(ARCHIVE_PATH), institution)

    new_items = max(0, len(after_items) - len(before_items))
    new_summaries = max(0, len(after_summaries) - len(before_summaries))
    new_queue = max(0, len(after_queue) - len(before_queue))
    new_archive = max(0, len(after_archive) - len(before_archive))

    print(f"\n{institution} run summary")
    print(f"sources considered: {len(eligible_sources)}")
    print(f"recency cutoff: {start_date}")
    print(f"total links found: {metric_from_log(extract_output, 'Total links found') or metric_from_log(debug_output, 'Total links found')}")
    print(f"candidate links found: {metric_from_log(extract_output, 'Candidate links found') or metric_from_log(debug_output, 'Candidate links found')}")
    print(f"detail pages fetched: {metric_from_log(extract_output, 'Detail pages fetched')}")
    print(f"recent items created: {metric_from_log(extract_output, 'Recent items created')}")
    print(f"saved recent developments: {metric_from_log(extract_output, 'Saved recent developments')}")
    print(f"rejected old items: {metric_from_log(extract_output, 'Rejected old items')}")
    print(f"rejected undated items: {metric_from_log(extract_output, 'Rejected undated items')}")
    print(f"rejected low-confidence dates: {metric_from_log(extract_output, 'Rejected low-confidence dates')}")
    print(f"rejected non-developments: {metric_from_log(extract_output, 'Rejected non-developments')}")
    print(f"rejected because only campaign_end_date existed: {metric_from_log(extract_output, 'Rejected because only campaign_end_date existed')}")
    print(f"recent item row delta: {new_items}")
    print(f"Claude summaries created: {metric_from_log(summarize_output, 'Summaries created')}")
    print(f"summary row delta: {new_summaries}")
    print(f"JSON parse failures: {metric_from_log(summarize_output, 'JSON parse failures')}")
    print(f"sent to review queue: {metric_from_log(triage_output, 'Sent to review queue')}")
    print(f"review queue row delta: {new_queue}")
    print(f"archived low priority: {metric_from_log(triage_output, 'Archived low priority')}")
    print(f"archive row delta: {new_archive}")
    print("first 5 item titles:")
    if after_items.empty:
        print("- none")
    else:
        for title in after_items["item_title"].head(5):
            print(f"- {title}")
    print("first 3 review queue titles:")
    if after_queue.empty:
        print("- none")
    else:
        for title in after_queue["item_title"].head(3):
            print(f"- {title}")
    print("first 3 archived titles:")
    if after_archive.empty:
        print("- none")
    else:
        for title in after_archive["item_title"].head(3):
            print(f"- {title}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run recent-development flow for one or more institutions.")
    parser.add_argument("--institution", default=None, help='Single institution, e.g. "İş Bankası".')
    parser.add_argument("--institutions", default=None, help='Comma-separated institutions, e.g. "İş Bankası,Yapı Kredi".')
    parser.add_argument("--limit", type=int, default=None, help="Override summarize_recent_items.py --limit.")
    parser.add_argument("--start-date", default="2026-05-01", help="Recent-development kesim tarihi, örn. 2026-05-01.")
    parser.add_argument("--allow-end-date-recency", action="store_true", help="Sadece kampanya bitiş tarihi bulunan adayları manuel izinle geçir.")
    args = parser.parse_args()

    institutions = []
    if args.institution:
        institutions.append(args.institution)
    if args.institutions:
        institutions.extend([item.strip() for item in args.institutions.split(",") if item.strip()])
    if not institutions:
        raise SystemExit("Use --institution or --institutions.")

    seen = set()
    for institution in institutions:
        key = institution.casefold()
        if key in seen:
            continue
        seen.add(key)
        run_institution(
            institution,
            summarize_limit=args.limit,
            start_date=args.start_date,
            allow_end_date_recency=args.allow_end_date_recency,
        )


if __name__ == "__main__":
    main()
