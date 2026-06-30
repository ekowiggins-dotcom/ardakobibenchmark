from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(ROOT_DIR))

from utils.development_clustering import CLUSTER_COLUMNS, cluster_recent_developments

ITEMS_PATH = DATA_DIR / "recent_items.csv"
SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"
CLUSTERS_PATH = DATA_DIR / "development_clusters.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def read_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame()


def truthy(value) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "evet"}


def main() -> None:
    items = read_csv(ITEMS_PATH)
    summaries = read_csv(SUMMARIES_PATH)
    if items.empty or summaries.empty:
        pd.DataFrame(columns=CLUSTER_COLUMNS).to_csv(CLUSTERS_PATH, index=False, encoding="utf-8-sig")
        logging.info("Recent items joined: 0")
        logging.info("Clusters created: 0")
        return

    for column in ["recent_item_id", "is_recent", "is_actual_development", "item_quality"]:
        if column not in items.columns:
            items[column] = ""
    active_items = items[
        items["is_recent"].apply(truthy)
        & items["is_actual_development"].apply(truthy)
        & items["item_quality"].astype(str).isin(["Good", "Medium"])
    ].copy()

    summary_cols = [
        column
        for column in summaries.columns
        if column not in {"document_id", "source_id", "institution_id", "institution_name", "item_title", "item_date", "item_url"}
    ]
    joined = active_items.merge(summaries[summary_cols], on="recent_item_id", how="inner", suffixes=("", "_summary"))
    clusters = cluster_recent_developments(joined)
    clusters.to_csv(CLUSTERS_PATH, index=False, encoding="utf-8-sig")

    logging.info("Recent items joined: %s", len(joined))
    logging.info("Clusters created: %s", len(clusters))
    if not clusters.empty:
        for _, row in clusters.head(10).iterrows():
            logging.info("Cluster | %s | %s | items=%s", row["institution_name"], row["cluster_title"], row["item_count"])


if __name__ == "__main__":
    main()
