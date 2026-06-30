from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from utils.recent_mvp import (
    ARCHIVE_COLUMNS,
    QUEUE_COLUMNS,
    RECENT_ITEM_COLUMNS,
    SUMMARY_COLUMNS,
    clean_text,
    link_markdown,
    parse_date_series,
    read_csv_safe,
    utc_now,
    write_csv_safe,
)
from utils.ui_theme import apply_akbank_theme, render_page_header


st.set_page_config(page_title="Elenen düşük öncelik", layout="wide")
apply_akbank_theme()

render_page_header(
    "Elenen Düşük Öncelik",
    "Triage veya analist kararıyla ana inceleme akışından ayrılan düşük değerli PR/noise maddeleri.",
)

archive = read_csv_safe("recent_item_archive.csv", ARCHIVE_COLUMNS)
summaries = read_csv_safe("recent_item_summaries.csv", SUMMARY_COLUMNS)
items = read_csv_safe("recent_items.csv", RECENT_ITEM_COLUMNS)

if archive.empty:
    st.info("Henüz düşük öncelikli arşiv maddesi yok.")
    st.stop()
    raise SystemExit

view = archive.copy()
if not summaries.empty:
    extra_cols = [c for c in ["summary_id", "strategic_theme", "product_area", "development_type", "item_url"] if c in summaries.columns]
    view = view.merge(summaries[extra_cols], on="summary_id", how="left", suffixes=("", "_summary"))
if not items.empty:
    item_cols = [c for c in ["recent_item_id", "source_url", "item_url"] if c in items.columns]
    view = view.merge(items[item_cols], on="recent_item_id", how="left", suffixes=("", "_item"))

for column in ["strategic_theme", "item_url", "source_url"]:
    if column not in view.columns:
        view[column] = ""
if "item_url_item" in view.columns:
    view["item_url"] = view["item_url"].fillna("")
    view["item_url"] = view["item_url"].where(view["item_url"].astype(str).str.len() > 0, view["item_url_item"].fillna(""))

view["date_dt"] = parse_date_series(view["item_date"])
view["archived_dt"] = parse_date_series(view["archived_at"])
view["date_dt"] = view["date_dt"].fillna(view["archived_dt"]).fillna(pd.Timestamp.utcnow().tz_localize(None))

k1, k2, k3 = st.columns(3)
k1.metric("Arşivlenen gelişme", len(view))
top_institution = view["institution_name"].mode().iloc[0] if not view["institution_name"].mode().empty else "-"
k2.metric("En çok arşivlenen kurum", clean_text(top_institution))
top_reason = view["triage_reason"].mode().iloc[0] if not view["triage_reason"].mode().empty else "-"
k3.metric("En yaygın neden", clean_text(top_reason)[:48])

with st.sidebar:
    st.header("Arşiv Filtreleri")
    institutions = sorted(view["institution_name"].dropna().astype(str).unique())
    themes = sorted(view["strategic_theme"].dropna().astype(str).unique())
    impacts = sorted(view["impact_on_us"].dropna().astype(str).unique())
    actions = sorted(view["recommended_action"].dropna().astype(str).unique())
    min_date = view["date_dt"].min().date()
    max_date = view["date_dt"].max().date()

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

if filtered.empty:
    st.warning("Seçili filtrelerle eşleşen arşiv maddesi yok.")
    st.stop()
    raise SystemExit

st.subheader("Arşiv Nedenleri")
st.bar_chart(filtered["triage_reason"].replace("", "Belirsiz").value_counts().head(10))


def review_id_for(recent_item_id: str, summary_id: str) -> str:
    digest = hashlib.sha1(f"{recent_item_id}:{summary_id}".encode("utf-8")).hexdigest()[:12]
    return f"RIRQ-{digest}"


def restore_to_queue(row: pd.Series) -> None:
    archive_disk = read_csv_safe("recent_item_archive.csv", ARCHIVE_COLUMNS)
    queue_disk = read_csv_safe("recent_item_review_queue.csv", QUEUE_COLUMNS)
    if queue_disk["recent_item_id"].astype(str).eq(str(row["recent_item_id"])).any():
        st.warning("Bu madde zaten inceleme kuyruğunda.")
        return
    new_row = {
        "review_id": review_id_for(str(row.get("recent_item_id", "")), str(row.get("summary_id", ""))),
        "summary_id": row.get("summary_id", ""),
        "recent_item_id": row.get("recent_item_id", ""),
        "document_id": row.get("document_id", ""),
        "source_id": row.get("source_id", ""),
        "institution_name": row.get("institution_name", ""),
        "item_title": row.get("item_title", ""),
        "item_date": row.get("item_date", ""),
        "strategic_theme": row.get("strategic_theme", ""),
        "headline": row.get("headline", ""),
        "summary": row.get("summary", ""),
        "core_assessment": row.get("core_assessment", ""),
        "strategic_relevance": row.get("strategic_relevance", ""),
        "impact_on_us": row.get("impact_on_us", ""),
        "recommended_action": row.get("recommended_action", ""),
        "confidence_level": row.get("confidence_level", ""),
        "item_url": row.get("item_url", ""),
        "source_url": row.get("source_url", ""),
        "review_status": "Beklemede",
        "reviewer": "",
        "review_notes": "Arşivden inceleme kuyruğuna geri alındı.",
        "approved_at": "",
        "analyst_note": "",
        "reviewed_at": utc_now(),
    }
    queue_disk = pd.concat([queue_disk, pd.DataFrame([new_row])], ignore_index=True)
    archive_disk = archive_disk[~archive_disk["archive_id"].astype(str).eq(str(row["archive_id"]))].copy()
    write_csv_safe(queue_disk, "recent_item_review_queue.csv", QUEUE_COLUMNS)
    write_csv_safe(archive_disk, "recent_item_archive.csv", ARCHIVE_COLUMNS)
    st.success("Madde inceleme kuyruğuna geri alındı.")
    st.rerun()


st.subheader("Arşiv Kartları")
for _, row in filtered.sort_values("date_dt", ascending=False).iterrows():
    with st.container(border=True):
        st.caption(f"{clean_text(row.get('institution_name'))} · {clean_text(row.get('strategic_theme'))} · {clean_text(row.get('item_date'))}")
        st.markdown(f"### {clean_text(row.get('item_title'))}")
        if clean_text(row.get("core_assessment"), ""):
            st.write(f"**Kısa yorum:** {clean_text(row.get('core_assessment'))}")
        st.write(f"**Özet:** {clean_text(row.get('summary'))}")
        st.write(f"**Arşiv nedeni:** {clean_text(row.get('triage_reason'))}")
        st.write(f"**Etki / Aksiyon:** {clean_text(row.get('impact_on_us'))} / {clean_text(row.get('recommended_action'))}")
        links = " · ".join(
            item
            for item in [
                link_markdown("Gelişmeyi aç", row.get("item_url", "")),
                link_markdown("Kaynak", row.get("source_url", "")),
            ]
            if item
        )
        if links:
            st.markdown(links)
        if st.button("İnceleme Kuyruğuna Geri Al", key=f"restore_{row['archive_id']}"):
            restore_to_queue(row)
