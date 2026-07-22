from __future__ import annotations

from pathlib import Path

import streamlit as st

from utils.page_runner import run_streamlit_page_without_page_config


ROOT = Path(__file__).resolve().parent


def render_review_queue() -> None:
    run_streamlit_page_without_page_config(ROOT / "pages" / "3_Analist_Onay_Kuyrugu.py")


def render_archive() -> None:
    run_streamlit_page_without_page_config(ROOT / "pages" / "4_Elenen_Dusuk_Oncelik.py")


def render_source_health() -> None:
    run_streamlit_page_without_page_config(ROOT / "pages" / "5_Kaynak_Sagligi.py")


st.set_page_config(
    page_title="Akbank Analist Operasyon Paneli",
    layout="wide",
    initial_sidebar_state="expanded",
)

review_page = st.Page(
    render_review_queue,
    title="Analist Onay Kuyruğu",
    url_path="analist-onay-kuyrugu",
    default=True,
)
archive_page = st.Page(
    render_archive,
    title="Elenen Düşük Öncelik",
    url_path="elenen-dusuk-oncelik",
)
source_health_page = st.Page(
    render_source_health,
    title="Kaynak Sağlığı",
    url_path="kaynak-sagligi",
)

page = st.navigation(
    {
        "Analist Operasyon": [review_page],
        "Kontrol & Sağlık": [archive_page, source_health_page],
    },
    position="sidebar",
    expanded=True,
)

page.run()
