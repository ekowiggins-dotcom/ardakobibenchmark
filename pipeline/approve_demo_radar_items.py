from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DEFAULT_SELECTION_PATH = DATA_DIR / "demo_approval_selection.csv"

QUEUE_FILES = {
    "individual": DATA_DIR / "recent_item_review_queue.csv",
    "cluster": DATA_DIR / "development_cluster_review_queue.csv",
    "management_awareness": DATA_DIR / "management_awareness_queue.csv",
}

ID_COLUMNS = {
    "individual": ["review_id", "summary_id", "recent_item_id"],
    "cluster": ["cluster_id"],
    "management_awareness": ["awareness_id", "summary_id", "recent_item_id"],
}

APPROVE_DECISIONS = {"onaylandı", "onayla", "approve", "approved", "yönetici bilgilendirme"}
REJECT_DECISIONS = {"reddedildi", "reddet", "reject", "rejected", "arşivle", "archive"}
RESEARCH_DECISIONS = {"ek araştırma gerekli", "araştır", "research", "needs research"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig").fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def normalize_type(value: object) -> str:
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "recent_item": "individual",
        "item": "individual",
        "tekil": "individual",
        "küme": "cluster",
        "patern": "cluster",
        "management": "management_awareness",
        "awareness": "management_awareness",
        "yonetici_bilgilendirme": "management_awareness",
        "yönetici_bilgilendirme": "management_awareness",
    }
    return aliases.get(text, text)


def normalize_status(decision: object) -> str:
    text = str(decision or "").strip().casefold()
    if text in APPROVE_DECISIONS:
        return "Onaylandı"
    if text in REJECT_DECISIONS:
        return "Reddedildi"
    if text in RESEARCH_DECISIONS:
        return "Ek Araştırma Gerekli"
    return str(decision or "").strip()


def find_mask(df: pd.DataFrame, object_type: str, object_id: str) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    for column in ID_COLUMNS[object_type]:
        if column in df.columns:
            mask = mask | df[column].astype(str).eq(object_id)
    return mask


def apply_selection(selection: pd.DataFrame) -> dict[str, int]:
    queues = {object_type: read_csv(path) for object_type, path in QUEUE_FILES.items()}
    counts = {"updated": 0, "missing": 0, "skipped": 0}
    reviewed_at = now_utc()

    for _, row in selection.iterrows():
        object_type = normalize_type(row.get("object_type", ""))
        object_id = str(row.get("object_id", "") or "").strip()
        status = normalize_status(row.get("decision", ""))
        analyst_note = str(row.get("analyst_note", "") or "").strip()
        reviewer = str(row.get("reviewer", "") or "").strip() or "Demo Radar"

        if object_type not in queues or not object_id or not status:
            counts["skipped"] += 1
            continue

        df = queues[object_type]
        if df.empty:
            counts["missing"] += 1
            continue
        mask = find_mask(df, object_type, object_id)
        if not mask.any():
            print(f"Missing selection target: {object_type} {object_id}")
            counts["missing"] += 1
            continue

        for column in ["review_status", "reviewer", "reviewed_at", "analyst_note"]:
            if column not in df.columns:
                df[column] = ""
        df.loc[mask, "review_status"] = status
        df.loc[mask, "reviewer"] = reviewer
        df.loc[mask, "reviewed_at"] = reviewed_at
        if analyst_note:
            df.loc[mask, "analyst_note"] = analyst_note
            if object_type == "individual" and "review_notes" in df.columns:
                df.loc[mask, "review_notes"] = analyst_note
        if object_type == "individual" and status == "Onaylandı":
            if "approved_at" not in df.columns:
                df["approved_at"] = ""
            df.loc[mask, "approved_at"] = reviewed_at
        counts["updated"] += int(mask.sum())

    for object_type, path in QUEUE_FILES.items():
        queues[object_type].to_csv(path, index=False, encoding="utf-8-sig")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply explicit demo radar approval selections.")
    parser.add_argument("--selection", default=str(DEFAULT_SELECTION_PATH), help="Approval selection CSV path.")
    args = parser.parse_args()

    selection_path = Path(args.selection)
    if not selection_path.exists():
        raise FileNotFoundError(f"Selection file not found: {selection_path}")
    selection = read_csv(selection_path)
    required = {"object_type", "object_id", "decision", "analyst_note", "reviewer"}
    missing = required.difference(selection.columns)
    if missing:
        raise ValueError(f"Selection file missing columns: {sorted(missing)}")

    counts = apply_selection(selection)
    print(f"Selection rows: {len(selection)}")
    print(f"Updated queue rows: {counts['updated']}")
    print(f"Missing targets: {counts['missing']}")
    print(f"Skipped rows: {counts['skipped']}")
    print("No items were published. Run publish scripts separately after reviewing approvals.")


if __name__ == "__main__":
    main()
