from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(ROOT_DIR))

from utils.translations import PHRASE_TRANSLATIONS, to_tr

SKIP_COLUMNS = {
    "url",
    "website",
    "source_url",
    "raw_html_path",
    "cleaned_text_path",
    "content_hash",
    "document_id",
    "source_id",
    "fact_id",
    "review_id",
    "extraction_id",
    "development_id",
    "llm_model",
    "model",
    "review_status",
    "status",
    "change_status",
}

CSV_FILES = [
    "source_registry.csv",
    "benchmark_facts.csv",
    "benchmark_fact_review_queue.csv",
    "llm_extractions.csv",
    "review_queue.csv",
    "weekly_developments.csv",
    "benchmark_scores.csv",
    "deposit_products.csv",
    "embedded_finance_features.csv",
    "payments_features.csv",
    "digital_journey_features.csv",
    "battlecards.csv",
    "institutions.csv",
    "sources.csv",
    "raw_documents_metadata.csv",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def translate_cell(value):
    if not isinstance(value, str):
        return value
    translated = value
    for old, new in PHRASE_TRANSLATIONS.items():
        translated = translated.replace(old, new)
    return to_tr(translated)


def translate_file(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    df = pd.read_csv(path, encoding="utf-8-sig")
    changed_cells = 0
    for col in df.columns:
        if col in SKIP_COLUMNS:
            continue
        if not pd.api.types.is_object_dtype(df[col]):
            continue
        before = df[col].copy()
        df[col] = df[col].apply(translate_cell)
        changed_cells += (before.fillna("") != df[col].fillna("")).sum()

    df.to_csv(path, index=False, encoding="utf-8-sig")
    return len(df), int(changed_cells)


def main() -> None:
    total_changed = 0
    for filename in CSV_FILES:
        rows, changed = translate_file(DATA_DIR / filename)
        total_changed += changed
        logging.info("%s | rows=%s | changed_cells=%s", filename, rows, changed)
    logging.info("Toplam değişen hücre: %s", total_changed)


if __name__ == "__main__":
    main()
