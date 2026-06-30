from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
AWARENESS_PATH = DATA_DIR / "management_awareness_queue.csv"
WEEKLY_PATH = DATA_DIR / "weekly_developments.csv"

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


def parse_item_date_to_iso(value: object, institution_name: object = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if slash_match:
        first, second, year = [int(part) for part in slash_match.groups()]
        institution = str(institution_name or "").strip().casefold()
        month_first = institution in {"visa", "mastercard"}
        if first > 12:
            day, month = first, second
        elif second > 12:
            month, day = first, second
        elif month_first:
            month, day = first, second
        else:
            day, month = first, second
        try:
            return pd.Timestamp(year=year, month=month, day=day).date().isoformat()
        except ValueError:
            return text
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.notna(parsed):
        return parsed.date().isoformat()
    return text


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


def best_date(row: pd.Series) -> str:
    item_date = str(row.get("item_date", "") or "").strip()
    if item_date:
        return parse_item_date_to_iso(item_date, row.get("institution_name", ""))
    created = pd.to_datetime(row.get("created_at", ""), errors="coerce")
    if pd.notna(created):
        return created.date().isoformat()
    return pd.Timestamp.utcnow().date().isoformat()


def publish_approved_management_awareness() -> int:
    awareness = read_csv(AWARENESS_PATH)
    weekly = read_csv(WEEKLY_PATH, WEEKLY_COLUMNS)
    if awareness.empty:
        weekly.to_csv(WEEKLY_PATH, index=False, encoding="utf-8-sig")
        return 0

    approved = awareness[awareness["review_status"].astype(str).eq("Onaylandı")].copy()
    existing_development_ids = set(weekly["development_id"].dropna().astype(str))
    existing_summary_ids = set(weekly["summary_id"].dropna().astype(str))
    existing_recent_item_ids = set(weekly["recent_item_id"].dropna().astype(str))
    new_rows = []
    published_at = pd.Timestamp.utcnow().isoformat()

    for _, row in approved.iterrows():
        summary_id = str(row.get("summary_id", "") or "").strip()
        recent_item_id = str(row.get("recent_item_id", "") or "").strip()
        if not summary_id:
            continue
        development_id = f"DEV-MA-{summary_id}"
        if development_id in existing_development_ids or summary_id in existing_summary_ids or recent_item_id in existing_recent_item_ids:
            continue
        analyst_note = str(row.get("analyst_note", "") or "").strip() or "Analist onayından geçmiş yönetici bilgilendirme notu."
        new_rows.append(
            {
                "development_id": development_id,
                "date": best_date(row),
                "institution_id": "",
                "institution_name": row.get("institution_name", ""),
                "headline": row.get("headline", ""),
                "strategic_theme": row.get("strategic_theme", "") or "Kurumsal Konumlandırma",
                "product_area": row.get("product_area", ""),
                "development_type": "Yönetici Bilgilendirme",
                "summary": row.get("summary", ""),
                "core_assessment": row.get("core_assessment", ""),
                "strategic_relevance": row.get("strategic_relevance", ""),
                "impact_on_us": row.get("impact_on_us", ""),
                "recommended_action": "Yönetici Bilgilendirme Notuna Ekle",
                "importance_level": row.get("importance_level", ""),
                "source_id": "",
                "analyst_note": analyst_note,
                "tags": f"management_awareness;summary_id:{summary_id};recent_item_id:{recent_item_id}",
                "summary_id": summary_id,
                "recent_item_id": recent_item_id,
                "cluster_id": "",
                "related_item_ids": "",
                "source_urls": "",
                "source_url": row.get("source_url", ""),
                "item_url": row.get("item_url", ""),
                "section": "Yönetici Bilgilendirme / İtibar Sinyalleri",
                "published_at": published_at,
            }
        )

    weekly = pd.concat([weekly, pd.DataFrame(new_rows)], ignore_index=True).reindex(columns=WEEKLY_COLUMNS)
    weekly.to_csv(WEEKLY_PATH, index=False, encoding="utf-8-sig")
    return len(new_rows)


def main() -> None:
    published_count = publish_approved_management_awareness()
    awareness = read_csv(AWARENESS_PATH)
    approved_count = int(awareness["review_status"].astype(str).eq("Onaylandı").sum()) if "review_status" in awareness.columns else 0
    logging.info("Approved management awareness items found: %s", approved_count)
    logging.info("Published management awareness items: %s", published_count)


if __name__ == "__main__":
    main()
