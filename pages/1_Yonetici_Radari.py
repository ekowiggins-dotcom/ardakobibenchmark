from __future__ import annotations

from datetime import datetime
import html
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from utils.display_text import build_executive_why_it_matters, clean_display_text
from utils.recent_mvp import (
    ARCHIVE_COLUMNS,
    CLUSTER_COLUMNS,
    QUEUE_COLUMNS,
    RECENT_ITEM_COLUMNS,
    SUMMARY_COLUMNS,
    WEEKLY_COLUMNS,
    add_sort_columns,
    clean_text,
    parse_json_list,
    read_csv_safe,
    real_published_weekly,
)
from utils.institution_aliases import institution_group
from utils.ui_theme import apply_akbank_theme, render_page_header


st.set_page_config(page_title="Yönetici Özeti", layout="wide")
apply_akbank_theme()

st.markdown(
    """
    <style>
    :root {
        --radar-red: #E30613;
        --radar-page-bg: #F3F5F7;
        --radar-card-bg: #FFFFFF;
        --radar-subtle-bg: #F8F9FB;
        --radar-summary-bg: #FFF7F7;
        --radar-primary-text: #172033;
        --radar-secondary-text: #667085;
        --radar-border: #D9DEE7;
        --radar-soft-border: #E7EAF0;
        --radar-card-shadow: 0 4px 16px rgba(16, 24, 40, 0.06);
        --radar-card-shadow-open: 0 8px 22px rgba(16, 24, 40, 0.08);
    }

    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMain"] > div,
    section.main,
    .main,
    .block-container {
        background: var(--radar-page-bg) !important;
    }

    .block-container {
        max-width: 1320px !important;
        padding-left: clamp(1rem, 2.1vw, 2rem) !important;
        padding-right: clamp(1rem, 2.1vw, 2rem) !important;
        padding-top: 1.35rem !important;
    }

    [data-testid="stAppViewContainer"] [data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stAppViewContainer"] [data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] > div {
        background-color: var(--radar-page-bg) !important;
        background: var(--radar-page-bg) !important;
        border: 0 !important;
        box-shadow: none !important;
    }

    .ak-page-header {
        border-color: var(--radar-border) !important;
        box-shadow: var(--radar-card-shadow) !important;
        margin-bottom: 1.25rem !important;
    }

    [data-testid="stMain"] hr {
        margin: 1.35rem 0 1.1rem !important;
        border-color: var(--radar-border) !important;
    }

    .radar-kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.9rem;
        margin: 1rem 0 1.35rem;
    }

    .radar-kpi-card {
        background: var(--radar-card-bg);
        border: 1px solid var(--radar-border);
        border-left: 2px solid var(--radar-border);
        border-radius: 14px;
        min-height: 124px;
        padding: 1.25rem 1.35rem 1.18rem;
        box-shadow: var(--radar-card-shadow);
        position: relative;
        overflow: hidden;
    }

    .radar-kpi-label {
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--radar-secondary-text);
        margin-bottom: 0.6rem;
    }

    .radar-kpi-value {
        font-size: 2.65rem;
        line-height: 1;
        font-weight: 850;
        letter-spacing: -0.04em;
        color: var(--radar-primary-text);
    }

    .radar-kpi-range {
        color: var(--radar-secondary-text);
        font-size: 0.5625rem;
        font-weight: 800;
        letter-spacing: 0.18em;
        line-height: 1.35;
        margin-top: 0.35rem;
        text-transform: uppercase;
    }

    .radar-kpi-rank {
        display: grid;
        grid-template-columns: 1.75rem 1fr 2rem;
        gap: 0.45rem;
        font-size: 0.9rem;
        line-height: 1.65;
        font-variant-numeric: tabular-nums;
        color: var(--radar-primary-text);
        background: var(--radar-subtle-bg);
        border: 1px solid var(--radar-border);
        border-radius: 10px;
        padding: 0.15rem 0.5rem;
        margin-bottom: 0.35rem;
    }

    .radar-watchlist {
        background: var(--radar-card-bg);
        border: 1px solid var(--radar-border);
        border-left: 3px solid var(--radar-red);
        border-radius: 14px;
        padding: 1.55rem 1.75rem;
        margin: 0 0 1.45rem;
        box-shadow: var(--radar-card-shadow-open);
    }

    .radar-watchlist-kicker {
        color: var(--radar-red);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin-bottom: 0.75rem;
        background: var(--radar-summary-bg);
        border: 1px solid var(--radar-soft-border);
        border-radius: 999px;
        display: inline-flex;
        padding: 0.18rem 0.62rem;
    }

    .radar-watchlist-title {
        font-size: 1.65rem;
        line-height: 1.2;
        font-weight: 800;
        margin-bottom: 1rem;
        color: var(--radar-primary-text);
    }

    .radar-watchlist-body {
        font-size: 1.05rem;
        line-height: 1.65;
        max-width: 1100px;
        color: var(--radar-secondary-text);
    }

    .radar-watchlist-list {
        display: grid;
        gap: 0;
        max-width: 1160px;
    }

    .radar-watchlist-item {
        display: grid;
        grid-template-columns: minmax(220px, 0.42fr) minmax(0, 1fr);
        column-gap: 2.5rem;
        align-items: baseline;
        padding: 1.25rem 0;
        border-bottom: 1px solid var(--radar-border);
    }

    .radar-watchlist-item:first-child {
        padding-top: 0;
    }

    .radar-watchlist-item-title {
        font-weight: 800;
        line-height: 1.35;
        min-width: 0;
        color: var(--radar-primary-text);
    }

    .radar-watchlist-item-copy {
        line-height: 1.55;
        color: var(--radar-secondary-text);
        min-width: 0;
        overflow-wrap: anywhere;
    }

    .radar-detail-head {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 1.25rem;
        align-items: start;
        padding: 1.05rem 1.15rem;
        border: 1px solid var(--radar-soft-border);
        border-radius: 12px;
        background: var(--radar-subtle-bg);
        margin-bottom: 1rem;
    }

    .radar-detail-meta {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.55rem;
        margin-bottom: 0.6rem;
        font-size: 0.76rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--radar-secondary-text);
    }

    .radar-bank-chip {
        display: inline-flex;
        align-items: center;
        min-height: 1.4rem;
        padding: 0.12rem 0.45rem;
        background: var(--radar-card-bg);
        color: var(--radar-primary-text);
        border: 1px solid var(--radar-border);
        border-radius: 8px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0;
    }

    .radar-detail-title {
        font-size: 1.08rem;
        line-height: 1.35;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin-bottom: 0;
        color: var(--radar-primary-text);
        overflow: visible;
        white-space: normal;
    }

    .radar-detail-summary {
        font-size: 0.875rem;
        line-height: 1.55;
        font-weight: 500;
        color: var(--radar-primary-text);
        max-width: none;
        background: var(--radar-summary-bg);
        border: 1px solid var(--radar-soft-border);
        border-left: 3px solid var(--radar-red);
        border-radius: 12px;
        padding: 0.9rem 1rem;
        margin-bottom: 1rem;
        white-space: normal;
        overflow: visible;
        height: auto;
        max-height: none;
    }

    .radar-detail-side {
        text-align: right;
        white-space: normal;
        font-size: 0.74rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--radar-secondary-text);
        display: grid;
        justify-items: end;
        gap: 0.55rem;
    }

    .radar-dot {
        display: inline-block;
        width: 0.5rem;
        height: 0.5rem;
        border-radius: 999px;
        background: var(--ak-muted);
        margin: 0 0.5rem;
        vertical-align: 0.06rem;
    }

    .radar-detail-actions {
        display: flex;
        gap: 0.75rem;
        align-items: center;
        padding-bottom: 0;
        border-bottom: 0;
        margin-bottom: 0;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--ak-secondary);
    }

    .radar-detail-actions a {
        color: inherit !important;
        text-decoration: none !important;
    }

    .radar-source-button {
        display: inline-flex;
        align-items: center;
        border: 1px solid var(--radar-border);
        border-radius: 999px;
        padding: 0.3rem 0.72rem;
        color: var(--radar-primary-text) !important;
        background: var(--radar-card-bg);
        font-size: 0.72rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .radar-detail-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
        padding-bottom: 0.1rem;
    }

    .radar-detail-block {
        background: var(--radar-card-bg);
        border: 1px solid var(--radar-soft-border);
        border-radius: 12px;
        padding: 1.05rem 1.15rem 1.15rem;
        min-height: 100%;
    }

    .radar-detail-label {
        font-size: 0.74rem;
        font-weight: 900;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        color: var(--radar-secondary-text);
        margin-bottom: 0.65rem;
    }

    .radar-detail-label.important {
        color: var(--radar-secondary-text);
    }

    .radar-detail-copy {
        font-size: 0.96rem;
        line-height: 1.68;
        color: var(--radar-primary-text);
    }

    .radar-source-link a {
        color: var(--radar-primary-text) !important;
        text-decoration: none !important;
        text-underline-offset: 0.2rem;
    }

    .radar-source-link a:hover,
    .radar-source-button:hover {
        color: var(--radar-primary-text) !important;
        text-decoration: underline !important;
    }

    [data-testid="stMain"] div[data-testid="stExpander"] details {
        background: var(--radar-card-bg) !important;
        border: 1px solid var(--radar-border) !important;
        border-radius: 14px !important;
        box-shadow: var(--radar-card-shadow) !important;
        margin-bottom: 0.72rem !important;
        overflow: hidden;
    }

    [data-testid="stMain"] div[data-testid="stExpander"] details[open] {
        border-color: var(--radar-border) !important;
        box-shadow: var(--radar-card-shadow-open) !important;
    }

    [data-testid="stMain"] div[data-testid="stExpander"] summary {
        padding-top: 0.85rem !important;
        padding-bottom: 0.85rem !important;
    }

    .block-container div[data-testid="stExpander"] details[open] > summary {
        display: flex !important;
        align-items: center !important;
        justify-content: flex-end !important;
        min-height: 34px !important;
        padding: 0.25rem 0.85rem !important;
        border-bottom: 1px solid var(--radar-soft-border);
        background: var(--radar-card-bg);
    }

    .block-container div[data-testid="stExpander"] details[open] > summary p {
        display: none !important;
    }

    .block-container div[data-testid="stExpander"] details[open] > summary > span {
        display: none !important;
    }

    .block-container div[data-testid="stExpander"] details[open] > summary::after {
        content: "Daralt";
        color: var(--radar-secondary-text);
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        line-height: 1;
        text-transform: uppercase;
    }

    [data-testid="stMain"] h3 {
        margin-top: 1.05rem !important;
        margin-bottom: 0.15rem !important;
    }

    [data-testid="stMain"] h3 + div,
    [data-testid="stMain"] .stCaptionContainer {
        margin-bottom: 0.45rem !important;
    }

    @media (max-width: 900px) {
        .radar-kpi-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .radar-kpi-card:nth-child(2) {
            border-right: 0;
        }
        .radar-kpi-card {
            border-bottom: 1px solid var(--ak-border);
        }
        .radar-detail-head,
        .radar-detail-grid,
        .radar-watchlist-item {
            grid-template-columns: 1fr;
        }
        .radar-detail-side {
            text-align: left;
            justify-items: start;
            white-space: normal;
        }
        .block-container {
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


SECTION_STRATEGIC = "Stratejik / BD Gelişmeleri"
SECTION_CLUSTER = "Patern / Küme Gelişmeler"
SECTION_AWARENESS = "Yönetici Bilgilendirme / İtibar Sinyalleri"

MONTH_LOOKUP = {
    "ocak": 1,
    "şubat": 2,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "agustos": 8,
    "eylül": 9,
    "eylul": 9,
    "ekim": 10,
    "kasım": 11,
    "kasim": 11,
    "aralık": 12,
    "aralik": 12,
}

MONTHS_TR = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}

ACTION_LABELS = {
    "BD Konuşma Notlarına Ekle": "BD konuşma notu",
    "Yönetici Bilgilendirme Notuna Ekle": "Bilgilendirme",
    "Uyarlama Fırsatını Değerlendir": "Uyarlama fırsatı",
    "İş Birliği Fırsatını İncele": "İş birliği",
    "Yönetime Eskale Et": "Eskale",
    "Önceliklendirme": "İzle",
    "İzle": "İzle",
}


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    text = clean_display_text(value)
    if not text:
        return pd.NaT
    if text[:10].count("-") == 2:
        parsed_iso = pd.to_datetime(text, errors="coerce")
        if pd.notna(parsed_iso):
            return parsed_iso
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.notna(parsed):
        return parsed
    parts = text.replace(",", " ").split()
    if len(parts) >= 3 and parts[0].isdigit():
        month = MONTH_LOOKUP.get(parts[1].casefold())
        year = int(parts[2]) if parts[2].isdigit() else None
        if month and year:
            return pd.Timestamp(datetime(year, month, int(parts[0])))
    return pd.NaT


def format_date(value: object) -> str:
    parsed = parse_date(value)
    if pd.isna(parsed):
        return clean_display_text(value) or "Tarih yok"
    return f"{parsed.day} {MONTHS_TR[parsed.month]} {parsed.year}"


def format_header_update(value: object) -> str:
    parsed = pd.to_datetime(clean_display_text(value), errors="coerce")
    if pd.isna(parsed):
        parsed = parse_date(value)
    if pd.isna(parsed):
        return "Canlı veri"
    if getattr(parsed, "tzinfo", None) is not None:
        parsed = parsed.tz_convert("Europe/Istanbul")
    return f"{parsed.day:02d}.{parsed.month:02d}.{parsed.year} {parsed.hour:02d}:{parsed.minute:02d}"


def format_week_label(value: object, max_date: pd.Timestamp) -> str:
    parsed = parse_date(value)
    if pd.isna(parsed):
        return "Tarih net değil"
    current_week_start = max_date - pd.Timedelta(days=int(max_date.weekday()))
    previous_week_start = current_week_start - pd.Timedelta(days=7)
    week_start = parsed - pd.Timedelta(days=int(parsed.weekday()))
    if week_start == current_week_start:
        return f"Bu hafta · {format_date(max_date)}"
    if week_start == previous_week_start:
        return "Geçen hafta"
    return f"{format_date(week_start)} haftası"


def row_lookup(df: pd.DataFrame, key: str) -> dict[str, pd.Series]:
    if df.empty or key not in df.columns:
        return {}
    return {str(row[key]): row for _, row in df.drop_duplicates(key, keep="last").iterrows() if str(row[key]).strip()}


def lookup_value(row: pd.Series, lookups: list[dict[str, pd.Series]], keys: list[str], column: str) -> str:
    for key in keys:
        key_value = clean_display_text(row.get(key))
        if not key_value:
            continue
        for lookup in lookups:
            found = lookup.get(key_value)
            if found is not None:
                value = clean_display_text(found.get(column))
                if value:
                    return value
    return clean_display_text(row.get(column))


def display_date(row: pd.Series) -> tuple[str, pd.Timestamp]:
    for column in ["published_at", "date", "item_date", "recency_basis_date"]:
        value = lookup_value(row, [item_by_recent_id], ["recent_item_id"], column)
        parsed = parse_date(value)
        if pd.notna(parsed):
            return format_date(value), parsed
    return "Tarih yok", pd.Timestamp("1970-01-01")


def source_url_for(row: pd.Series) -> str:
    for value in [row.get("item_url", ""), row.get("source_url", "")]:
        text = clean_display_text(value)
        if text.startswith("http"):
            return text
    for url in parse_json_list(row.get("source_urls", "")):
        text = clean_display_text(url)
        if text.startswith("http"):
            return text
    return ""


def source_domain(url: str) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.replace("www.", "") or url


def action_label(value: object) -> str:
    text = clean_text(value, "")
    return ACTION_LABELS.get(text, text or "İzle")


def boolish(value: object) -> bool:
    return clean_display_text(value).casefold() in {"true", "1", "yes", "evet"}


def impact_rank(value: object) -> int:
    text = clean_text(value, "").casefold()
    if text in {"yüksek", "high"}:
        return 3
    if text in {"orta", "medium"}:
        return 2
    return 1


def esc(value: object) -> str:
    return html.escape(clean_text(value, ""))


def compact_text(value: object, max_chars: int = 150) -> str:
    text = clean_text(value, "")
    if len(text) <= max_chars:
        return text
    trimmed = text[: max_chars - 3].rstrip()
    last_space = trimmed.rfind(" ")
    if last_space > max_chars * 0.55:
        trimmed = trimmed[:last_space].rstrip()
    return f"{trimmed}..."


def display_title_for(title: str, institution: str) -> str:
    clean_title = clean_text(title, "")
    clean_institution = clean_text(institution, "")
    if clean_institution and clean_title.casefold().startswith(clean_institution.casefold()):
        stripped = clean_title[len(clean_institution):].lstrip(" ,:-–—|")
        if not stripped or stripped.startswith("'"):
            return clean_title
        first = stripped[0]
        if first.islower():
            return clean_title
        return stripped
    return clean_title


def section_breakdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "Bu hafta yayınlanan gelişme yok"
    strategic = int(df["section"].eq(SECTION_STRATEGIC).sum())
    cluster = int(df["section"].eq(SECTION_CLUSTER).sum())
    awareness = int(df["section"].eq(SECTION_AWARENESS).sum())
    return f"{strategic} stratejik · {cluster} patern · {awareness} yönetici notu"


def week_delta_text(current_count: int, previous_count: int) -> str:
    if previous_count <= 0:
        return "Önceki hafta referansı yok"
    delta = current_count - previous_count
    if delta == 0:
        return "Geçen haftaya göre yatay"
    prefix = "+" if delta > 0 else "-"
    return f"{prefix}{abs(delta)} geçen haftaya göre"


def render_kpi_cards(df: pd.DataFrame, global_count: int) -> None:
    max_date = df["display_date_dt"].max()
    current_week_start = max_date - pd.Timedelta(days=int(max_date.weekday()))
    current = df[(df["display_date_dt"] >= current_week_start) & (df["display_date_dt"] < current_week_start + pd.Timedelta(days=7))]
    top_banks_this_week = current["institution_name"].value_counts().head(3)
    top_banks_all_time = df["institution_name"].value_counts().head(3)
    top_bank_week_html = "".join(
        f'<div class="radar-kpi-rank"><span>{idx:02d}</span><span>{esc(bank).upper()}</span><span>{count:02d}</span></div>'
        for idx, (bank, count) in enumerate(top_banks_this_week.items(), start=1)
    ) or (
        '<div class="radar-kpi-rank"><span>--</span><span>VERİ YOK</span><span>00</span></div>'
    )
    top_bank_all_time_html = "".join(
        f'<div class="radar-kpi-rank"><span>{idx:02d}</span><span>{esc(bank).upper()}</span><span>{count:02d}</span></div>'
        for idx, (bank, count) in enumerate(top_banks_all_time.items(), start=1)
    ) or (
        '<div class="radar-kpi-rank"><span>--</span><span>VERİ YOK</span><span>00</span></div>'
    )

    st.markdown(
        f"""
        <div class="radar-kpi-grid">
          <div class="radar-kpi-card">
            <div class="radar-kpi-label">Bu hafta toplam</div>
            <div class="radar-kpi-value">{len(current):02d}</div>
            <div class="radar-kpi-range">Bu hafta</div>
          </div>
          <div class="radar-kpi-card">
            <div class="radar-kpi-label">Global Gelişmeler</div>
            <div class="radar-kpi-value">{global_count:02d}</div>
            <div class="radar-kpi-range">Son 30 gün</div>
          </div>
          <div class="radar-kpi-card">
            <div class="radar-kpi-label">İlk 3 kurum</div>
            {top_bank_week_html}
            <div class="radar-kpi-range">Bu hafta</div>
          </div>
          <div class="radar-kpi-card">
            <div class="radar-kpi-label">İlk 3 kurum</div>
            {top_bank_all_time_html}
            <div class="radar-kpi-range">Tüm zamanlar</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_watchlist(df: pd.DataFrame) -> None:
    top = df.sort_values(["_impact_rank", "_importance_rank", "display_date_dt"], ascending=False).head(3)
    item_html = ""
    if top.empty:
        item_html = (
            '<div class="radar-watchlist-body">'
            "Bu filtrelerle yöneticinin hemen izlemesi gereken stratejik / BD gündemi yok; "
            "orta etkili kampanya ve iş birliği hareketleri izlenmeli."
            "</div>"
        )
    else:
        items: list[str] = []
        for _, row in top.iterrows():
            institution = clean_text(row.get("institution_name"))
            headline = display_title_for(clean_text(row.get("headline")), institution)
            summary = compact_text(clean_text(row.get("core_assessment")) or clean_text(row.get("summary")), 170)
            items.append(
                '<div class="radar-watchlist-item">'
                f'<div class="radar-watchlist-item-title">{esc(institution)} — {esc(headline)}</div>'
                f'<div class="radar-watchlist-item-copy">{esc(summary)}</div>'
                '</div>'
            )
        item_html = f'<div class="radar-watchlist-list">{"".join(items)}</div>'

    st.markdown(
        f"""
        <div class="radar-watchlist">
          <div class="radar-watchlist-kicker">Stratejik / BD gündemi</div>
          <div class="radar-watchlist-title">Haftanın öne çıkan gelişmeleri</div>
          {item_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_radar_section(title: str, subtitle: str, df: pd.DataFrame, max_date: pd.Timestamp) -> None:
    st.subheader(title)
    st.caption(f"{subtitle} · {len(df)} gelişme")
    if df.empty:
        st.info("Bu bölümde seçili filtrelerle eşleşen yayınlanmış gelişme yok.")
        return

    grouped = df.sort_values("display_date_dt", ascending=False).copy()
    grouped["week_label"] = grouped["display_date_dt"].apply(lambda value: format_week_label(value, max_date))

    for week_label, week_df in grouped.groupby("week_label", sort=False):
        st.markdown(f"**{week_label}**")
        for _, row in week_df.iterrows():
            title_text = clean_text(row.get("headline")) or clean_text(row.get("item_title"))
            institution = clean_text(row.get("institution_name"))
            display_title = display_title_for(title_text, institution)
            theme = clean_text(row.get("strategic_theme"))
            date_label = clean_text(row.get("display_date_label")) or format_date(row.get("date"))
            summary = clean_text(row.get("summary"))
            why = build_executive_why_it_matters(row.get("core_assessment"), row.get("strategic_relevance"))
            url = source_url_for(row)
            domain = source_domain(url)
            section = clean_display_text(row.get("section"))
            source_label = domain or clean_text(row.get("source_id")) or "Kaynak yok"
            related_html = ""
            if section == SECTION_CLUSTER:
                related_ids = parse_json_list(row.get("related_item_ids", ""))
                if related_ids:
                    related_html = (
                        '<div class="radar-detail-label" style="margin-top: 1rem;">Bağlı gelişmeler</div>'
                        f'<div class="radar-detail-copy">{esc(", ".join(related_ids))}</div>'
                    )
            label = f"{display_title} — {institution} · {theme or 'Tema yok'} · {date_label}"
            with st.expander(label):
                st.markdown(
                    f"""
                    <div class="radar-detail-head">
                      <div>
                        <div class="radar-detail-meta">
                          <span class="radar-bank-chip">{esc(institution)}</span>
                          <span>{esc(theme or "Tema yok")}</span>
                        </div>
                        <div class="radar-detail-title">{esc(display_title)}</div>
                      </div>
                      <div class="radar-detail-side">
                        <span>{esc(date_label)}</span>
                        <span>{esc(source_label)}</span>
                        {f'<a class="radar-source-button" href="{esc(url)}" target="_blank">Kaynağı aç</a>' if url else ''}
                      </div>
                    </div>
                    <div class="radar-detail-summary">{esc(summary or "-")}</div>
                    <div class="radar-detail-grid">
                      <div class="radar-detail-block">
                        <div class="radar-detail-label">Ne oldu?</div>
                        <div class="radar-detail-copy">{esc(summary or "-")}</div>
                      </div>
                      <div class="radar-detail-block">
                        <div class="radar-detail-label important">Neden önemli? <span style="opacity: 0.62; color: inherit;">— Akbank için</span></div>
                        <div class="radar-detail-copy">{esc(why or "-")}</div>
                        {related_html}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


weekly_all = read_csv_safe("weekly_developments.csv", WEEKLY_COLUMNS)
weekly = real_published_weekly(weekly_all)
archive = read_csv_safe("recent_item_archive.csv", ARCHIVE_COLUMNS)
review_queue = read_csv_safe("recent_item_review_queue.csv", QUEUE_COLUMNS)
items = read_csv_safe("recent_items.csv", RECENT_ITEM_COLUMNS)
summaries = read_csv_safe("recent_item_summaries.csv", SUMMARY_COLUMNS)
clusters = read_csv_safe("development_clusters.csv", CLUSTER_COLUMNS)

item_by_recent_id = row_lookup(items, "recent_item_id")

if weekly.empty:
    render_page_header(
        "Yönetici Özeti",
        "AI'ın yakaladığı İş Geliştirme ekibinin onayından geçmiş rekabetteki gelişmeler ve KOBİ departmanlarının gündemi",
        updated_at="Canlı veri",
    )
    st.info("Henüz radara yayınlanmış gelişme yok. Analist Onay Kuyruğu’ndan birkaç gelişmeyi onaylayıp yayınlayın.")
    st.stop()
    raise SystemExit

latest_published_at = ""
if "published_at" in weekly.columns:
    published_dates = pd.to_datetime(weekly["published_at"], errors="coerce")
    if published_dates.notna().any():
        latest_published_at = published_dates.max()

render_page_header(
    "Yönetici Özeti",
    "AI'ın yakaladığı İş Geliştirme ekibinin onayından geçmiş rekabetteki gelişmeler ve KOBİ departmanlarının gündemi",
    updated_at=format_header_update(latest_published_at),
)

weekly["section"] = weekly["section"].fillna("").astype(str)
weekly["display_date_label"] = weekly.apply(lambda row: display_date(row)[0], axis=1)
weekly["display_date_dt"] = weekly.apply(lambda row: display_date(row)[1], axis=1)
weekly["institution_group"] = weekly["institution_name"].apply(institution_group)
weekly["_impact_rank"] = weekly["impact_on_us"].apply(impact_rank)
weekly["_importance_rank"] = weekly["importance_level"].apply(impact_rank)
weekly = add_sort_columns(weekly, "display_date_dt")

archive_count = len(archive)
rejected_count = int(review_queue["review_status"].astype(str).eq("Reddedildi").sum()) if not review_queue.empty else 0
archived_total = archive_count + rejected_count

current_max_date = weekly["display_date_dt"].max()
current_week_start = current_max_date - pd.Timedelta(days=int(current_max_date.weekday()))
global_count = int(
    summaries["institution_name"].astype(str).str.casefold().isin(["visa", "mastercard"]).sum()
) if not summaries.empty and "institution_name" in summaries.columns else 0

render_kpi_cards(weekly, global_count)

with st.sidebar:
    st.header("Gelişme Filtreleri")
    institution_groups = sorted(weekly["institution_group"].dropna().astype(str).unique())
    institutions = sorted(weekly["institution_name"].dropna().astype(str).unique())
    sections = sorted(weekly["section"].dropna().astype(str).unique())
    themes = sorted(weekly["strategic_theme"].dropna().astype(str).unique())
    product_areas = sorted(weekly["product_area"].dropna().astype(str).unique())
    actions = sorted(weekly["recommended_action"].dropna().astype(str).unique())
    min_date = weekly["display_date_dt"].min().date()
    max_date = weekly["display_date_dt"].max().date()

    with st.expander("Filtreleri aç", expanded=False):
        selected_institution_groups = st.multiselect("Kurum grubu", institution_groups, default=institution_groups)
        selected_institutions = st.multiselect("Kurum", institutions, default=institutions)
        selected_sections = st.multiselect("Bölüm", sections, default=sections)
        selected_themes = st.multiselect("Tema", themes, default=themes)
        selected_product_areas = st.multiselect("Ürün alanı", product_areas, default=product_areas)
        selected_actions = st.multiselect("Aksiyon", actions, default=actions)
        selected_range = st.date_input("Tarih aralığı", value=(min_date, max_date), min_value=min_date, max_value=max_date)

if isinstance(selected_range, tuple) and len(selected_range) == 2:
    start_date, end_date = selected_range
else:
    start_date, end_date = min_date, max_date

filtered = weekly[
    weekly["institution_group"].isin(selected_institution_groups)
    & weekly["institution_name"].isin(selected_institutions)
    & weekly["section"].isin(selected_sections)
    & weekly["strategic_theme"].isin(selected_themes)
    & weekly["product_area"].isin(selected_product_areas)
    & weekly["recommended_action"].isin(selected_actions)
    & (weekly["display_date_dt"].dt.date >= start_date)
    & (weekly["display_date_dt"].dt.date <= end_date)
].copy()

if filtered.empty:
    st.warning("Seçili filtrelerle eşleşen radar gelişmesi yok.")
    st.stop()
    raise SystemExit

tokens = [f"{len(filtered)} sonuç"]
if len(selected_institutions) != len(institutions):
    tokens.extend(selected_institutions)
if len(selected_institution_groups) != len(institution_groups):
    tokens.extend(selected_institution_groups)
if len(selected_sections) != len(sections):
    tokens.extend(selected_sections)
if start_date != min_date or end_date != max_date:
    tokens.append(f"{format_date(start_date)} - {format_date(end_date)}")
if len(tokens) > 1:
    st.caption(" · ".join(tokens))

render_watchlist(filtered[filtered["section"].eq(SECTION_STRATEGIC)].copy())

st.divider()
render_radar_section(
    "Stratejik / BD Gündemi",
    "Yönetimin ve BD ekiplerinin aksiyon veya yakın takip gerektiren maddeleri",
    filtered[filtered["section"].eq(SECTION_STRATEGIC)].copy(),
    current_max_date,
)

render_radar_section(
    "Patern & Küme Sinyalleri",
    "Tekil haberlerden ziyade birden fazla gelişmeyi bağlayan rekabet sinyalleri",
    filtered[filtered["section"].eq(SECTION_CLUSTER)].copy(),
    current_max_date,
)

render_radar_section(
    "KOBİ Departmanlarının İmaj Çalışmaları",
    "Bankaların tüzel çalışmalarıyla aldığı ödüller",
    filtered[filtered["section"].eq(SECTION_AWARENESS)].copy(),
    current_max_date,
)
