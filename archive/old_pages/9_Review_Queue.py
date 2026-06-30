import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data_loader import load_all_data
from utils.translations import tr_columns, tr_label


st.set_page_config(page_title="Analist Onay Kuyruğu", layout="wide")

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
QUEUE_PATH = DATA_DIR / "review_queue.csv"
EXTRACTIONS_PATH = DATA_DIR / "llm_extractions.csv"

data = load_all_data()
queue = data["review_queue"].copy()
extractions = data["llm_extractions"].copy()
registry = data["source_registry"].copy()
metadata = data["raw_documents_metadata"].copy()

st.title("Analist Onay Kuyruğu")
st.caption("Haftalık gelişme çıkarımı için LLM/dry-run taslaklarının insan onay kapısı.")

STATUS_LABELS = {
    "Onayla": "Approved",
    "Reddet": "Rejected",
    "Ek Araştırma Gerekli": "Needs More Research",
    "Beklemede Bırak": "Pending",
}
STATUS_BY_VALUE = {value: label for label, value in STATUS_LABELS.items()}


def parse_json_list(value):
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [str(parsed)]
    except Exception:
        return [value]


def save_review_status(review_id, extraction_id, status, reviewer, notes):
    queue_disk = pd.read_csv(QUEUE_PATH, encoding="utf-8-sig")
    extractions_disk = pd.read_csv(EXTRACTIONS_PATH, encoding="utf-8-sig")
    mask = queue_disk["review_id"].eq(review_id)
    if not mask.any():
        st.error(f"Onay maddesi bulunamadı: {review_id}")
        return

    approved_at = datetime.now(timezone.utc).isoformat() if status == "Approved" else ""
    queue_disk.loc[mask, "review_status"] = status
    queue_disk.loc[mask, "reviewer"] = reviewer
    queue_disk.loc[mask, "review_notes"] = notes
    queue_disk.loc[mask, "approved_at"] = approved_at
    extractions_disk.loc[extractions_disk["extraction_id"].eq(extraction_id), "review_status"] = status

    queue_disk.to_csv(QUEUE_PATH, index=False, encoding="utf-8-sig")
    extractions_disk.to_csv(EXTRACTIONS_PATH, index=False, encoding="utf-8-sig")
    st.success(f"{review_id} için karar kaydedildi: {tr_label('review_status', status)}")
    st.rerun()


if queue.empty:
    st.info("Henüz onay kuyruğu maddesi yok. Haftalık gelişme çıkarımı ve `update_review_queue.py` çalıştırıldıktan sonra burada görünecek.")
else:
    review = queue.merge(
        extractions,
        on=["extraction_id", "document_id", "source_id"],
        how="left",
        suffixes=("_review", ""),
    ).merge(
        registry[["source_id", "tier", "source_type", "source_name", "url", "strategic_themes"]],
        on="source_id",
        how="left",
    )
    if not metadata.empty:
        review = review.merge(
            metadata[["document_id", "title", "fetched_at", "cleaned_text_path", "raw_html_path", "status"]],
            on="document_id",
            how="left",
        )
    else:
        review["cleaned_text_path"] = ""

    review["review_status"] = review["review_status_review"].fillna(review.get("review_status", "Pending"))
    review["confidence_level"] = review["confidence_level_review"].fillna(review.get("confidence_level", "Low"))
    review["impact_on_us"] = review["impact_on_us_review"].fillna(review.get("impact_on_us", "Low"))
    review["recommended_action"] = review["recommended_action_review"].fillna(review.get("recommended_action", "Monitor"))

    with st.sidebar:
        st.header("Onay Filtreleri")
        status_filter = st.multiselect("Onay durumu", ["Pending", "Approved", "Rejected", "Needs More Research"], default=["Pending"], format_func=lambda x: tr_label("review_status", x))
        institution_filter = st.multiselect("Kurum", sorted(review["institution_name"].dropna().unique()), default=sorted(review["institution_name"].dropna().unique()))
        theme_filter = st.multiselect("Tema", sorted(review["strategic_theme"].dropna().unique()), default=sorted(review["strategic_theme"].dropna().unique()), format_func=lambda x: tr_label("strategic_theme", x))
        impact_filter = st.multiselect("Etki", sorted(review["impact_on_us"].dropna().unique()), default=sorted(review["impact_on_us"].dropna().unique()), format_func=lambda x: tr_label("impact_on_us", x))
        confidence_filter = st.multiselect("Güven", sorted(review["confidence_level"].dropna().unique()), default=sorted(review["confidence_level"].dropna().unique()), format_func=lambda x: tr_label("confidence_level", x))
        tier_filter = st.multiselect("Kaynak seviyesi", sorted(review["tier"].dropna().unique()), default=sorted(review["tier"].dropna().unique()))

    filtered = review[
        review["review_status"].isin(status_filter)
        & review["institution_name"].isin(institution_filter)
        & review["strategic_theme"].isin(theme_filter)
        & review["impact_on_us"].isin(impact_filter)
        & review["confidence_level"].isin(confidence_filter)
        & review["tier"].isin(tier_filter)
    ].copy()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Görüntülenen madde", len(filtered))
    k2.metric("Beklemede", review["review_status"].eq("Pending").sum())
    k3.metric("Onaylandı", review["review_status"].eq("Approved").sum())
    k4.metric("Ek araştırma", review["review_status"].eq("Needs More Research").sum())

    if filtered.empty:
        st.warning("Seçili filtrelerle eşleşen onay maddesi yok.")
    else:
        st.subheader("Haftalık Gelişme Taslakları")
        table = filtered[
            ["review_id", "institution_name", "headline", "strategic_theme", "impact_on_us", "recommended_action", "confidence_level", "tier", "source_type", "review_status"]
        ].copy()
        table["strategic_theme"] = table["strategic_theme"].apply(lambda x: tr_label("strategic_theme", x))
        table["impact_on_us"] = table["impact_on_us"].apply(lambda x: tr_label("impact_on_us", x))
        table["recommended_action"] = table["recommended_action"].apply(lambda x: tr_label("recommended_action", x))
        table["confidence_level"] = table["confidence_level"].apply(lambda x: tr_label("confidence_level", x))
        table["review_status"] = table["review_status"].apply(lambda x: tr_label("review_status", x))
        st.dataframe(
            tr_columns(table, {"review_id": "Onay ID", "institution_name": "Kurum", "headline": "Başlık", "strategic_theme": "Tema", "impact_on_us": "Etki", "recommended_action": "Aksiyon", "confidence_level": "Güven", "tier": "Seviye", "source_type": "Kaynak tipi", "review_status": "Durum"}),
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Analist İncelemesi")
        for _, row in filtered.iterrows():
            label = f"{row['review_id']} | {row['institution_name']} | {row['headline']}"
            with st.expander(label, expanded=row["review_status"] == "Pending"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Özet**")
                    st.write(row.get("summary", ""))
                    st.write("**Stratejik önem**")
                    st.write(row.get("strategic_relevance", ""))
                    st.write("**Kaynağa dayalı maddeler**")
                    facts = parse_json_list(row.get("extracted_facts_json", ""))
                    for fact in facts or ["Madde bulunmuyor."]:
                        st.write(f"- {fact}")
                with c2:
                    st.write("**Açık sorular**")
                    questions = parse_json_list(row.get("open_questions_json", ""))
                    for question in questions or ["Açık soru bulunmuyor."]:
                        st.write(f"- {question}")
                    st.write("**Kaynak**")
                    if pd.notna(row.get("url")) and row.get("url"):
                        st.markdown(f"[Kaynağı Aç]({row['url']})")
                    st.write(f"Temizlenmiş Metni Gör: `{row.get('cleaned_text_path', '')}`")

                with st.form(f"review_form_{row['review_id']}"):
                    current_label = STATUS_BY_VALUE.get(row["review_status"], "Beklemede Bırak")
                    decision_label = st.selectbox("Karar", list(STATUS_LABELS.keys()), index=list(STATUS_LABELS.keys()).index(current_label))
                    reviewer = st.text_input("Analist", value=row["reviewer"] if isinstance(row.get("reviewer"), str) else "")
                    notes = st.text_area("Not Ekle", value=row["review_notes"] if isinstance(row.get("review_notes"), str) else "")
                    if st.form_submit_button("Kaydet"):
                        save_review_status(row["review_id"], row["extraction_id"], STATUS_LABELS[decision_label], reviewer, notes)
