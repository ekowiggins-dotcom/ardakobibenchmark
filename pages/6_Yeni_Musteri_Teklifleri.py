from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.ui_theme import apply_akbank_theme, render_page_header


st.set_page_config(page_title="Yeni Müşteri Teklifleri", layout="wide")
apply_akbank_theme()


DATA_PATH = Path("data/new_customer_offers.csv")
TIER_1_BANKS = ["Garanti BBVA", "İş Bankası", "Yapı Kredi"]
TIER_2_BANKS = ["DenizBank", "Enpara", "QNB Finansbank", "Odeabank", "Alternatif Bank"]
GLOBAL_BANKS = ["HSBC UK", "Santander UK", "ING Germany", "DBS Singapore", "JPMorgan Chase"]
LOCAL_BANKS = TIER_1_BANKS + TIER_2_BANKS
BANK_TIERS = (
    {bank: "Tier 1" for bank in TIER_1_BANKS}
    | {bank: "Tier 2" for bank in TIER_2_BANKS}
    | {bank: "Global Tier 1" for bank in GLOBAL_BANKS}
)
ALL_BANKS = LOCAL_BANKS + GLOBAL_BANKS


def esc(value: object) -> str:
    return html.escape(str(value or "").strip())


def read_offers() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(DATA_PATH, dtype=str).fillna("")
    if "institution_tier" not in df.columns:
        df["institution_tier"] = df["institution_name"].map(BANK_TIERS).fillna("Belirsiz")
    if "market_scope" not in df.columns:
        df["market_scope"] = df["institution_name"].apply(lambda value: "Global" if value in GLOBAL_BANKS else "Türkiye")
    df.loc[df["market_scope"].str.strip().eq(""), "market_scope"] = df["institution_name"].apply(
        lambda value: "Global" if value in GLOBAL_BANKS else "Türkiye"
    )
    return df[df["institution_name"].isin(ALL_BANKS)].copy()


def status_rank(status: str) -> int:
    return {"Aktif": 3, "Yakında bitecek": 2, "Belirsiz": 1, "Süresi doldu": 0}.get(status, 1)


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    return pd.to_datetime(str(value or "").strip(), errors="coerce")


def format_date(value: object) -> str:
    parsed = parse_date(value)
    if pd.isna(parsed):
        return "Tarih yok"
    return f"{parsed.day:02d}.{parsed.month:02d}.{parsed.year}"


def format_short_date(value: object) -> str:
    parsed = parse_date(value)
    if pd.isna(parsed):
        return "Tarih yok"
    return f"{parsed.day:02d}.{parsed.month:02d}"


def offer_is_active(row: pd.Series) -> bool:
    status = str(row.get("status", "")).strip()
    valid_until = parse_date(row.get("valid_until"))
    today = pd.Timestamp.today().normalize()
    return status == "Aktif" and (pd.isna(valid_until) or valid_until >= today)


def inject_css(scope: str) -> None:
    global_css = ""
    if scope == "Global":
        global_css = """
        html, body, .stApp, [data-testid="stAppViewContainer"] {
            background: var(--ak-global-bg) !important;
        }

        [data-testid="stHeader"] {
            background: color-mix(in srgb, var(--ak-global-bg) 94%, transparent) !important;
        }

        .offer-kpi,
        .offer-bank-card,
        .offer-panel,
        .ak-page-header {
            border-color: var(--ak-global-border);
        }

        .offer-tier-pill,
        .offer-count-pill,
        .offer-type-pill {
            background: var(--ak-global-chip);
            border-color: var(--ak-global-border);
            color: var(--ak-global-text);
        }

        .offer-detail-block {
            background: var(--ak-global-soft);
            border-color: var(--ak-global-border);
        }
        """
    st.markdown(
        """
        <style>
        """
        + global_css
        + """

        .offer-scope-toggle {
            display: flex;
            justify-content: center;
            margin: 0.2rem 0 1rem;
        }

        .offer-kpi-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 1rem;
            margin: 0.2rem 0 1.35rem;
        }

        .offer-kpi {
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-left: 2px solid var(--ak-border);
            border-radius: 14px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.07);
            padding: 1.1rem 1.2rem;
            min-height: 118px;
        }

        .offer-kpi-label,
        .offer-card-label,
        .offer-detail-label {
            color: var(--ak-muted);
            font-size: 0.7rem;
            font-weight: 850;
            letter-spacing: 0.11em;
            text-transform: uppercase;
        }

        .offer-kpi-value {
            color: var(--ak-text);
            font-size: 2.5rem;
            font-weight: 900;
            line-height: 1;
            margin-top: 0.55rem;
        }

        .offer-kpi-note {
            color: var(--ak-secondary);
            font-size: 0.82rem;
            line-height: 1.45;
            margin-top: 0.55rem;
        }

        .offer-bank-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
            margin: 0.8rem 0 1.45rem;
        }

        .offer-bank-card,
        .offer-panel {
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-radius: 14px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.07);
        }

        .offer-bank-card {
            padding: 1.15rem 1.2rem;
        }

        .offer-bank-head {
            display: flex;
            align-items: start;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .offer-bank-name {
            color: var(--ak-text);
            font-size: 1.08rem;
            font-weight: 850;
        }

        .offer-count-pill,
        .offer-tier-pill,
        .offer-type-pill,
        .offer-status-pill,
        .offer-dob-pill {
            display: inline-flex;
            align-items: center;
            border: 1px solid var(--ak-border);
            border-radius: 999px;
            color: var(--ak-text);
            background: var(--ak-soft);
            font-size: 0.72rem;
            font-weight: 800;
            padding: 0.18rem 0.52rem;
            white-space: nowrap;
        }

        .offer-status-pill {
            background: var(--ak-chip-bg);
            color: var(--ak-chip-text);
            border-color: var(--ak-chip-border);
        }

        .offer-tier-pill {
            background: var(--ak-soft);
        }

        .offer-dob-pill {
            background: var(--ak-surface);
            color: var(--ak-text);
            border-color: var(--ak-border);
        }

        .offer-bank-list {
            display: grid;
            gap: 0.85rem;
        }

        .offer-bank-item {
            border-top: 1px solid var(--ak-border);
            padding-top: 0.85rem;
        }

        .offer-title {
            color: var(--ak-text);
            font-size: 0.96rem;
            font-weight: 850;
            line-height: 1.35;
            margin-bottom: 0.45rem;
        }

        .offer-summary {
            color: var(--ak-secondary);
            font-size: 0.9rem;
            line-height: 1.55;
        }

        .offer-panel {
            padding: 1.25rem 1.35rem;
            margin-bottom: 1.15rem;
        }

        .offer-panel-head {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .offer-panel-title {
            color: var(--ak-text);
            font-size: 1.25rem;
            font-weight: 900;
            letter-spacing: -0.02em;
        }

        .offer-detail-grid {
            display: grid;
            grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
            gap: 1rem;
        }

        .offer-detail-block {
            background: var(--ak-soft);
            border: 1px solid var(--ak-border);
            border-radius: 12px;
            padding: 1rem;
        }

        .offer-detail-copy {
            color: var(--ak-text);
            font-size: 0.92rem;
            line-height: 1.62;
            margin-top: 0.5rem;
        }

        .offer-source-link a {
            color: var(--ak-text) !important;
            font-weight: 800;
            text-decoration: none !important;
        }

        .offer-source-link a:hover {
            color: var(--ak-red-dark) !important;
            text-decoration: underline !important;
        }

        @media (max-width: 1000px) {
            .offer-kpi-grid,
            .offer-bank-grid,
            .offer-detail-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(df: pd.DataFrame, selected_tiers: list[str]) -> None:
    active_count = int(df.apply(offer_is_active, axis=1).sum()) if not df.empty else 0
    faizsiz_count = int(df["offer_type"].str.contains("Faizsiz", case=False, na=False).sum())
    free_tx_count = int(df["fee_waiver"].str.strip().astype(bool).sum())
    dob_count = int(df["dob_required"].str.strip().str.casefold().eq("evet").sum())
    checked_dates = [parse_date(value) for value in df["last_checked"] if str(value).strip()]
    latest_checked = max((value for value in checked_dates if not pd.isna(value)), default=pd.NaT)
    checked_label = format_short_date(latest_checked)
    tier_label = " + ".join(selected_tiers) if selected_tiers else "Seçili kapsam"
    cards = [
        ("Aktif teklif", f"{active_count:02d}", tier_label),
        ("DOB şartlı", f"{dob_count:02d}", "Dijital müşteri olma akışı"),
        ("Faizsiz finansman", f"{faizsiz_count:02d}", "Kredi / avans odağı"),
        ("Ücret muafiyeti", f"{free_tx_count:02d}", "EFT, havale, çek, kart"),
        ("Son kontrol", checked_label, "Kaynak doğrulama tarihi"),
    ]
    html_cards = "".join(
        (
            '<div class="offer-kpi">'
            f'<div class="offer-kpi-label">{esc(label)}</div>'
            f'<div class="offer-kpi-value">{esc(value)}</div>'
            f'<div class="offer-kpi-note">{esc(note)}</div>'
            '</div>'
        )
        for label, value, note in cards
    )
    st.markdown(f'<div class="offer-kpi-grid">{html_cards}</div>', unsafe_allow_html=True)


def render_bank_cards(df: pd.DataFrame, bank_order: list[str]) -> None:
    cards: list[str] = []
    for bank in bank_order:
        bank_df = df[df["institution_name"].eq(bank)].copy()
        bank_df["_status_rank"] = bank_df["status"].apply(status_rank)
        bank_df = bank_df.sort_values(["_status_rank", "offer_type"], ascending=[False, True])
        items = []
        for _, row in bank_df.iterrows():
            items.append(
                '<div class="offer-bank-item">'
                f'<div class="offer-dob-pill">DOB: {esc(row.get("dob_required"))}</div>'
                f'<div class="offer-title">{esc(row.get("offer_title"))}</div>'
                f'<div class="offer-summary">{esc(row.get("value_summary"))}</div>'
                '</div>'
            )
        body = "".join(items) or '<div class="offer-summary">Bu kapsamda doğrulanmış teklif yok.</div>'
        cards.append(
            '<div class="offer-bank-card">'
            '<div class="offer-bank-head">'
            f'<div><div class="offer-card-label">Banka</div><div class="offer-bank-name">{esc(bank)}</div></div>'
            '<div style="display:flex; gap:.45rem; flex-wrap:wrap; justify-content:flex-end;">'
            f'<div class="offer-tier-pill">{esc(BANK_TIERS.get(bank, "Belirsiz"))}</div>'
            f'<div class="offer-count-pill">{len(bank_df)} teklif</div>'
            '</div>'
            '</div>'
            f'<div class="offer-bank-list">{body}</div>'
            '</div>'
        )
    st.markdown(f'<div class="offer-bank-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_offer_details(df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        source = str(row.get("source_url", "")).strip()
        dates = []
        if str(row.get("valid_from", "")).strip():
            dates.append(format_date(row.get("valid_from")))
        if str(row.get("valid_until", "")).strip():
            dates.append(format_date(row.get("valid_until")))
        date_text = " - ".join(dates) if dates else "Süre kaynakta net değil"
        with st.expander(
            f'{row.get("institution_name")} · {row.get("offer_type")} · {row.get("offer_title")}',
            expanded=False,
        ):
            st.markdown(
                f"""
                <div class="offer-panel">
                  <div class="offer-panel-head">
                    <div>
                      <div class="offer-card-label">{esc(row.get("institution_name"))} · {esc(row.get("target_segment"))}</div>
                      <div class="offer-panel-title">{esc(row.get("offer_title"))}</div>
                    </div>
                    <div style="display:flex; gap:.45rem; flex-wrap:wrap; justify-content:flex-end;">
                      <span class="offer-type-pill">{esc(row.get("offer_type"))}</span>
                      <span class="offer-status-pill">{esc(row.get("status"))}</span>
                      <span class="offer-dob-pill">DOB: {esc(row.get("dob_required"))}</span>
                    </div>
                  </div>
                  <div class="offer-detail-grid">
                    <div class="offer-detail-block">
                      <div class="offer-detail-label">Teklif özeti</div>
                      <div class="offer-detail-copy">{esc(row.get("value_summary"))}</div>
                      <div class="offer-detail-copy"><strong>Tutar:</strong> {esc(row.get("amount"))}</div>
                      <div class="offer-detail-copy"><strong>Süre:</strong> {esc(row.get("term"))}</div>
                      <div class="offer-detail-copy"><strong>Geçerlilik:</strong> {esc(date_text)}</div>
                    </div>
                    <div class="offer-detail-block">
                      <div class="offer-detail-label">Koşul ve Akbank notu</div>
                      <div class="offer-detail-copy"><strong>DOB şartı:</strong> {esc(row.get("dob_required"))} · {esc(row.get("dob_channel"))}</div>
                      <div class="offer-detail-copy"><strong>DOB kanıtı:</strong> {esc(row.get("dob_evidence"))}</div>
                      <div class="offer-detail-copy"><strong>Gerekli aksiyon:</strong> {esc(row.get("required_action"))}</div>
                      <div class="offer-detail-copy"><strong>Uygunluk:</strong> {esc(row.get("eligibility"))}</div>
                      <div class="offer-detail-copy"><strong>Akbank için:</strong> {esc(row.get("akbank_implication"))}</div>
                      <div class="offer-detail-copy offer-source-link"><strong>Kaynak:</strong> {f'<a href="{esc(source)}" target="_blank">resmi sayfayı aç</a>' if source else "Kaynak yok"}</div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


offers = read_offers()
if offers.empty:
    st.info("Henüz yeni müşteri teklifi verisi yok.")
    st.stop()
    raise SystemExit

scope = st.radio("Kapsam", ["Türkiye", "Global"], horizontal=True, label_visibility="collapsed")
inject_css(scope)
if scope == "Global":
    render_page_header(
        "Global Yeni Müşteri Teklifleri",
        "Global Tier 1 bankaların yeni business/SME müşteri kazanımı için sunduğu hesap açılışı, ücret muafiyeti ve ödül teklifleri.",
    )
else:
    render_page_header(
        "Yeni Müşteri Teklifleri",
        "Tier 1 ve Tier 2 bankaların yeni tüzel/KOBİ müşteri kazanımı için sunduğu faizsiz finansman, işlem muafiyeti ve ticari kart teklifleri.",
    )

offers = offers[offers["market_scope"].eq(scope)].copy()
bank_order = GLOBAL_BANKS if scope == "Global" else LOCAL_BANKS

offers["_is_active"] = offers.apply(offer_is_active, axis=1)
offers["_status_rank"] = offers["status"].apply(status_rank)
offers["_valid_until_dt"] = pd.to_datetime(offers["valid_until"], errors="coerce")

with st.sidebar:
    st.header("Teklif Filtreleri")
    tier_order = ["Global Tier 1"] if scope == "Global" else ["Tier 1", "Tier 2"]
    tiers = [tier for tier in tier_order if tier in set(offers["institution_tier"])]
    selected_tiers = st.multiselect("Banka grubu", tiers, default=tiers)
    tier_banks = [bank for bank in bank_order if BANK_TIERS.get(bank) in selected_tiers]
    banks = [bank for bank in tier_banks if bank in set(offers["institution_name"])]
    types = sorted(offers["offer_type"].unique())
    statuses = sorted(offers["status"].unique())
    dob_options = sorted(offers["dob_required"].unique())
    selected_banks = st.multiselect("Banka", banks, default=banks)
    selected_types = st.multiselect("Teklif tipi", types, default=types)
    selected_statuses = st.multiselect("Durum", statuses, default=statuses)
    selected_dob = st.multiselect("DOB şartı", dob_options, default=dob_options)

filtered = offers[
    offers["institution_tier"].isin(selected_tiers)
    & offers["institution_name"].isin(selected_banks)
    & offers["offer_type"].isin(selected_types)
    & offers["status"].isin(selected_statuses)
    & offers["dob_required"].isin(selected_dob)
].copy()

if filtered.empty:
    st.warning("Seçili filtrelerle eşleşen teklif yok.")
    st.stop()
    raise SystemExit

render_kpis(filtered, selected_tiers)
render_bank_cards(filtered, selected_banks)

st.subheader("Teklif Detayları")
filtered = filtered.sort_values(["_status_rank", "institution_name", "offer_type"], ascending=[False, True, True])
render_offer_details(filtered)

st.subheader("Karşılaştırma Matrisi")
matrix_cols = [
    "institution_name",
    "institution_tier",
    "offer_type",
    "target_segment",
    "dob_required",
    "dob_channel",
    "amount",
    "term",
    "fee_waiver",
    "valid_until",
    "confidence_level",
]
st.dataframe(
    filtered[matrix_cols].rename(
        columns={
            "institution_name": "Banka",
            "institution_tier": "Grup",
            "offer_type": "Teklif tipi",
            "target_segment": "Hedef segment",
            "dob_required": "DOB şartı",
            "dob_channel": "DOB kanalı",
            "amount": "Tutar / fayda",
            "term": "Süre",
            "fee_waiver": "Ücret muafiyeti",
            "valid_until": "Bitiş",
            "confidence_level": "Güven",
        }
    ),
    use_container_width=True,
    hide_index=True,
)
