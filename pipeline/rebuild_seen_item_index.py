from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(ROOT_DIR))


SEEN_COLUMNS = [
    "institution_name",
    "source_id",
    "canonical_item_url",
    "normalized_title",
    "content_fingerprint",
    "recent_item_id",
    "first_seen_at",
    "last_seen_at",
    "first_run_id",
    "last_run_id",
    "current_status",
    "summary_id",
    "cluster_id",
    "published",
    "archived",
    "rejected",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def truthy(value) -> bool:
    return clean(value).casefold() in {"true", "1", "yes", "evet", "published"}


def normalize_title(value) -> str:
    text = clean(value).casefold()
    text = text.replace("ı", "i").replace("İ", "i")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def fingerprint(*values: str) -> str:
    text = " ".join(clean(value) for value in values if clean(value))
    if not text:
        return ""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def read_csv(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig").fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def first_value(df: pd.DataFrame, key: str, value_col: str) -> dict[str, str]:
    if df.empty or key not in df.columns or value_col not in df.columns:
        return {}
    out: dict[str, str] = {}
    for _, row in df.iterrows():
        k = clean(row.get(key))
        if k and k not in out:
            out[k] = clean(row.get(value_col))
    return out


def existing_seen_map() -> dict[str, dict[str, str]]:
    existing = read_csv("seen_item_index.csv")
    if existing.empty:
        return {}
    for column in SEEN_COLUMNS:
        if column not in existing.columns:
            existing[column] = ""
    return {row_key(row): row.to_dict() for _, row in existing.iterrows()}


def row_key(row: pd.Series | dict[str, str]) -> str:
    item_id = clean(row.get("recent_item_id", ""))
    if item_id:
        return f"id:{item_id}"
    parts = [
        clean(row.get("institution_name", "")),
        clean(row.get("source_id", "")),
        clean(row.get("canonical_item_url", "")),
        clean(row.get("normalized_title", "")),
        clean(row.get("content_fingerprint", "")),
    ]
    return "combo:" + "|".join(parts)


def row_from_item(row: pd.Series, run_id: str, stamp: str) -> dict[str, str]:
    title = clean(row.get("normalized_title")) or normalize_title(row.get("item_title"))
    content_fp = clean(row.get("content_fingerprint")) or clean(row.get("item_hash")) or fingerprint(
        row.get("item_title"), row.get("item_text")
    )
    return {
        "institution_name": clean(row.get("institution_name")),
        "source_id": clean(row.get("source_id")),
        "canonical_item_url": clean(row.get("canonical_item_url")) or clean(row.get("item_url")),
        "normalized_title": title,
        "content_fingerprint": content_fp,
        "recent_item_id": clean(row.get("recent_item_id")),
        "first_seen_at": clean(row.get("detected_at")) or stamp,
        "last_seen_at": stamp,
        "first_run_id": run_id,
        "last_run_id": run_id,
        "current_status": "Keşfedildi",
        "summary_id": "",
        "cluster_id": clean(row.get("cluster_id")),
        "published": "False",
        "archived": "False",
        "rejected": "False",
    }


def apply_existing_first_seen(row: dict[str, str], existing: dict[str, dict[str, str]]) -> dict[str, str]:
    previous = existing.get(row_key(row))
    if not previous:
        return row
    for column in ["first_seen_at", "first_run_id"]:
        if clean(previous.get(column)):
            row[column] = clean(previous.get(column))
    return row


def build_seen_index(run_id: str = "") -> pd.DataFrame:
    stamp = now_iso()
    existing = existing_seen_map()
    items = read_csv("recent_items.csv")
    summaries = read_csv("recent_item_summaries.csv")
    queue = read_csv("recent_item_review_queue.csv")
    awareness = read_csv("management_awareness_queue.csv")
    archive = read_csv("recent_item_archive.csv")
    weekly = read_csv("weekly_developments.csv")

    summary_by_item = first_value(summaries, "recent_item_id", "summary_id")
    cluster_by_item = first_value(summaries, "recent_item_id", "cluster_id")
    queue_status_by_item = first_value(queue, "recent_item_id", "review_status")
    awareness_status_by_item = first_value(awareness, "recent_item_id", "review_status")

    published_items = set(weekly.get("recent_item_id", pd.Series(dtype=str)).dropna().astype(str))
    published_summaries = set(weekly.get("summary_id", pd.Series(dtype=str)).dropna().astype(str))
    archived_items = set(archive.get("recent_item_id", pd.Series(dtype=str)).dropna().astype(str))
    rejected_items = set(
        queue[queue.get("review_status", pd.Series(dtype=str)).astype(str).eq("Reddedildi")]["recent_item_id"].astype(str)
        if not queue.empty and "review_status" in queue.columns and "recent_item_id" in queue.columns
        else []
    )

    rows: dict[str, dict[str, str]] = {}
    if not items.empty:
        for _, item in items.iterrows():
            row = row_from_item(item, run_id, stamp)
            item_id = row["recent_item_id"]
            row["summary_id"] = summary_by_item.get(item_id, "")
            row["cluster_id"] = row["cluster_id"] or cluster_by_item.get(item_id, "")
            if item_id in published_items or row["summary_id"] in published_summaries:
                row["current_status"] = "Yayınlandı"
                row["published"] = "True"
            elif item_id in archived_items:
                row["current_status"] = "Arşivlendi"
                row["archived"] = "True"
            elif item_id in rejected_items:
                row["current_status"] = "Reddedildi"
                row["rejected"] = "True"
            elif item_id in queue_status_by_item:
                row["current_status"] = queue_status_by_item[item_id] or "İncelemede"
            elif item_id in awareness_status_by_item:
                row["current_status"] = awareness_status_by_item[item_id] or "Yönetici Bilgilendirme"
            elif row["summary_id"]:
                row["current_status"] = "Özetlendi"
            rows[row_key(row)] = apply_existing_first_seen(row, existing)

    def add_minimal(frame: pd.DataFrame, status: str, published: bool = False, archived: bool = False, rejected: bool = False) -> None:
        if frame.empty:
            return
        for _, src in frame.iterrows():
            item_id = clean(src.get("recent_item_id"))
            summary_id = clean(src.get("summary_id"))
            if item_id and f"id:{item_id}" in rows:
                continue
            row = {
                "institution_name": clean(src.get("institution_name")),
                "source_id": clean(src.get("source_id")),
                "canonical_item_url": clean(src.get("item_url")) or clean(src.get("source_url")),
                "normalized_title": normalize_title(src.get("item_title") or src.get("headline")),
                "content_fingerprint": fingerprint(src.get("item_title"), src.get("headline"), src.get("summary")),
                "recent_item_id": item_id,
                "first_seen_at": clean(src.get("created_at")) or clean(src.get("archived_at")) or clean(src.get("published_at")) or stamp,
                "last_seen_at": stamp,
                "first_run_id": run_id,
                "last_run_id": run_id,
                "current_status": status,
                "summary_id": summary_id,
                "cluster_id": clean(src.get("cluster_id")),
                "published": str(published),
                "archived": str(archived),
                "rejected": str(rejected),
            }
            rows[row_key(row)] = apply_existing_first_seen(row, existing)

    add_minimal(queue, "İncelemede")
    add_minimal(awareness, "Yönetici Bilgilendirme")
    add_minimal(archive, "Arşivlendi", archived=True)
    add_minimal(weekly, "Yayınlandı", published=True)

    index = pd.DataFrame(rows.values()).reindex(columns=SEEN_COLUMNS)
    if not index.empty:
        index = index.drop_duplicates(subset=["recent_item_id"], keep="last")
        index = index.sort_values(["institution_name", "last_seen_at", "normalized_title"], ascending=[True, False, True])
    return index


def write_seen_index(index: pd.DataFrame) -> Path:
    path = DATA_DIR / "seen_item_index.csv"
    index.reindex(columns=SEEN_COLUMNS).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild persistent seen-item index from active and archived MVP data.")
    parser.add_argument("--run-id", default="", help="Optional run id to stamp last_run_id for rebuilt rows.")
    args = parser.parse_args()

    index = build_seen_index(args.run_id)
    path = write_seen_index(index)
    print(f"seen_item_index rows: {len(index)}")
    print(f"wrote: {path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
