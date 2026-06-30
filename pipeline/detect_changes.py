from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
METADATA_PATH = DATA_DIR / "raw_documents_metadata.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def classify_group(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("fetched_at").copy()
    previous_hash = None
    for idx, row in group.iterrows():
        if row["status"] == "error" or not str(row.get("content_hash", "")).strip():
            group.at[idx, "change_status"] = "error"
            continue
        if previous_hash is None:
            group.at[idx, "change_status"] = "new_source"
        elif row["content_hash"] == previous_hash:
            group.at[idx, "change_status"] = "unchanged"
        else:
            group.at[idx, "change_status"] = "changed"
        previous_hash = row["content_hash"]
    return group


def main() -> None:
    if not METADATA_PATH.exists():
        raise FileNotFoundError("Run collect_static_pages.py before detect_changes.py")

    metadata = pd.read_csv(METADATA_PATH, encoding="utf-8-sig")
    if metadata.empty:
        logging.info("No metadata rows to classify.")
        return
    if "change_status" not in metadata.columns:
        metadata["change_status"] = ""
    metadata["change_status"] = metadata["change_status"].fillna("").astype(str)

    groups = []
    for _, group in metadata.groupby("source_id", sort=False):
        groups.append(classify_group(group))
    classified = pd.concat(groups, ignore_index=True)
    classified = classified.reindex(columns=metadata.columns)
    classified.to_csv(METADATA_PATH, index=False, encoding="utf-8-sig")
    logging.info("Classified %s documents for change status", len(classified))


if __name__ == "__main__":
    main()
