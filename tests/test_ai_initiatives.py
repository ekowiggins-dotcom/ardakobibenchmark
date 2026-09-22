from pathlib import Path

import pandas as pd


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "bank_ai_initiatives.csv"
EXPECTED_BANKS = {"Akbank", "Garanti BBVA", "İş Bankası", "Yapı Kredi"}
REQUIRED_COLUMNS = {
    "initiative_id",
    "institution_name",
    "institution_tier",
    "initiative_name",
    "ai_category",
    "initiative_type",
    "target_segment",
    "sme_relevance",
    "description",
    "ai_capability",
    "delivery_model",
    "evidence_level",
    "source_url",
    "last_verified",
    "akbank_relevance",
}


def read_ai_initiatives() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH, dtype=str).fillna("")


def test_ai_initiative_schema_and_ids_are_valid() -> None:
    frame = read_ai_initiatives()

    assert REQUIRED_COLUMNS.issubset(frame.columns)
    assert frame["initiative_id"].is_unique
    assert frame["initiative_id"].str.fullmatch(r"AI-\d{3}").all()
    assert not frame[list(REQUIRED_COLUMNS)].eq("").any().any()


def test_tier_one_bank_coverage_is_balanced() -> None:
    frame = read_ai_initiatives()
    counts = frame.groupby("institution_name").size()

    assert set(counts.index) == EXPECTED_BANKS
    assert counts.min() >= 5
    assert frame["institution_tier"].eq("Tier 1").all()


def test_every_ai_initiative_has_an_official_source() -> None:
    frame = read_ai_initiatives()

    assert frame["source_url"].str.startswith("https://").all()
    assert frame["evidence_level"].isin({"Yüksek", "Orta"}).all()
    assert frame["sme_relevance"].isin({"Yüksek", "Orta", "Dolaylı", "Düşük"}).all()


def test_ai_dataset_includes_direct_sme_and_saas_signals() -> None:
    frame = read_ai_initiatives()

    assert frame["sme_relevance"].eq("Yüksek").any()
    assert frame["delivery_model"].eq("Partner SaaS").any()
    assert frame["ai_category"].eq("KOBİ AI Çözümü").any()
