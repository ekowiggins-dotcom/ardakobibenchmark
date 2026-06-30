from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.translations import format_turkish_date, tr_columns, tr_label


st.set_page_config(page_title="Gelişme Onay Kuyruğu", layout="wide")

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
QUEUE_PATH = DATA_DIR / "recent_item_review_queue.csv"
SUMMARIES_PATH = DATA_DIR / "recent_item_summaries.csv"

QUEUE_COLUMNS = [
    "review_id",
    "summary_id",
    "recent_item_id",
    "document_id",
    "source_id",
    "institution_name",
    "item_title",
    "item_date",
    "strategic_theme",
    "headline",
    "summary",
    "core_assessment",
    "strategic_relevance",
    "impact_on_us",
    "recommended_action",
    "confidence_level",
    "item_url",
    "source_url",
    "review_status",
    "reviewer",
    "review_notes",
    "approved_at",
]

STATUS_OPTIONS = ["Beklemede", "Onaylandı", "Reddedildi", "Ek Araştırma Gerekli"]


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


def parse_json_list(value) -> list[str]:
    if pd.isna(value) or value == "":
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except Exception:
        pass
    return [str(value)]


def save_review(review_id: str, summary_id: str, status: str, reviewer: str, notes: str) -> None:
    queue_disk = read_csv(QUEUE_PATH, QUEUE_COLUMNS)
    summaries_disk = read_csv(SUMMARIES_PATH)
    approved_at = datetime.now(timezone.utc).isoformat() if status == "Onaylandı" else ""

    queue_mask = queue_disk["review_id"].eq(review_id)
    queue_disk.loc[queue_mask, "review_status"] = status
    queue_disk.loc[queue_mask, "reviewer"] = reviewer
    queue_disk.loc[queue_mask, "review_notes"] = notes
    queue_disk.loc[queue_mask, "approved_at"] = approved_at

    if "review_status" in summaries_disk.columns:
        summaries_mask = summaries_disk["summary_id"].eq(summary_id)
        summaries_disk.loc[summaries_mask, "review_status"] = status

    queue_disk.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
    summaries_disk.to_csv(SUMMARIES_PATH, index=False, encoding="utf-8-sig")
    st.success(f"{review_id} için karar kaydedildi: {status}")
    st.rerun()


queue = read_csv(QUEUE_PATH, QUEUE_COLUMNS)
summaries = read_csv(SUMMARIES_PATH)

st.title("Gelişme Onay Kuyruğu")
st.caption("Tekil haber, kampanya ve duyuru adayları yönetici radarına girmeden önce burada onaylanır.")
st.info(
    "Bu kuyruk yalnızca LLM tarafından potansiyel olarak ilgili görülen veya orta/yüksek etkili gelişmeleri içerir. "
    "Düşük öncelikli maddeler arşive alınır."
)

if queue.empty:
    st.info("Henüz onay bekleyen tekil gelişme özeti yok. Önce recent item pipeline’ını çalıştırın.")
    st.stop()

view = queue.copy()
if not summaries.empty:
    extra_cols = [
        "summary_id",
        "product_area",
        "development_type",
        "importance_level",
        "extracted_facts_json",
        "open_questions_json",
        "created_at",
        "error_message",
    ]
    available = [col for col in extra_cols if col in summaries.columns]
    view = view.merge(summaries[available], on="summary_id", how="left")

view["item_date_dt"] = pd.to_datetime(view["item_date"], errors="coerce", dayfirst=True, utc=True)
if view["item_date_dt"].isna().all() and "created_at" in view.columns:
    view["item_date_dt"] = pd.to_datetime(view["created_at"], errors="coerce", utc=True)
view["item_date_dt"] = view["item_date_dt"].fillna(pd.Timestamp.utcnow()).dt.tz_localize(None)

min_date = view["item_date_dt"].min().date()
max_date = view["item_date_dt"].max().date()

with st.sidebar:
    st.header("Onay Filtreleri")
    institutions = sorted(view["institution_name"].dropna().astype(str).unique())
    themes = sorted(view["strategic_theme"].dropna().astype(str).unique())
    impacts = sorted(view["impact_on_us"].dropna().astype(str).unique())
    confidences = sorted(view["confidence_level"].dropna().astype(str).unique())
    actions = sorted(view["recommended_action"].dropna().astype(str).unique())
    statuses = sorted(view["review_status"].dropna().astype(str).unique())

    selected_institutions = st.multiselect("Kurum", institutions, default=institutions)
    selected_themes = st.multiselect("Stratejik Tema", themes, default=themes)
    selected_impacts = st.multiselect("Etki Seviyesi", impacts, default=impacts)
    selected_confidences = st.multiselect("Güven Seviyesi", confidences, default=confidences)
    selected_actions = st.multiselect("Önerilen Aksiyon", actions, default=actions)
    selected_statuses = st.multiselect("Onay Durumu", statuses or STATUS_OPTIONS, default=statuses or ["Beklemede"])
    selected_range = st.date_input("Tarih aralığı", value=(min_date, max_date), min_value=min_date, max_value=max_date)

if isinstance(selected_range, tuple) and len(selected_range) == 2:
    start_date, end_date = selected_range
else:
    start_date, end_date = min_date, max_date

filtered = view[
    view["institution_name"].isin(selected_institutions)
    & view["strategic_theme"].isin(selected_themes)
    & view["impact_on_us"].isin(selected_impacts)
    & view["confidence_level"].isin(selected_confidences)
    & view["recommended_action"].isin(selected_actions)
    & view["review_status"].isin(selected_statuses)
    & (view["item_date_dt"].dt.date >= start_date)
    & (view["item_date_dt"].dt.date <= end_date)
].copy()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Görüntülenen", len(filtered))
k2.metric("Beklemede", view["review_status"].eq("Beklemede").sum())
k3.metric("Onaylandı", view["review_status"].eq("Onaylandı").sum())
k4.metric("Ek araştırma", view["review_status"].eq("Ek Araştırma Gerekli").sum())

table = filtered[
    [
        "review_id",
        "institution_name",
        "item_title",
        "strategic_theme",
        "impact_on_us",
        "recommended_action",
        "confidence_level",
        "review_status",
    ]
].copy()
st.dataframe(
    tr_columns(
        table,
        {
            "review_id": "Onay ID",
            "institution_name": "Kurum",
            "item_title": "Aday başlık",
            "strategic_theme": "Stratejik tema",
            "impact_on_us": "Etki",
            "recommended_action": "Önerilen aksiyon",
            "confidence_level": "Güven",
            "review_status": "Durum",
        },
    ),
    use_container_width=True,
    hide_index=True,
)

if filtered.empty:
    st.warning("Seçili filtrelerle eşleşen gelişme adayı yok.")
    st.stop()

st.subheader("Analist İncelemesi")
for _, row in filtered.sort_values(["review_status", "item_date_dt"], ascending=[True, False]).iterrows():
    label = f"{row['institution_name']} | {row['item_title']}"
    with st.expander(label, expanded=row["review_status"] == "Beklemede"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Etki", tr_label("impact_on_us", row["impact_on_us"]))
        c2.metric("Güven", tr_label("confidence_level", row["confidence_level"]))
        c3.metric("Aksiyon", tr_label("recommended_action", row["recommended_action"]))

        st.write(f"**Kurum:** {row['institution_name']}")
        st.write(f"**Aday başlık:** {row['item_title']}")
        st.write(f"**Tarih:** {format_turkish_date(row['item_date_dt'])}")
        st.write(f"**Radar başlığı:** {row['headline']}")
        if str(row.get("core_assessment", "") or "").strip():
            st.write(f"**Kısa değerlendirme:** {row['core_assessment']}")
        st.write(f"**Özet:** {row['summary']}")
        st.write(f"**Stratejik önem:** {row['strategic_relevance']}")

        facts = parse_json_list(row.get("extracted_facts_json", ""))
        questions = parse_json_list(row.get("open_questions_json", ""))
        if facts:
            st.write("**Çıkarılan bulgular**")
            for fact in facts:
                st.write(f"- {fact}")
        if questions:
            st.write("**Açık sorular**")
            for question in questions:
                st.write(f"- {question}")

        link_cols = st.columns(2)
        if str(row.get("item_url", "") or "").startswith("http"):
            link_cols[0].link_button("Gelişmeyi Aç", row["item_url"])
        if str(row.get("source_url", "") or "").startswith("http"):
            link_cols[1].link_button("Kaynağı Aç", row["source_url"])

        with st.form(f"review_form_{row['review_id']}"):
            current_status = row["review_status"] if row["review_status"] in STATUS_OPTIONS else "Beklemede"
            selected_status = st.radio(
                "Karar",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(current_status),
                horizontal=True,
            )
            reviewer = st.text_input("Analist", value="" if pd.isna(row.get("reviewer")) else str(row.get("reviewer", "")))
            notes = st.text_area("Not Ekle", value="" if pd.isna(row.get("review_notes")) else str(row.get("review_notes", "")))
            submitted = st.form_submit_button("Kaydet")
            if submitted:
                save_review(row["review_id"], row["summary_id"], selected_status, reviewer, notes)
