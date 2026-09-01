from __future__ import annotations

from pathlib import Path

import streamlit as st

from utils.page_runner import run_streamlit_page_without_page_config


ROOT = Path(__file__).resolve().parent


def render_yonetici_radari() -> None:
    run_streamlit_page_without_page_config(ROOT / "pages" / "1_Yonetici_Radari.py")


def render_tum_gelismeler() -> None:
    run_streamlit_page_without_page_config(ROOT / "pages" / "2_Tum_Gelismeler.py")


def render_yeni_musteri_teklifleri() -> None:
    run_streamlit_page_without_page_config(ROOT / "pages" / "6_Yeni_Musteri_Teklifleri.py")


def render_ucret_komisyon_matrisi() -> None:
    run_streamlit_page_without_page_config(ROOT / "pages" / "7_Ucret_Komisyon_Matrisi.py")


st.set_page_config(
    page_title="Akbank Yönetici Özeti",
    layout="wide",
    initial_sidebar_state="collapsed",
)

yonetici_page = st.Page(
    render_yonetici_radari,
    title="Yönetici Özeti",
    url_path="yonetici-radari",
    default=True,
)
tum_gelismeler_page = st.Page(
    render_tum_gelismeler,
    title="Tüm Gelişmeler",
    url_path="tum-gelismeler",
)
yeni_musteri_teklifleri_page = st.Page(
    render_yeni_musteri_teklifleri,
    title="Yeni Müşteri Teklifleri",
    url_path="yeni-musteri-teklifleri",
)
ucret_komisyon_matrisi_page = st.Page(
    render_ucret_komisyon_matrisi,
    title="Ücret Komisyon Matrisi",
    url_path="ucret-komisyon-matrisi",
)

page = st.navigation(
    [yonetici_page, tum_gelismeler_page, yeni_musteri_teklifleri_page, ucret_komisyon_matrisi_page],
    position="sidebar",
    expanded=True,
)

current_title = getattr(page, "title", "") or "Yönetici Özeti"
active_nav_key = {
    "Yönetici Özeti": "executive_nav_radar",
    "Tüm Gelişmeler": "executive_nav_all",
    "Yeni Müşteri Teklifleri": "executive_nav_new_customer",
    "Ücret Komisyon Matrisi": "executive_nav_pricing",
}.get(current_title, "executive_nav_radar")

st.markdown(
    """
    <style>
    .st-key-executive_page_switcher {
        margin: 1.65rem 0 1.15rem;
    }

    .st-key-executive_page_switcher div[data-testid="stHorizontalBlock"] {
        align-items: end;
    }

    .st-key-executive_page_switcher {
        display: flex;
        justify-content: flex-end;
    }

    .st-key-executive_page_switcher [data-baseweb="button-group"] {
        border-bottom: 1px solid var(--ak-border);
        gap: 0.75rem;
    }

    .st-key-executive_page_switcher [data-baseweb="button-group"] button {
        background: transparent !important;
        border: 0 !important;
        border-bottom: 2px solid transparent !important;
        border-radius: 0 !important;
        color: var(--ak-muted) !important;
        min-height: 2rem;
        padding: 0 0 0.38rem !important;
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
    }

    .st-key-executive_page_switcher [data-baseweb="button-group"] button[aria-pressed="true"],
    .st-key-executive_page_switcher [data-baseweb="button-group"] button[aria-selected="true"],
    .st-key-executive_page_switcher [data-baseweb="button-group"] button[kind="segmented_controlActive"] {
        color: var(--ak-text) !important;
        border-bottom-color: var(--ak-red) !important;
    }

    .st-key-executive_page_switcher [data-baseweb="button-group"] button[kind="segmented_controlActive"] p {
        color: var(--ak-text) !important;
    }

    .st-key-executive_page_switcher .stButton > button[kind="secondary"] {
        background: transparent !important;
        border: 0 !important;
        border-bottom: 2px solid transparent !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        color: var(--ak-muted) !important;
        min-height: 2rem !important;
        padding: 0 0 0.38rem !important;
    }

    .st-key-executive_page_switcher .stButton > button[kind="secondary"] p {
        color: inherit !important;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .st-key-executive_page_switcher .stButton > button[kind="secondary"]:hover {
        color: var(--ak-text) !important;
        border-bottom-color: var(--ak-border-strong);
    }

    .st-key-executive_page_switcher .stButton > button[kind="secondary"]:disabled {
        opacity: 1 !important;
        color: var(--ak-text) !important;
        border-bottom-color: var(--ak-red);
        cursor: default !important;
    }

    .st-key-executive_page_switcher .stButton > button[kind="secondary"]:disabled p {
        color: var(--ak-text) !important;
    }

    @media (max-width: 700px) {
        .st-key-executive_page_switcher {
            justify-content: center;
            margin: 1.4rem 0 1.05rem;
            padding: 0 1rem;
        }

        .st-key-executive_page_switcher [data-baseweb="button-group"] {
            width: 100%;
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.5rem;
        }

        .st-key-executive_page_switcher [data-baseweb="button-group"] button {
            justify-content: center;
            font-size: 0.68rem;
            letter-spacing: 0.06em;
            white-space: nowrap;
        }
    }
    """
    + f"""

    .st-key-executive_page_switcher .st-key-{active_nav_key} .stButton > button[kind="secondary"] {{
        color: var(--ak-text) !important;
        border-bottom-color: var(--ak-red) !important;
    }}

    .st-key-executive_page_switcher .st-key-{active_nav_key} .stButton > button[kind="secondary"] p {{
        color: var(--ak-text) !important;
    }}
    """
    + """
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="executive_page_switcher"):
    selected_page = st.segmented_control(
        "Sayfa",
        ["Yönetici Özeti", "Tüm Gelişmeler", "Yeni Müşteri Teklifleri", "Ücret Komisyon Matrisi"],
        default=current_title,
        key="executive_nav_segment",
        label_visibility="collapsed",
    )

if selected_page == "Yönetici Özeti" and current_title != "Yönetici Özeti":
    st.switch_page(yonetici_page)
if selected_page == "Tüm Gelişmeler" and current_title != "Tüm Gelişmeler":
    st.switch_page(tum_gelismeler_page)
if selected_page == "Yeni Müşteri Teklifleri" and current_title != "Yeni Müşteri Teklifleri":
    st.switch_page(yeni_musteri_teklifleri_page)
if selected_page == "Ücret Komisyon Matrisi" and current_title != "Ücret Komisyon Matrisi":
    st.switch_page(ucret_komisyon_matrisi_page)

page.run()
