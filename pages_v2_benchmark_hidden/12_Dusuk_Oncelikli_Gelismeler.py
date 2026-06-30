from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from utils.translations import format_turkish_date


st.set_page_config(page_title="Düşük Öncelikli Gelişmeler", layout="wide")

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARCHIVE_PATH = DATA_DIR / "recent_item_archive.csv"
SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"
ITEMS_PATH = DATA_DIR / "recent_items.csv"

ARCHIVE_COLUMNS = [
    "archive_id",
    "summary_id",
    "recent_item_id",
    "document_id",
    "source_id",
    "institution_name",
    "item_title",
    "item_date",
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "importance_level",
    "confidence_level",
    "triage_status",
    "triage_reason",
    "archived_at",
]


def read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path, encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=columns or [])
    if columns:
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        df = df.reindex(columns=columns)
    return df


archive = read_csv(ARCHIVE_PATH, ARCHIVE_COLUMNS)
summaries = read_csv(SUMMARIES_PATH)
items = read_csv(ITEMS_PATH)

st.title("Düşük Öncelikli Gelişmeler")
st.caption("LLM triage sonrası ana onay kuyruğuna alınmayan düşük öncelikli gelişme özetleri.")

if archive.empty:
    st.info("Henüz düşük öncelikli arşiv maddesi yok.")
    st.stop()

view = archive.copy()
if not summaries.empty:
    extra_cols = [col for col in ["summary_id", "strategic_theme", "item_url"] if col in summaries.columns]
    if extra_cols:
        view = view.merge(summaries[extra_cols], on="summary_id", how="left", suffixes=("", "_summary"))
if not items.empty:
    item_cols = [col for col in ["recent_item_id", "source_url", "item_url"] if col in items.columns]
    if item_cols:
        view = view.merge(items[item_cols], on="recent_item_id", how="left", suffixes=("", "_item"))

for column in ["strategic_theme", "item_url", "source_url"]:
    if column not in view.columns:
        view[column] = ""
if "item_url_item" in view.columns:
    view["item_url"] = view["item_url"].fillna("")
    view["item_url"] = view["item_url"].where(view["item_url"].astype(str).str.len() > 0, view["item_url_item"].fillna(""))

view["date_dt"] = pd.to_datetime(view["item_date"], errors="coerce", dayfirst=True, utc=True)
view["archived_dt"] = pd.to_datetime(view["archived_at"], errors="coerce", utc=True)
view["date_dt"] = view["date_dt"].fillna(view["archived_dt"]).fillna(pd.Timestamp.utcnow()).dt.tz_localize(None)

min_date = view["date_dt"].min().date()
max_date = view["date_dt"].max().date()

with st.sidebar:
    st.header("Arşiv Filtreleri")
    institutions = sorted(view["institution_name"].dropna().astype(str).unique())
    themes = sorted(view["strategic_theme"].dropna().astype(str).unique())
    impacts = sorted(view["impact_on_us"].dropna().astype(str).unique())
    actions = sorted(view["recommended_action"].dropna().astype(str).unique())

    selected_institutions = st.multiselect("Kurum", institutions, default=institutions)
    selected_themes = st.multiselect("Tema", themes, default=themes)
    selected_impacts = st.multiselect("Etki", impacts, default=impacts)
    selected_actions = st.multiselect("Aksiyon", actions, default=actions)
    selected_range = st.date_input("Tarih", value=(min_date, max_date), min_value=min_date, max_value=max_date)

if isinstance(selected_range, tuple) and len(selected_range) == 2:
    start_date, end_date = selected_range
else:
    start_date, end_date = min_date, max_date

filtered = view[
    view["institution_name"].isin(selected_institutions)
    & view["strategic_theme"].isin(selected_themes)
    & view["impact_on_us"].isin(selected_impacts)
    & view["recommended_action"].isin(selected_actions)
    & (view["date_dt"].dt.date >= start_date)
    & (view["date_dt"].dt.date <= end_date)
].copy()

k1, k2, k3 = st.columns(3)
k1.metric("Arşiv maddesi", len(filtered))
k2.metric("Düşük etki", filtered["impact_on_us"].eq("Düşük").sum())
k3.metric("Önceliklendirme", filtered["recommended_action"].eq("Önceliklendirme").sum())

if filtered.empty:
    st.warning("Seçili filtrelerle eşleşen arşiv maddesi yok.")
    st.stop()

for _, row in filtered.sort_values("date_dt", ascending=False).iterrows():
    with st.container(border=True):
        st.subheader(str(row.get("item_title", "")))
        st.write(f"**Tarih:** {format_turkish_date(row.get('date_dt'))}")
        st.write(f"**Başlık:** {row.get('headline', '')}")
        if str(row.get("core_assessment", "") or "").strip():
            st.write(f"**Kısa değerlendirme:** {row.get('core_assessment', '')}")
        st.write(f"**Özet:** {row.get('summary', '')}")
        st.write(f"**Triage nedeni:** {row.get('triage_reason', '')}")

        links = st.columns(2)
        item_url = str(row.get("item_url", "") or "")
        source_url = str(row.get("source_url", "") or "")
        if item_url.startswith("http"):
            links[0].link_button("Gelişmeyi Aç", item_url)
        if source_url.startswith("http"):
            links[1].link_button("Kaynağı Aç", source_url)
