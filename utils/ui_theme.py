from __future__ import annotations

import html

import streamlit as st


PALETTE = {
    "primary_red": "#E30613",
    "primary_red_dark": "#B9000C",
    "bg_main": "#ECEFF3",
    "bg_surface": "#FFFFFF",
    "bg_soft": "#F5F6F8",
    "bg_sidebar": "#F8F9FB",
    "border": "#D0D7DE",
    "border_strong": "#BCC5D0",
    "text_main": "#17212F",
    "text_secondary": "#566273",
    "text_muted": "#727D8E",
    "chip_bg": "#FFF5F5",
    "chip_border": "#FFD9DE",
    "chip_text": "#B9000C",
}


def apply_akbank_theme() -> None:
    """Apply the shared Akbank-inspired MVP visual system."""

    st.markdown(
        f"""
        <style>
        :root {{
            --ak-red: {PALETTE["primary_red"]};
            --ak-red-dark: {PALETTE["primary_red_dark"]};
            --ak-bg: {PALETTE["bg_main"]};
            --ak-surface: {PALETTE["bg_surface"]};
            --ak-soft: {PALETTE["bg_soft"]};
            --ak-sidebar: {PALETTE["bg_sidebar"]};
            --ak-border: {PALETTE["border"]};
            --ak-border-strong: {PALETTE["border_strong"]};
            --ak-text: {PALETTE["text_main"]};
            --ak-secondary: {PALETTE["text_secondary"]};
            --ak-muted: {PALETTE["text_muted"]};
            --ak-chip-bg: {PALETTE["chip_bg"]};
            --ak-chip-border: {PALETTE["chip_border"]};
            --ak-chip-text: {PALETTE["chip_text"]};
            --primary-color: {PALETTE["primary_red"]};
        }}

        html, body, .stApp, [data-testid="stAppViewContainer"] {{
            background: var(--ak-bg) !important;
            color: var(--ak-text) !important;
        }}

        [data-testid="stHeader"] {{
            background: rgba(236, 239, 243, 0.94) !important;
            border-bottom: 1px solid var(--ak-border-strong);
        }}

        .block-container {{
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1420px;
        }}

        h1, h2, h3 {{
            color: var(--ak-text) !important;
            letter-spacing: 0 !important;
        }}

        p, li, label, span, div {{
            color: inherit;
        }}

        [data-testid="stSidebar"] {{
            background: var(--ak-sidebar) !important;
            border-right: 1px solid var(--ak-border-strong);
        }}

        [data-testid="stSidebar"] * {{
            color: var(--ak-text) !important;
        }}

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
            color: var(--ak-text) !important;
        }}

        [data-testid="stSidebar"] .st-emotion-cache-1y4p8pa,
        [data-testid="stSidebar"] section {{
            background: var(--ak-sidebar) !important;
        }}

        [data-testid="stSidebar"] hr {{
            border-color: var(--ak-border) !important;
        }}

        [data-testid="stSidebarNav"] a {{
            border-radius: 0;
            color: var(--ak-text) !important;
            font-weight: 650;
            transition: background 120ms ease, color 120ms ease;
        }}

        [data-testid="stSidebarNav"] a:hover {{
            background: var(--ak-chip-bg) !important;
            color: var(--ak-red-dark) !important;
        }}

        [data-testid="stSidebar"] [aria-selected="true"],
        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background: var(--ak-chip-bg) !important;
            color: var(--ak-red-dark) !important;
            border-left: 3px solid var(--ak-red);
        }}

        .ak-page-header {{
            background: var(--ak-surface);
            border-top: 1px solid var(--ak-border);
            border-right: 1px solid var(--ak-border);
            border-bottom: 1px solid var(--ak-border-strong);
            border-left: 1px solid var(--ak-border);
            border-radius: 16px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.07);
            padding: 1.35rem 1.75rem;
            margin-bottom: 1.65rem;
        }}

        .ak-page-header-inner {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 2rem;
        }}

        .ak-page-header-main {{
            min-width: 0;
        }}

        .ak-page-meta {{
            flex: 0 0 auto;
            padding-top: 0.2rem;
            text-align: right;
            color: var(--ak-muted);
            font-size: 0.625rem;
            font-weight: 800;
            letter-spacing: 0.18em;
            line-height: 1.75;
            text-transform: none;
            white-space: nowrap;
        }}

        .ak-product-chip {{
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            color: var(--ak-red-dark);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }}

        .ak-product-chip::before {{
            content: "";
            width: 0.55rem;
            height: 0.55rem;
            border-radius: 999px;
            background: var(--ak-red);
            display: inline-block;
        }}

        .ak-page-header h1 {{
            margin: 0;
            font-size: clamp(2rem, 3vw, 3rem);
            line-height: 1.08;
            font-weight: 850;
            color: var(--ak-text) !important;
        }}

        .ak-page-header p {{
            margin: 0.75rem 0 0;
            max-width: 820px;
            color: var(--ak-secondary) !important;
            font-size: 1rem;
            line-height: 1.55;
        }}

        @media (max-width: 700px) {{
            .block-container {{
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-top: 1.15rem !important;
            }}

            .ak-page-header {{
                border-radius: 14px;
                padding: 1.15rem 1.15rem 1.2rem;
                margin-bottom: 1rem;
            }}

            .ak-page-header-inner {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 0.85rem;
            }}

            .ak-page-header-main {{
                width: 100%;
            }}

            .ak-product-chip {{
                max-width: 100%;
                align-items: flex-start;
                font-size: 0.68rem;
                letter-spacing: 0.09em;
                line-height: 1.35;
                margin-bottom: 0.65rem;
                overflow-wrap: normal;
                word-break: normal;
            }}

            .ak-page-header h1 {{
                font-size: clamp(2rem, 11vw, 2.55rem);
                line-height: 1.08;
                overflow-wrap: normal;
                word-break: normal;
                hyphens: none;
            }}

            .ak-page-header p {{
                max-width: 100%;
                font-size: 0.92rem;
                line-height: 1.48;
                overflow-wrap: normal;
                word-break: normal;
                hyphens: none;
            }}

            .ak-page-meta {{
                text-align: left;
                white-space: normal;
                font-size: 0.58rem;
                letter-spacing: 0.12em;
                line-height: 1.6;
                padding-top: 0;
                border-top: 1px solid var(--ak-border);
                padding-top: 0.75rem;
            }}
        }}

        [data-testid="stMetric"] {{
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-radius: 14px;
            padding: 1rem 1.05rem;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.07);
            min-height: 116px;
        }}

        [data-testid="stMetricLabel"] {{
            color: var(--ak-secondary) !important;
            font-size: 0.82rem !important;
            font-weight: 700;
        }}

        [data-testid="stMetricValue"] {{
            color: var(--ak-text) !important;
            font-weight: 800;
        }}

        [data-testid="stMetricDelta"] {{
            color: var(--ak-muted) !important;
        }}

        button[kind="primary"] {{
            background: var(--ak-red) !important;
            color: white !important;
            border: 1px solid var(--ak-red) !important;
            border-radius: 10px !important;
            font-weight: 750 !important;
        }}

        div[data-testid="stDownloadButton"] button {{
            background: var(--ak-red) !important;
            color: white !important;
            border: 1px solid var(--ak-red) !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            padding: 0.625rem 1rem !important;
            font-size: 0.6875rem !important;
            font-weight: 800 !important;
            letter-spacing: 0.16em !important;
            text-transform: uppercase !important;
        }}

        div[data-testid="stDownloadButton"] button:hover {{
            background: var(--ak-red) !important;
            color: white !important;
        }}

        button[kind="secondary"] {{
            background: var(--ak-surface) !important;
            color: var(--ak-text) !important;
            border: 1px solid var(--ak-border-strong) !important;
            border-radius: 0 !important;
            font-weight: 700 !important;
        }}

        button:hover {{
            border-color: var(--ak-border-strong) !important;
        }}

        div[data-testid="stExpander"] details,
        details {{
            background: var(--ak-surface) !important;
            border: 1px solid var(--ak-border) !important;
            border-radius: 14px !important;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.07);
        }}

        div[data-testid="stExpander"] summary,
        details summary {{
            color: var(--ak-text) !important;
            font-weight: 750;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--ak-surface) !important;
            border-color: var(--ak-border) !important;
            border-radius: 14px !important;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.07);
        }}

        [data-testid="stSidebar"] div[data-testid="stExpander"] details,
        [data-testid="stSidebar"] details,
        [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 0 !important;
            box-shadow: none !important;
            border-color: var(--ak-border) !important;
        }}

        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {{
            border: 1px solid var(--ak-border);
            border-radius: 14px;
            overflow: hidden;
            background: var(--ak-surface);
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.45rem;
            border-bottom: 1px solid var(--ak-border);
        }}

        .stTabs [data-baseweb="tab"] {{
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-bottom: 0;
            border-radius: 10px 10px 0 0;
            color: var(--ak-secondary);
            font-weight: 700;
        }}

        .stTabs [aria-selected="true"] {{
            color: var(--ak-text) !important;
            border-top: 1px solid var(--ak-border-strong);
        }}

        [data-testid="stAlert"] {{
            border-radius: 12px;
            border: 1px solid var(--ak-border);
        }}

        .stMultiSelect [data-baseweb="tag"],
        [data-baseweb="tag"] {{
            background: var(--ak-chip-bg) !important;
            color: var(--ak-chip-text) !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
        }}

        input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"] {{
            background: var(--ak-surface) !important;
            border-color: var(--ak-border) !important;
            color: var(--ak-text) !important;
            border-radius: 0 !important;
        }}

        a {{
            color: var(--ak-text) !important;
            text-decoration: none !important;
            text-underline-offset: 0.25rem;
        }}

        a:hover {{
            color: var(--ak-red-dark) !important;
            text-decoration: underline !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str = "", updated_at: str = "Canlı veri") -> None:
    subtitle_html = f"<p>{html.escape(subtitle)}</p>" if subtitle else ""
    updated_at_text = html.escape(updated_at or "Canlı veri")
    st.markdown(
        f"""
        <div class="ak-page-header">
          <div class="ak-page-header-inner">
            <div class="ak-page-header-main">
              <div class="ak-product-chip">Akbank KOBİ Rekabet Radarı</div>
              <h1>{html.escape(title)}</h1>
              {subtitle_html}
            </div>
            <div class="ak-page-meta">
              <div>ANALİZ EKİBİ: KOBİ İŞ GELİŞTİRME</div>
              <div>SON YAYIN: {updated_at_text}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
