from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.ui_theme import apply_akbank_theme, render_page_header


st.set_page_config(page_title="Ücret Komisyon Matrisi", layout="wide")
apply_akbank_theme()


DATA_PATH = Path("data/pricing_matrix.csv")
LOCAL_TIER_ORDER = ["Tier 1", "Tier 2"]
GLOBAL_TIER_ORDER = ["Global Tier 1"]
LOCAL_BANK_ORDER = [
    "Akbank",
    "Garanti BBVA",
    "İş Bankası",
    "Yapı Kredi",
    "DenizBank",
    "Enpara",
    "QNB Finansbank",
    "Odeabank",
    "Alternatif Bank",
]
GLOBAL_BANK_ORDER = [
    "HSBC UK",
    "Santander UK",
    "JPMorgan Chase",
    "DBS Singapore",
]
BANK_ORDER_BY_SCOPE = {
    "Türkiye": LOCAL_BANK_ORDER,
    "Global": GLOBAL_BANK_ORDER,
}
TIER_ORDER_BY_SCOPE = {
    "Türkiye": LOCAL_TIER_ORDER,
    "Global": GLOBAL_TIER_ORDER,
}
BANK_ORDER = [*LOCAL_BANK_ORDER, *GLOBAL_BANK_ORDER]
MATRIX_BUCKETS = ["Kartlar", "POS", "Yurt içi transfer", "Yurt dışı / SWIFT", "Paket / Kredi"]
MATRIX_PREVIEW_LIMIT = 3


def esc(value: object) -> str:
    return html.escape(str(value or "").strip())


def read_pricing() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(DATA_PATH, dtype=str).fillna("")
    if "market_scope" not in df.columns:
        df["market_scope"] = df["institution_name"].apply(
            lambda value: "Global" if value in GLOBAL_BANK_ORDER else "Türkiye"
        )
    df.loc[df["market_scope"].str.strip().eq(""), "market_scope"] = df["institution_name"].apply(
        lambda value: "Global" if value in GLOBAL_BANK_ORDER else "Türkiye"
    )
    return df[df["institution_name"].isin(BANK_ORDER)].copy()


def tl_amount(value: object) -> float | None:
    text = str(value or "")
    if "%" in text or "Ücretsiz" in text or "ücretsiz" in text:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(".", ""))
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def zero_or_free(value: object) -> bool:
    text = str(value or "").casefold()
    return "ücretsiz" in text or "0 tl" in text or text.strip() == "0"


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    return pd.to_datetime(str(value or "").strip(), errors="coerce")


def format_short_date(value: object) -> str:
    parsed = parse_date(value)
    if pd.isna(parsed):
        return "Tarih yok"
    return f"{parsed.day:02d}.{parsed.month:02d}"


def first_percentage(value: object) -> float | None:
    match = re.search(r"%\s*(\d+(?:[.,]\d+)?)", str(value or ""))
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def best_new_acquiring_rate(df: pd.DataFrame) -> str:
    candidates = []
    for _, row in df.iterrows():
        if matrix_bucket(row) != "POS":
            continue
        text = " ".join(
            str(row.get(column, ""))
            for column in ["fee_family", "fee_item", "fee_basis", "product_or_channel"]
        ).casefold()
        scope = str(row.get("market_scope", "Türkiye")).strip()
        has_card_signal = any(
            token in text
            for token in ["kredi kart", "credit card", "card-present", "card payment", "merchant", "acquiring"]
        )
        if scope == "Türkiye" and ("yeni kazanım" not in text or "kredi kart" not in text or "peşin" not in text):
            continue
        if not has_card_signal:
            continue
        if scope == "Türkiye" and "sektör" in text:
            continue
        rate = first_percentage(row.get("fee_value"))
        if rate is not None:
            candidates.append(rate)
    if not candidates:
        return "Veri yok"
    best = min(candidates)
    return f"%{best:.2f}".replace(".", ",")


def matrix_bucket(row: pd.Series) -> str:
    fee_family = str(row.get("fee_family", "")).casefold()
    if any(token in fee_family for token in ["pos", "üye işyeri", "merchant", "acquiring"]):
        return "POS"
    if any(token in fee_family for token in ["kart", "card"]):
        return "Kartlar"
    if any(token in fee_family for token in ["kredi", "paket", "lending", "overdraft", "account", "package"]):
        return "Paket / Kredi"
    if any(token in fee_family for token in ["swift", "yurt dış", "yabancı para", "uluslararası", "döviz", "international", "wire", "cross-border", "fx", "telegraphic"]):
        return "Yurt dışı / SWIFT"
    if any(token in fee_family for token in ["havale", "eft", "fast", "ach", "paynow", "faster payment", "domestic transfer"]):
        return "Yurt içi transfer"
    text = " ".join(
        str(row.get(column, ""))
        for column in ["fee_family", "fee_item", "product_or_channel", "fee_basis", "notes"]
    ).casefold()
    if any(token in text for token in ["pos", "üye işyeri", "merchant", "acquiring", "card-present", "card payment"]):
        return "POS"
    if any(token in text for token in ["paket", "kredi tahsis", "taksitli ticari kredi", "faizsiz", "business account", "checking", "overdraft", "lending", "package"]):
        return "Paket / Kredi"
    if any(token in text for token in ["swift", "yurt dış", "uluslararası", "döviz", "yabancı para", "international", "wire", "cross-border", "fx", "telegraphic"]):
        return "Yurt dışı / SWIFT"
    if any(token in text for token in ["havale", "transfer", "eft", "ach", "paynow", "faster payment", "domestic"]):
        return "Yurt içi transfer"
    if "maaş" in text:
        return "Paket / Kredi"
    return "Kartlar"


def compact_fee_label(row: pd.Series) -> str:
    item = str(row.get("fee_item", "")).strip()
    value = str(row.get("fee_value", "")).strip()
    if not item and not value:
        return ""
    parts = [part for part in [item, value] if part]
    return " — ".join(parts)


def render_matrix_item(row: pd.Series, muted: bool = False) -> str:
    label = esc(compact_fee_label(row))
    source_url = str(row.get("source_url", "")).strip()
    classes = "pricing-matrix-item"
    if muted:
        classes += " pricing-matrix-item-muted"
    if source_url:
        return (
            f'<a class="{classes} pricing-matrix-link" '
            f'href="{esc(source_url)}" target="_blank" rel="noopener noreferrer">'
            f"<span>{label}</span>"
            '<span class="pricing-matrix-link-icon">↗</span>'
            "</a>"
        )
    return f'<div class="{classes}">{label}</div>'


def matrix_preview_limit(bucket: str) -> int:
    if bucket == "Yurt içi transfer":
        return 6
    if bucket == "Yurt dışı / SWIFT":
        return 6
    if bucket == "Paket / Kredi":
        return 6
    return MATRIX_PREVIEW_LIMIT


def render_matrix_items(rows: list[pd.Series], bucket: str) -> str:
    preview_limit = matrix_preview_limit(bucket)
    visible = rows[:preview_limit]
    hidden = rows[preview_limit:]
    items = "".join(render_matrix_item(row) for row in visible)
    if hidden:
        hidden_items = "".join(render_matrix_item(row, muted=True) for row in hidden)
        items += (
            '<details class="pricing-matrix-more">'
            f'<summary>+{len(hidden)} kalem</summary>'
            f'<div class="pricing-matrix-hidden">{hidden_items}</div>'
            '</details>'
        )
    return items


def matrix_item_sort_key(row: pd.Series, bucket: str, fallback_order: int) -> tuple[int, int]:
    text = " ".join(
        str(row.get(column, ""))
        for column in ["fee_family", "fee_item", "product_or_channel", "fee_basis"]
    ).casefold()
    if bucket == "Kartlar":
        if "banka kart" in text or "paracard" in text:
            return (2, fallback_order)
        if "aidatsız" in text or "free" in text or "0 tl" in text:
            return (1, fallback_order)
        if "yıllık ücret" in text:
            return (0, fallback_order)
        if "nakit avans" in text:
            return (3, fallback_order)
        return (4, fallback_order)
    if bucket == "Yurt içi transfer":
        if any(token in text for token in ["pahalı kanal", "atm", "şube", "branch", "müşteri iletişim", "çözüm merkezi"]):
            return (2, fallback_order)
        if any(token in text for token in ["havale", "paynow", "faster payment", "ach"]):
            return (1, fallback_order)
        return (0, fallback_order)
    if bucket == "Yurt dışı / SWIFT":
        if "gelen" in text:
            return (9, fallback_order)
        if any(token in text for token in ["şube", "branch", "pahalı kanal"]):
            return (8, fallback_order)
        if "visa" in text:
            return (0, fallback_order)
        if "yurt dışı fast" in text or "fast uluslararası" in text:
            return (1, fallback_order)
        if (
            "0-10.000" in text
            or "0-10 bin" in text
            or "0-12.000" in text
            or "0-12 bin" in text
            or "15 bin tl ve alt" in text
            or "15.000 tl ve alt" in text
            or "30 bin tl alt" in text
        ):
            return (2, fallback_order)
        if "12.000,01-40.000" in text or "12-40 bin" in text:
            return (3, fallback_order)
        if "40.000,01-80.000" in text or "40-80 bin" in text:
            return (4, fallback_order)
        if (
            "80.000,01" in text
            or "80 bin" in text
            or "10.000 tl üzeri" in text
            or "10 bin+" in text
            or "15 bin tl+" in text
            or "15.000,01" in text
            or "30 bin tl üst" in text
        ):
            return (5, fallback_order)
        if "same-day" in text or "aynı gün" in text:
            return (2, fallback_order)
        if "1 gün" in text:
            return (3, fallback_order)
        if "ileri gün" in text:
            return (4, fallback_order)
        return (6, fallback_order)
    if bucket == "Paket / Kredi":
        if any(token in text for token in ["hoş geldin", "yeni müşteri", "faizsiz", "account", "checking"]):
            return (0, fallback_order)
        if "nakit akışınla kazan" in text:
            return (1, fallback_order)
        if (
            "dış ticaret paketi" in text
            or "ithalat paket" in text
            or "ihracat paket" in text
            or "karma dış ticaret" in text
            or "kota" in text
            or "swift paketi" in text
            or "swift paketleri" in text
        ):
            return (2, fallback_order)
        if "genç kobi" in text or "genciz kobi" in text or "kadın kobi" in text or "kadın girişimci" in text:
            return (3, fallback_order)
        if "çek" in text or "senet" in text:
            return (4, fallback_order)
        if "kgf" in text or "kobi ihtiyaç" in text or "anında ticari" in text or "ticari kredili" in text:
            return (5, fallback_order)
        if "pos'una kredi" in text or "posuna kredi" in text:
            return (6, fallback_order)
        return (7, fallback_order)
    if bucket != "POS":
        return (fallback_order, 0)
    if any(token in text for token in ["kampanya", "hoş geldin", "yeni kazanım", "pos'um cepte"]):
        return (0, fallback_order)
    if any(token in text for token in ["peşin", "azami", "standart"]):
        return (1, fallback_order)
    if "taksit" in text:
        return (2, fallback_order)
    return (3, fallback_order)


def sort_matrix_bucket(bucket_df: pd.DataFrame, bucket: str) -> pd.DataFrame:
    ordered = bucket_df.copy()
    ordered["_matrix_order"] = [
        matrix_item_sort_key(row, bucket, index)
        for index, (_, row) in enumerate(ordered.iterrows())
    ]
    return ordered.sort_values("_matrix_order").drop(columns=["_matrix_order"])


def sync_multiselect_options(key: str, options: list[str]) -> None:
    options_key = f"{key}__options"
    previous_options = st.session_state.get(options_key)
    selected = st.session_state.get(key)
    if not isinstance(selected, list):
        st.session_state[options_key] = options
        return
    selected = [option for option in selected if option in options]
    if isinstance(previous_options, list):
        newly_added = [option for option in options if option not in previous_options]
        selected.extend(option for option in newly_added if option not in selected)
    st.session_state[key] = selected
    st.session_state[options_key] = options


def render_scope_switcher() -> str:
    if st.session_state.get("pricing_scope") not in ["Türkiye", "Global"]:
        st.session_state["pricing_scope"] = "Türkiye"

    st.markdown('<div class="pricing-scope-caption">Benchmark kapsamı</div>', unsafe_allow_html=True)
    tr_col, global_col, spacer = st.columns([1.15, 1.15, 7.7])
    with tr_col:
        if st.button(
            "Türkiye",
            key="pricing_scope_turkiye",
            type="primary" if st.session_state["pricing_scope"] == "Türkiye" else "secondary",
            use_container_width=True,
        ):
            st.session_state["pricing_scope"] = "Türkiye"
            st.rerun()
    with global_col:
        if st.button(
            "Global",
            key="pricing_scope_global",
            type="primary" if st.session_state["pricing_scope"] == "Global" else "secondary",
            use_container_width=True,
        ):
            st.session_state["pricing_scope"] = "Global"
            st.rerun()
    with spacer:
        st.empty()
    return st.session_state["pricing_scope"]


def inject_css(scope: str) -> None:
    global_css = ""
    if scope == "Global":
        global_css = """
        html, body, .stApp, [data-testid="stAppViewContainer"] {
            background: var(--ak-global-bg) !important;
        }

        [data-testid="stHeader"] {
            background: color-mix(in srgb, var(--ak-global-bg) 94%, white) !important;
        }

        .pricing-kpi,
        .pricing-panel,
        .pricing-bank-card,
        .pricing-tier-panel {
            border-color: var(--ak-global-border) !important;
        }

        .pricing-pill {
            background: var(--ak-global-chip) !important;
            border-color: var(--ak-global-border) !important;
            color: var(--ak-global-text) !important;
        }

        .pricing-matrix-header {
            background: var(--ak-global-soft) !important;
        }
        """
    st.markdown(
        """
        <style>
        """
        + global_css
        + """
        .pricing-kpi-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 1rem;
            margin: 0.2rem 0 1.35rem;
        }

        .pricing-scope-caption {
            color: var(--ak-muted);
            font-size: 0.68rem;
            font-weight: 850;
            letter-spacing: 0.12em;
            line-height: 1;
            margin: 0.25rem 0 0.45rem;
            text-transform: uppercase;
        }

        .pricing-kpi,
        .pricing-panel,
        .pricing-bank-card {
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-radius: 14px;
            box-shadow: var(--ak-shadow-soft);
        }

        .pricing-kpi {
            min-height: 112px;
            padding: 1.1rem 1.2rem;
        }

        .pricing-label,
        .pricing-card-label {
            color: var(--ak-muted);
            font-size: 0.7rem;
            font-weight: 850;
            letter-spacing: 0.11em;
            text-transform: uppercase;
        }

        .pricing-value {
            color: var(--ak-text);
            font-size: clamp(1.9rem, 2.4vw, 2.35rem);
            font-weight: 900;
            line-height: 1;
            margin-top: 0.55rem;
            white-space: nowrap;
        }

        .pricing-note {
            color: var(--ak-secondary);
            font-size: 0.82rem;
            line-height: 1.45;
            margin-top: 0.55rem;
        }

        .pricing-bank-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            margin: 0.8rem 0 1.45rem;
        }

        .pricing-bank-card {
            padding: 1.05rem 1.1rem;
        }

        .pricing-bank-head {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: start;
            margin-bottom: 0.9rem;
        }

        .pricing-bank-name {
            color: var(--ak-text);
            font-size: 1rem;
            font-weight: 850;
        }

        .pricing-pill {
            display: inline-flex;
            align-items: center;
            border: 1px solid var(--ak-border);
            border-radius: 999px;
            background: var(--ak-soft);
            color: var(--ak-text);
            font-size: 0.72rem;
            font-weight: 800;
            padding: 0.18rem 0.52rem;
            white-space: nowrap;
        }

        .pricing-bank-list {
            display: grid;
            gap: 0.72rem;
        }

        .pricing-bank-item {
            border-top: 1px solid var(--ak-border);
            padding-top: 0.72rem;
        }

        .pricing-item-title {
            color: var(--ak-text);
            font-size: 0.9rem;
            font-weight: 850;
            line-height: 1.35;
        }

        .pricing-item-meta {
            color: var(--ak-secondary);
            font-size: 0.82rem;
            line-height: 1.45;
            margin-top: 0.28rem;
        }

        .pricing-panel {
            padding: 1.2rem 1.3rem;
            margin-bottom: 1.15rem;
        }

        .pricing-tier-panel {
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-radius: 14px;
            box-shadow: var(--ak-shadow-soft);
            margin: 0 0 1.2rem;
            overflow-x: auto;
        }

        .pricing-tier-head {
            display: flex;
            align-items: end;
            justify-content: space-between;
            gap: 1rem;
            padding: 1rem 1.15rem;
            border-bottom: 1px solid var(--ak-border);
        }

        .pricing-tier-title {
            color: var(--ak-text);
            font-size: 1.05rem;
            font-weight: 900;
        }

        .pricing-tier-copy {
            color: var(--ak-secondary);
            font-size: 0.82rem;
            margin-top: 0.18rem;
        }

        .pricing-matrix {
            display: grid;
            grid-template-columns: minmax(150px, 0.75fr) repeat(var(--pricing-column-count, 5), minmax(220px, 1fr));
            min-width: 1260px;
        }

        .pricing-matrix-cell {
            min-height: 68px;
            padding: 0.72rem 0.84rem;
            border-right: 1px solid var(--ak-border);
            border-bottom: 1px solid var(--ak-border);
        }

        .pricing-matrix-header {
            min-height: auto;
            background: var(--ak-soft);
            color: var(--ak-muted);
            font-size: 0.68rem;
            font-weight: 900;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }

        .pricing-matrix-bank {
            color: var(--ak-text);
            font-size: 0.93rem;
            font-weight: 900;
        }

        .pricing-matrix-tier {
            color: var(--ak-muted);
            font-size: 0.7rem;
            font-weight: 800;
            margin-top: 0.18rem;
        }

        .pricing-matrix-items {
            display: grid;
            gap: 0.3rem;
        }

        .pricing-matrix-item {
            color: var(--ak-text);
            font-size: 0.74rem;
            font-weight: 750;
            line-height: 1.22;
            border-bottom: 1px solid var(--ak-border);
            padding-bottom: 0.3rem;
        }

        .pricing-matrix-item:last-child {
            border-bottom: 0;
            padding-bottom: 0;
        }

        .pricing-matrix-link {
            display: flex;
            align-items: start;
            justify-content: space-between;
            gap: 0.45rem;
            text-decoration: none !important;
            transition: color 120ms ease;
        }

        .pricing-matrix-link:hover {
            color: var(--ak-red-dark);
            text-decoration: underline !important;
            text-underline-offset: 3px;
        }

        .pricing-matrix-link-icon {
            color: var(--ak-muted);
            flex: 0 0 auto;
            font-size: 0.66rem;
            line-height: 1;
            margin-top: 0.08rem;
        }

        .pricing-matrix-link:hover .pricing-matrix-link-icon {
            color: var(--ak-red-dark);
        }

        .pricing-matrix-item-muted {
            color: var(--ak-secondary);
        }

        .pricing-matrix-more {
            margin-top: 0.12rem;
        }

        .pricing-matrix-more summary {
            cursor: pointer;
            color: var(--ak-text);
            font-size: 0.68rem;
            font-weight: 900;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            list-style: none;
            display: inline-flex;
            align-items: center;
            border: 1px solid var(--ak-border);
            border-radius: 999px;
            background: var(--ak-soft);
            padding: 0.18rem 0.5rem;
        }

        .pricing-matrix-more summary::-webkit-details-marker {
            display: none;
        }

        .pricing-matrix-more[open] summary {
            margin-bottom: 0.36rem;
        }

        .pricing-matrix-hidden {
            display: grid;
            gap: 0.3rem;
        }

        .pricing-matrix-empty {
            color: var(--ak-muted);
            font-size: 0.78rem;
            font-weight: 750;
        }

        .pricing-section-label {
            color: var(--ak-text);
            font-size: 1.15rem;
            font-weight: 900;
            margin: 1.4rem 0 0.35rem;
        }

        .pricing-panel-title {
            color: var(--ak-text);
            font-size: 1.18rem;
            font-weight: 900;
            margin-bottom: 0.25rem;
        }

        .pricing-panel-copy {
            color: var(--ak-secondary);
            font-size: 0.92rem;
            line-height: 1.55;
            margin-bottom: 1rem;
        }

        .pricing-source a {
            color: var(--ak-text) !important;
            font-weight: 800;
            text-decoration: none !important;
        }

        .pricing-source a:hover {
            color: var(--ak-red-dark) !important;
            text-decoration: underline !important;
        }

        section[data-testid="stSidebar"] [data-baseweb="tag"] {
            background: var(--ak-soft) !important;
            border: 1px solid var(--ak-border) !important;
            color: var(--ak-text) !important;
        }

        section[data-testid="stSidebar"] [data-baseweb="tag"] span {
            color: var(--ak-text) !important;
        }

        section[data-testid="stSidebar"] [data-baseweb="tag"] svg {
            fill: var(--ak-muted) !important;
        }

        @media (max-width: 1200px) {
            .pricing-kpi-grid,
            .pricing-bank-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 700px) {
            .pricing-kpi-grid,
            .pricing-bank-grid {
                grid-template-columns: 1fr;
            }

            .pricing-matrix {
                grid-template-columns: minmax(132px, 0.8fr) repeat(var(--pricing-column-count, 5), minmax(190px, 1fr));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(df: pd.DataFrame) -> None:
    bank_count = df["institution_name"].nunique()
    row_count = len(df)
    free_count = int(df["fee_value"].apply(zero_or_free).sum())
    checked_dates = [parse_date(value) for value in df["update_date"] if str(value).strip()]
    latest_checked = max((value for value in checked_dates if not pd.isna(value)), default=pd.NaT)
    latest_label = format_short_date(latest_checked)
    cards = [
        ("Bakılan banka adedi", f"{bank_count:02d}", "Tier 1 + Tier 2"),
        ("Kıyas noktası adedi", f"{row_count:02d}", "Kaynak destekli kayıt"),
        ("0 TL / ücretsiz", f"{free_count:02d}", "Masrafsız avantaj"),
        ("En iyi POS oranı", best_new_acquiring_rate(df), "Yeni kazanım peşin"),
        ("Son kontrol", latest_label, "Kaynak kontrol tarihi"),
    ]
    html_cards = "".join(
        (
            '<div class="pricing-kpi">'
            f'<div class="pricing-label">{esc(label)}</div>'
            f'<div class="pricing-value">{esc(value)}</div>'
            f'<div class="pricing-note">{esc(note)}</div>'
            '</div>'
        )
        for label, value, note in cards
    )
    st.markdown(f'<div class="pricing-kpi-grid">{html_cards}</div>', unsafe_allow_html=True)


def render_bank_cards(df: pd.DataFrame, selected_banks: list[str]) -> None:
    cards: list[str] = []
    for bank in selected_banks:
        bank_df = df[df["institution_name"].eq(bank)]
        if bank_df.empty:
            continue
        free_count = int(bank_df["fee_value"].apply(zero_or_free).sum())
        rows = []
        for _, row in bank_df.head(3).iterrows():
            rows.append(
                '<div class="pricing-bank-item">'
                f'<div class="pricing-item-title">{esc(row.get("fee_item"))}</div>'
                f'<div class="pricing-item-meta">{esc(row.get("fee_value"))} · {esc(row.get("fee_period"))}</div>'
                '</div>'
            )
        cards.append(
            '<div class="pricing-bank-card">'
            '<div class="pricing-bank-head">'
            f'<div><div class="pricing-card-label">{esc(bank_df.iloc[0].get("institution_tier"))}</div>'
            f'<div class="pricing-bank-name">{esc(bank)}</div></div>'
            f'<span class="pricing-pill">{len(bank_df)} satır · {free_count} ücretsiz</span>'
            '</div>'
            f'<div class="pricing-bank-list">{"".join(rows)}</div>'
            '</div>'
        )
    st.markdown(f'<div class="pricing-bank-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_tier_matrix(df: pd.DataFrame, tier: str, buckets: list[str], bank_order: list[str]) -> None:
    tier_df = df[df["institution_tier"].eq(tier)].copy()
    if tier_df.empty:
        return
    tier_df["matrix_bucket"] = tier_df.apply(matrix_bucket, axis=1)
    banks = [bank for bank in bank_order if bank in set(tier_df["institution_name"])]
    visible_row_count = len(tier_df[tier_df["matrix_bucket"].isin(buckets)])
    cells = ['<div class="pricing-matrix-cell pricing-matrix-header">Banka</div>']
    cells.extend(
        f'<div class="pricing-matrix-cell pricing-matrix-header">{esc(bucket)}</div>'
        for bucket in buckets
    )
    for bank in banks:
        bank_df = tier_df[tier_df["institution_name"].eq(bank)]
        cells.append(
            '<div class="pricing-matrix-cell">'
            f'<div class="pricing-matrix-bank">{esc(bank)}</div>'
            f'<div class="pricing-matrix-tier">{esc(tier)}</div>'
            '</div>'
        )
        for bucket in buckets:
            bucket_df = bank_df[bank_df["matrix_bucket"].eq(bucket)]
            if bucket_df.empty:
                cells.append('<div class="pricing-matrix-cell"><span class="pricing-matrix-empty">Kayıt yok</span></div>')
                continue
            bucket_df = sort_matrix_bucket(bucket_df, bucket)
            items = render_matrix_items([row for _, row in bucket_df.iterrows()], bucket)
            cells.append(f'<div class="pricing-matrix-cell"><div class="pricing-matrix-items">{items}</div></div>')
    st.markdown(
        (
            '<div class="pricing-tier-panel">'
            '<div class="pricing-tier-head">'
            f'<div><div class="pricing-tier-title">{esc(tier)} ücret-komisyon matrisi</div>'
            '<div class="pricing-tier-copy">Banka satırları; kart, POS, transfer ve paket/kredi kalemleri yan yana okunur.</div></div>'
            f'<span class="pricing-pill">{len(banks)} banka · {visible_row_count} görünür satır</span>'
            '</div>'
            f'<div class="pricing-matrix" style="--pricing-column-count: {len(buckets)};">{"".join(cells)}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


pricing = read_pricing()
if pricing.empty:
    st.info("Henüz ücret-komisyon verisi yok.")
    st.stop()
    raise SystemExit

scope = render_scope_switcher()
inject_css(scope)
if scope == "Global":
    render_page_header(
        "Global Ücret Komisyon Benchmarkı",
        "Global Tier 1 bankalarda KOBİ/ticari müşteri maliyetlerini etkileyen hesap, kart, POS ve transfer uygulamaları.",
    )
else:
    render_page_header(
        "Ücret Komisyon Matrisi",
        "Tier 1 ve Tier 2 bankalarda KOBİ/ticari müşteri maliyetlerini etkileyen kart, transfer, POS ve paket ücretleri.",
    )

pricing = pricing[pricing["market_scope"].eq(scope)].copy()
bank_order = BANK_ORDER_BY_SCOPE[scope]
tier_order = TIER_ORDER_BY_SCOPE[scope]
if pricing.empty:
    st.info(f"{scope} kapsamında ücret-komisyon verisi yok.")
    st.stop()
    raise SystemExit

with st.sidebar:
    st.header("ÜVEK Filtreleri")
    tiers = [tier for tier in tier_order if tier in set(pricing["institution_tier"])]
    sync_multiselect_options("pricing_tier_filter", tiers)
    selected_tiers = st.multiselect("Banka grubu", tiers, default=tiers, key="pricing_tier_filter")
    banks = [bank for bank in bank_order if bank in set(pricing.loc[pricing["institution_tier"].isin(selected_tiers), "institution_name"])]
    families = sorted(pricing["fee_family"].unique())
    confidence = sorted(pricing["confidence_level"].unique())
    sync_multiselect_options("pricing_bank_filter", banks)
    sync_multiselect_options("pricing_fee_family_filter", families)
    sync_multiselect_options("pricing_confidence_filter", confidence)
    selected_banks = st.multiselect("Banka", banks, default=banks, key="pricing_bank_filter")
    selected_families = st.multiselect("Ücret ailesi", families, default=families, key="pricing_fee_family_filter")
    selected_confidence = st.multiselect("Güven", confidence, default=confidence, key="pricing_confidence_filter")

filtered = pricing[
    pricing["institution_tier"].isin(selected_tiers)
    & pricing["institution_name"].isin(selected_banks)
    & pricing["fee_family"].isin(selected_families)
    & pricing["confidence_level"].isin(selected_confidence)
].copy()

if filtered.empty:
    st.warning("Seçili filtrelerle eşleşen ücret satırı yok.")
    st.stop()
    raise SystemExit

render_kpis(filtered)

st.markdown('<div class="pricing-section-label">Tier bazlı ana matris</div>', unsafe_allow_html=True)
matrix_focus = st.radio(
    "Matris odağı",
    ["Tüm kalemler", *MATRIX_BUCKETS],
    horizontal=True,
    label_visibility="collapsed",
)
visible_buckets = MATRIX_BUCKETS if matrix_focus == "Tüm kalemler" else [matrix_focus]
for tier in tier_order:
    if tier in ["Tier 1", "Global Tier 1"]:
        render_tier_matrix(filtered, tier, visible_buckets, bank_order)
    else:
        with st.expander(f"{tier} ücret-komisyon matrisi", expanded=False):
            render_tier_matrix(filtered, tier, visible_buckets, bank_order)

with st.expander("Banka bazlı hızlı okuma", expanded=False):
    render_bank_cards(filtered, selected_banks)

with st.expander("Ücret-komisyon karşılaştırması", expanded=False):
    display_cols = [
        "institution_name",
        "institution_tier",
        "fee_family",
        "fee_item",
        "product_or_channel",
        "fee_value",
        "fee_basis",
        "fee_period",
        "update_date",
        "confidence_level",
    ]
    st.dataframe(
        filtered[display_cols].rename(
            columns={
                "institution_name": "Banka",
                "institution_tier": "Grup",
                "fee_family": "Ücret ailesi",
                "fee_item": "Ücret kalemi",
                "product_or_channel": "Ürün / kanal",
                "fee_value": "Ücret / oran",
                "fee_basis": "Baz",
                "fee_period": "Periyot",
                "update_date": "Güncelleme",
                "confidence_level": "Güven",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Kaynak ve okuma notları", expanded=False):
    detail_rows = []
    for _, row in filtered.iterrows():
        source = str(row.get("source_url", "")).strip()
        source_html = f'<a href="{esc(source)}" target="_blank">resmi kaynağı aç</a>' if source else "Kaynak yok"
        detail_rows.append(
            f"""
            <details class="pricing-source-detail">
              <summary>{esc(row.get("institution_name"))} · {esc(row.get("fee_item"))} · {esc(row.get("fee_value"))}</summary>
              <div class="pricing-panel">
                <div class="pricing-panel-title">{esc(row.get("fee_item"))}</div>
                <div class="pricing-panel-copy">{esc(row.get("market_read"))}</div>
                <div class="pricing-item-meta"><strong>Kapsam:</strong> {esc(row.get("customer_segment"))}</div>
                <div class="pricing-item-meta"><strong>Not:</strong> {esc(row.get("notes"))}</div>
                <div class="pricing-item-meta pricing-source"><strong>Kaynak:</strong> {source_html}</div>
              </div>
            </details>
            """
        )
    st.markdown("".join(detail_rows), unsafe_allow_html=True)
