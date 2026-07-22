from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
QUEUE_PATH = DATA_DIR / "development_cluster_review_queue.csv"
CLUSTERS_PATH = DATA_DIR / "development_clusters.csv"
WEEKLY_PATH = DATA_DIR / "weekly_developments.csv"
ITEMS_PATH = DATA_DIR / "recent_items.csv"

WEEKLY_COLUMNS = [
    "development_id",
    "date",
    "institution_id",
    "institution_name",
    "headline",
    "strategic_theme",
    "product_area",
    "development_type",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "source_id",
    "analyst_note",
    "tags",
    "summary_id",
    "recent_item_id",
    "cluster_id",
    "related_item_ids",
    "source_urls",
    "source_url",
    "item_url",
    "section",
    "published_at",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=columns or [])
    if columns is not None:
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        df = df.reindex(columns=columns)
    return df


def best_date(row: pd.Series) -> str:
    for column in ["cluster_start_date", "created_at"]:
        parsed = pd.to_datetime(row.get(column, ""), errors="coerce")
        if pd.notna(parsed):
            return parsed.date().isoformat()
    return pd.Timestamp.utcnow().date().isoformat()


def publish_approved_clusters() -> int:
    queue = read_csv(QUEUE_PATH)
    clusters = read_csv(CLUSTERS_PATH)
    weekly = read_csv(WEEKLY_PATH, WEEKLY_COLUMNS)
    items = read_csv(ITEMS_PATH)
    if queue.empty:
        weekly.to_csv(WEEKLY_PATH, index=False, encoding="utf-8-sig")
        return 0

    approved = queue[queue["review_status"].astype(str).eq("Onaylandı")].copy()
    if not clusters.empty:
        metadata_cols = [
            "cluster_id",
            "strategic_theme",
            "product_area",
            "development_type",
            "cluster_start_date",
            "cluster_end_date",
        ]
        approved = approved.merge(
            clusters[[column for column in metadata_cols if column in clusters.columns]],
            on="cluster_id",
            how="left",
            suffixes=("", "_cluster"),
        )
    existing_cluster_ids = set(weekly.get("cluster_id", pd.Series(dtype=str)).dropna().astype(str))

    new_rows = []
    published_item_updates: list[tuple[str, str]] = []
    published_at = pd.Timestamp.utcnow().isoformat()
    for _, row in approved.iterrows():
        cluster_id = str(row.get("cluster_id", ""))
        if not cluster_id or cluster_id in existing_cluster_ids:
            continue
        item_ids = str(row.get("item_ids", ""))
        development_id = f"DEV-{cluster_id}"
        new_rows.append(
            {
                "development_id": development_id,
                "date": best_date(row),
                "institution_id": "",
                "institution_name": row.get("institution_name", ""),
                "headline": row.get("cluster_title", ""),
                "strategic_theme": row.get("strategic_theme", ""),
                "product_area": row.get("product_area", ""),
                "development_type": "Patern / Küme",
                "summary": row.get("cluster_summary", ""),
                "core_assessment": row.get("cluster_core_assessment", ""),
                "strategic_relevance": row.get("why_it_matters", ""),
                "impact_on_us": row.get("impact_on_us", ""),
                "recommended_action": row.get("recommended_action", ""),
                "importance_level": row.get("importance_level", ""),
                "source_id": "",
                "analyst_note": row.get("analyst_note", "") or "Analist onayından geçmiş küme/patern sentezi.",
                "tags": f"cluster_flow;cluster_id:{cluster_id};item_count:{row.get('item_count', '')}",
                "summary_id": "",
                "recent_item_id": "",
                "cluster_id": cluster_id,
                "related_item_ids": item_ids,
                "source_urls": row.get("source_urls", ""),
                "source_url": "",
                "item_url": "",
                "section": "Patern / Küme Gelişmeler",
                "published_at": published_at,
            }
        )
        for raw_id in item_ids.replace("[", "").replace("]", "").replace('"', "").split(","):
            item_id = raw_id.strip()
            if item_id:
                published_item_updates.append((item_id, cluster_id))

    if published_item_updates and not items.empty:
        for column in ["cluster_published", "cluster_id"]:
            if column not in items.columns:
                items[column] = ""
        for item_id, cluster_id in published_item_updates:
            mask = items["recent_item_id"].astype(str).eq(item_id)
            items.loc[mask, "cluster_published"] = True
            items.loc[mask, "cluster_id"] = cluster_id
        items.to_csv(ITEMS_PATH, index=False, encoding="utf-8-sig")

    weekly = pd.concat([weekly, pd.DataFrame(new_rows)], ignore_index=True).reindex(columns=WEEKLY_COLUMNS)
    weekly.to_csv(WEEKLY_PATH, index=False, encoding="utf-8-sig")
    return len(new_rows)


def main() -> None:
    published_count = publish_approved_clusters()
    queue = read_csv(QUEUE_PATH)
    approved_count = int(queue["review_status"].astype(str).eq("Onaylandı").sum()) if "review_status" in queue.columns else 0
    items = read_csv(ITEMS_PATH)
    published_item_count = int(items.get("cluster_published", pd.Series(dtype=object)).astype(str).str.casefold().isin(["true", "1", "yes"]).sum()) if not items.empty else 0
    logging.info("Approved clusters found: %s", approved_count)
    logging.info("Published clusters: %s", published_count)
    logging.info("Included individual items marked cluster_published: %s", published_item_count)


if __name__ == "__main__":
    main()
