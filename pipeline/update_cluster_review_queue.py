from __future__ import annotations

import logging
import json
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
CLUSTERS_PATH = DATA_DIR / "development_clusters.csv"
QUEUE_PATH = DATA_DIR / "development_cluster_review_queue.csv"
SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"

QUEUE_COLUMNS = [
    "cluster_id",
    "institution_name",
    "cluster_title",
    "cluster_summary",
    "cluster_core_assessment",
    "why_it_matters",
    "competitor_intent",
    "recommended_action",
    "impact_on_us",
    "importance_level",
    "confidence_level",
    "management_takeaway",
    "item_count",
    "item_ids",
    "item_titles",
    "source_urls",
    "review_status",
    "analyst_note",
    "reviewer",
    "reviewed_at",
    "created_at",
    "language_lint_score",
    "language_lint_warnings",
    "needs_language_review",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path, encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=columns or [])
    if columns is not None:
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        df = df.reindex(columns=columns)
    return df


def parse_item_ids(value) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass
    return [token.strip() for token in text.replace("[", "").replace("]", "").replace('"', "").split(",") if token.strip()]


def mark_covered_summaries(clusters: pd.DataFrame) -> int:
    summaries = read_csv(SUMMARIES_PATH)
    if summaries.empty:
        summaries.to_csv(SUMMARIES_PATH, index=False, encoding="utf-8-sig")
        return 0

    for column in ["cluster_id", "cluster_status", "covered_by_cluster", "suppress_individual_review", "suppression_reason"]:
        if column not in summaries.columns:
            summaries[column] = ""

    marked = 0
    active_clusters = clusters[pd.to_numeric(clusters.get("item_count", pd.Series(dtype=str)), errors="coerce").fillna(0) >= 2].copy()
    for _, cluster in active_clusters.iterrows():
        cluster_id = str(cluster.get("cluster_id", "") or "").strip()
        if not cluster_id:
            continue
        for item_id in parse_item_ids(cluster.get("item_ids", "")):
            mask = summaries["recent_item_id"].astype(str).eq(item_id)
            if not mask.any():
                continue
            summaries.loc[mask, "cluster_id"] = cluster_id
            summaries.loc[mask, "cluster_status"] = "Küme İncelemede"
            summaries.loc[mask, "covered_by_cluster"] = True
            marked += int(mask.sum())

    summaries.to_csv(SUMMARIES_PATH, index=False, encoding="utf-8-sig")
    return marked


def main() -> None:
    queue = read_csv(QUEUE_PATH, QUEUE_COLUMNS)
    clusters = read_csv(CLUSTERS_PATH)
    if clusters.empty:
        queue.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
        logging.info("Clusters read: 0")
        logging.info("Cluster review queue rows: %s", len(queue))
        logging.info("Sent to cluster review queue: 0")
        return

    for column in QUEUE_COLUMNS:
        if column not in clusters.columns:
            clusters[column] = ""

    candidates = clusters[pd.to_numeric(clusters["item_count"], errors="coerce").fillna(0) >= 2].copy()
    queue_by_id = {str(row["cluster_id"]): idx for idx, row in queue.iterrows()} if not queue.empty else {}
    new_rows = []
    updated = 0

    protected_columns = {"review_status", "analyst_note", "reviewer", "reviewed_at"}
    for _, row in candidates.iterrows():
        cluster_id = str(row.get("cluster_id", ""))
        if not cluster_id:
            continue
        row_data = {column: row.get(column, "") for column in QUEUE_COLUMNS}
        row_data["review_status"] = row_data["review_status"] or "Beklemede"
        if cluster_id in queue_by_id:
            idx = queue_by_id[cluster_id]
            for column, value in row_data.items():
                if column in protected_columns:
                    continue
                queue.at[idx, column] = value
            updated += 1
        else:
            if not row_data["review_status"]:
                row_data["review_status"] = "Beklemede"
            new_rows.append(row_data)

    covered_summary_count = mark_covered_summaries(clusters)
    queue = pd.concat([queue, pd.DataFrame(new_rows)], ignore_index=True).reindex(columns=QUEUE_COLUMNS)
    queue.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
    logging.info("Clusters read: %s", len(clusters))
    logging.info("Sent to cluster review queue: %s", len(new_rows) + updated)
    logging.info("New cluster review rows: %s", len(new_rows))
    logging.info("Cluster review queue rows: %s", len(queue))
    logging.info("Recent item summaries marked covered_by_cluster: %s", covered_summary_count)


if __name__ == "__main__":
    main()
