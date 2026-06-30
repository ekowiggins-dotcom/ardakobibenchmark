from pathlib import Path

import pandas as pd
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


@st.cache_data(show_spinner=False)
def load_csv(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    return pd.read_csv(path, encoding="utf-8-sig")


@st.cache_data(show_spinner=False)
def load_all_data() -> dict[str, pd.DataFrame]:
    data = {
        "institutions": load_csv("institutions.csv"),
        "scores": load_csv("benchmark_scores.csv"),
        "deposits": load_csv("deposit_products.csv"),
        "embedded": load_csv("embedded_finance_features.csv"),
        "payments": load_csv("payments_features.csv"),
        "journeys": load_csv("digital_journey_features.csv"),
        "sources": load_csv("sources.csv"),
        "battlecards": load_csv("battlecards.csv"),
        "weekly_developments": load_csv("weekly_developments.csv"),
        "source_registry": load_csv("source_registry.csv"),
        "raw_documents_metadata": load_csv("raw_documents_metadata.csv"),
        "llm_extractions": load_csv("llm_extractions.csv"),
        "review_queue": load_csv("review_queue.csv"),
        "benchmark_facts": load_csv("benchmark_facts.csv"),
        "benchmark_fact_review_queue": load_csv("benchmark_fact_review_queue.csv"),
    }

    for key in ["scores", "deposits", "embedded", "payments", "journeys"]:
        if "last_updated" in data[key].columns:
            data[key]["last_updated"] = pd.to_datetime(data[key]["last_updated"])

    data["sources"]["date_accessed"] = pd.to_datetime(data["sources"]["date_accessed"])
    data["weekly_developments"]["date"] = pd.to_datetime(data["weekly_developments"]["date"])
    if not data["raw_documents_metadata"].empty:
        data["raw_documents_metadata"]["fetched_at"] = pd.to_datetime(
            data["raw_documents_metadata"]["fetched_at"], errors="coerce"
        )
    if not data["llm_extractions"].empty:
        data["llm_extractions"]["created_at"] = pd.to_datetime(
            data["llm_extractions"]["created_at"], errors="coerce"
        )
    if not data["review_queue"].empty:
        data["review_queue"]["approved_at"] = pd.to_datetime(
            data["review_queue"]["approved_at"], errors="coerce"
        )
    if not data["benchmark_facts"].empty:
        data["benchmark_facts"]["extracted_at"] = pd.to_datetime(
            data["benchmark_facts"]["extracted_at"], errors="coerce"
        )
    if not data["benchmark_fact_review_queue"].empty:
        data["benchmark_fact_review_queue"]["approved_at"] = pd.to_datetime(
            data["benchmark_fact_review_queue"]["approved_at"], errors="coerce"
        )
    return data


def with_institution_names(df: pd.DataFrame, institutions: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "institution_id",
        "institution_name",
        "institution_type",
        "country",
        "region",
        "strategic_notes",
    ]
    return df.merge(institutions[columns], on="institution_id", how="left")


def institution_options(institutions: pd.DataFrame) -> dict[str, str]:
    return dict(zip(institutions["institution_name"], institutions["institution_id"]))
