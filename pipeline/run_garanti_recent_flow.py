from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

RECENT_ITEMS_PATH = DATA_DIR / "recent_items.csv"
REGISTRY_PATH = DATA_DIR / "source_registry.csv"

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
    if capture:
        output = (result.stdout or "") + (result.stderr or "")
        print(output, end="")
        return output
    return ""


def metric_from_log(text: str, label: str) -> int:
    matches = re.findall(rf"{re.escape(label)}:\s*(\d+)", text)
    return int(matches[-1]) if matches else 0


def main() -> None:
    institution = "Garanti BBVA"

    run_step(["pipeline/collect_static_pages.py", "--institution", institution])
    run_step(["pipeline/detect_changes.py"])
    run_step(["pipeline/clean_bad_recent_items.py"])
    debug_output = run_step(
        ["pipeline/extract_recent_items.py", "--institution", institution, "--debug-candidates", "--limit", "5"],
        capture=True,
    )
    extract_output = run_step(
        [
            "pipeline/extract_recent_items.py",
            "--institution",
            institution,
            "--fetch-detail-pages",
            "--limit",
            "10",
            "--force",
        ],
        capture=True,
    )

    registry = read_csv(REGISTRY_PATH)
    items = read_csv(RECENT_ITEMS_PATH)
    garanti_sources = registry[
        registry["institution_name"].astype(str).eq(institution)
        | registry["institution_id"].astype(str).eq("garanti_bbva")
    ]
    garanti_items = items[
        items.get("institution_name", pd.Series(dtype=str)).astype(str).eq(institution)
    ] if not items.empty else pd.DataFrame()

    quality_distribution = (
        garanti_items["item_quality"].value_counts().to_dict()
        if not garanti_items.empty and "item_quality" in garanti_items.columns
        else {}
    )

    print("\nGaranti BBVA recent item extraction complete")
    print(f"Garanti sources considered: {len(garanti_sources)}")
    print(f"total links found: {metric_from_log(extract_output, 'Total links found') or metric_from_log(debug_output, 'Total links found')}")
    print(f"candidate links found: {metric_from_log(extract_output, 'Candidate links found') or metric_from_log(debug_output, 'Candidate links found')}")
    print(f"detail pages fetched: {metric_from_log(extract_output, 'Detail pages fetched')}")
    print(f"recent items created: {metric_from_log(extract_output, 'Recent items created')}")
    print(f"rows in recent_items.csv: {len(items)}")
    print("first 10 recent item titles and URLs:")
    if garanti_items.empty:
        print("- none")
    else:
        for _, row in garanti_items.head(10).iterrows():
            print(f"- {row.get('item_title', '')} | {row.get('item_url', '')}")
    print(f"item_quality distribution: {quality_distribution}")


if __name__ == "__main__":
    main()
