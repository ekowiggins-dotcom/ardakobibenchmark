from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data_loader import load_all_data
from utils.translations import tr_columns, tr_label


st.set_page_config(page_title="Benchmark Bulguları Onay Kuyruğu", layout="wide")

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
FACTS_PATH = DATA_DIR / "benchmark_facts.csv"
QUEUE_PATH = DATA_DIR / "benchmark_fact_review_queue.csv"

QUEUE_COLUMNS = [
    "review_id",
    "fact_id",
    "document_id",
    "source_id",
    "institution_name",
    "product_area",
    "benchmark_dimension",
    "fact_type",
    "fact_text",
    "strategic_relevance",
    "confidence_level",
    "review_status",
    "reviewer",
    "review_notes",
    "approved_at",
]

data = load_all_data()
facts = data["benchmark_facts"].copy()
queue = data["benchmark_fact_review_queue"].copy()
metadata = data["raw_documents_metadata"].copy()

st.title("Benchmark Bulguları Onay Kuyruğu")
st.caption("Stabil ürün ve kaynak sayfalarından çıkarılan benchmark bulguları için analist onay alanı.")

STATUS_LABELS = {
    "Onayla": "Approved",
    "Reddet": "Rejected",
    "Ek Araştırma Gerekli": "Needs More Research",
    "Beklemede Bırak": "Pending",
}
STATUS_BY_VALUE = {value: label for label, value in STATUS_LABELS.items()}


def review_id_for(fact_id: str) -> str:
    return f"BFREV-{fact_id.replace('FACT-', '')}"


def sync_queue(facts_df: pd.DataFrame, queue_df: pd.DataFrame) -> pd.DataFrame:
    existing = set(queue_df["fact_id"].dropna()) if not queue_df.empty else set()
    new_rows = []
    for _, row in facts_df.iterrows():
        if row["fact_id"] in existing:
            continue
        new_rows.append(
            {
                "review_id": review_id_for(row["fact_id"]),
                "fact_id": row["fact_id"],
                "document_id": row["document_id"],
                "source_id": row["source_id"],
                "institution_name": row["institution_name"],
                "product_area": row["product_area"],
                "benchmark_dimension": row["benchmark_dimension"],
                "fact_type": row["fact_type"],
                "fact_text": row["fact_text"],
                "strategic_relevance": row.get("strategic_relevance", ""),
                "confidence_level": row["confidence_level"],
                "review_status": "Pending",
                "reviewer": "",
                "review_notes": "",
                "approved_at": "",
            }
        )
    updated = pd.concat([queue_df, pd.DataFrame(new_rows)], ignore_index=True) if new_rows else queue_df
    updated = updated.reindex(columns=QUEUE_COLUMNS)
    updated.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
    return updated


def save_review(review_id: str, fact_id: str, status: str, reviewer: str, notes: str) -> None:
    queue_disk = pd.read_csv(QUEUE_PATH, encoding="utf-8-sig")
    facts_disk = pd.read_csv(FACTS_PATH, encoding="utf-8-sig")
    mask = queue_disk["review_id"].eq(review_id)
    approved_at = datetime.now(timezone.utc).isoformat() if status == "Approved" else ""
    queue_disk.loc[mask, "review_status"] = status
    queue_disk.loc[mask, "reviewer"] = reviewer
    queue_disk.loc[mask, "review_notes"] = notes
    queue_disk.loc[mask, "approved_at"] = approved_at
    facts_disk.loc[facts_disk["fact_id"].eq(fact_id), "review_status"] = status
    queue_disk.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
    facts_disk.to_csv(FACTS_PATH, index=False, encoding="utf-8-sig")
    st.success(f"{review_id} için karar kaydedildi: {tr_label('review_status', status)}")
    st.rerun()


if facts.empty:
    st.info("Henüz benchmark bulgusu yok. Sayfalar toplandıktan ve değişim tespiti yapıldıktan sonra `run_benchmark_fact_extraction.py` çalıştırın.")
else:
    queue = sync_queue(facts, queue)
    view = queue.merge(
        facts[["fact_id", "source_type", "source_url", "extracted_at", "strategic_relevance"]],
        on="fact_id",
        how="left",
        suffixes=("", "_fact"),
    )
    if "strategic_relevance_fact" in view.columns:
        view["strategic_relevance"] = view["strategic_relevance"].fillna(view["strategic_relevance_fact"])
    if not metadata.empty:
        view = view.merge(metadata[["document_id", "cleaned_text_path", "raw_html_path", "title"]], on="document_id", how="left")
    else:
        view["cleaned_text_path"] = ""
        view["title"] = ""

    with st.sidebar:
        st.header("Bulgu Filtreleri")
        institution_filter = st.multiselect("Kurum", sorted(view["institution_name"].dropna().unique()), default=sorted(view["institution_name"].dropna().unique()))
        product_area_filter = st.multiselect("Ürün alanı", sorted(view["product_area"].dropna().unique()), default=sorted(view["product_area"].dropna().unique()))
        dimension_filter = st.multiselect("Benchmark boyutu", sorted(view["benchmark_dimension"].dropna().unique()), default=sorted(view["benchmark_dimension"].dropna().unique()))
        confidence_filter = st.multiselect("Güven seviyesi", sorted(view["confidence_level"].dropna().unique()), default=sorted(view["confidence_level"].dropna().unique()), format_func=lambda x: tr_label("confidence_level", x))
        status_filter = st.multiselect("Onay durumu", ["Pending", "Approved", "Rejected", "Needs More Research"], default=["Pending", "Approved", "Rejected", "Needs More Research"], format_func=lambda x: tr_label("review_status", x))

    filtered = view[
        view["institution_name"].isin(institution_filter)
        & view["product_area"].isin(product_area_filter)
        & view["benchmark_dimension"].isin(dimension_filter)
        & view["confidence_level"].isin(confidence_filter)
        & view["review_status"].isin(status_filter)
    ].copy()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Görüntülenen bulgu", len(filtered))
    k2.metric("Beklemede", view["review_status"].eq("Pending").sum())
    k3.metric("Onaylandı", view["review_status"].eq("Approved").sum())
    k4.metric("Ek araştırma", view["review_status"].eq("Needs More Research").sum())

    st.subheader("Çıkarılan Benchmark Bulguları")
    table = filtered[["review_id", "institution_name", "product_area", "benchmark_dimension", "fact_type", "fact_text", "confidence_level", "review_status"]].copy()
    table["confidence_level"] = table["confidence_level"].apply(lambda x: tr_label("confidence_level", x))
    table["review_status"] = table["review_status"].apply(lambda x: tr_label("review_status", x))
    st.dataframe(
        tr_columns(table, {"review_id": "Onay ID", "institution_name": "Kurum", "product_area": "Ürün alanı", "benchmark_dimension": "Benchmark boyutu", "fact_type": "Bulgu tipi", "fact_text": "Bulgu", "confidence_level": "Güven", "review_status": "Durum"}),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Analist İncelemesi")
    for _, row in filtered.iterrows():
        with st.expander(f"{row['review_id']} | {row['institution_name']} | {row['fact_type']}"):
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Bulgu**")
                st.write(row["fact_text"])
                st.write("**Stratejik önem**")
                st.write(row.get("strategic_relevance", ""))
            with c2:
                st.write("**Kaynak**")
                if row.get("source_url"):
                    st.markdown(f"[Kaynağı Aç]({row['source_url']})")
                st.write(f"Temizlenmiş Metni Gör: `{row.get('cleaned_text_path', '')}`")
                st.write(f"Kaynak başlığı: {row.get('title', '')}")

            with st.form(f"fact_review_{row['review_id']}"):
                current_label = STATUS_BY_VALUE.get(row["review_status"], "Beklemede Bırak")
                decision_label = st.selectbox("Karar", list(STATUS_LABELS.keys()), index=list(STATUS_LABELS.keys()).index(current_label))
                reviewer = st.text_input("Analist", value=row["reviewer"] if isinstance(row.get("reviewer"), str) else "")
                notes = st.text_area("Not Ekle", value=row["review_notes"] if isinstance(row.get("review_notes"), str) else "")
                if st.form_submit_button("Kaydet"):
                    save_review(row["review_id"], row["fact_id"], STATUS_LABELS[decision_label], reviewer, notes)
