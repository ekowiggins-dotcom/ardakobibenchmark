from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.ui_theme import apply_akbank_theme, render_page_header


st.set_page_config(page_title="Bankaların AI Çalışmaları", layout="wide")
apply_akbank_theme()


DATA_PATH = Path("data/bank_ai_initiatives.csv")
BANK_ORDER_BY_TIER = {
    "Tier 1": ["Akbank", "Garanti BBVA", "İş Bankası", "Yapı Kredi"],
    "Tier 2": ["DenizBank", "Enpara", "QNB Finansbank", "Odeabank", "Alternatif Bank"],
}
ALL_BANKS = [bank for banks in BANK_ORDER_BY_TIER.values() for bank in banks]
MATRIX_BUCKETS = [
    "KOBİ & SaaS",
    "Müşteri AI",
    "Pazarlama",
    "İç Kullanım",
    "Ekosistem",
    "Yönetişim",
]


def esc(value: object) -> str:
    return html.escape(str(value or "").strip())


def read_initiatives() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()
    frame = pd.read_csv(DATA_PATH, dtype=str).fillna("")
    return frame[frame["institution_name"].isin(ALL_BANKS)].copy()


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    return pd.to_datetime(str(value or "").strip(), errors="coerce")


def format_date(value: object) -> str:
    parsed = parse_date(value)
    if pd.isna(parsed):
        return "Tarih belirtilmemiş"
    return f"{parsed.day:02d}.{parsed.month:02d}.{parsed.year}"


def short_date(value: object) -> str:
    parsed = parse_date(value)
    if pd.isna(parsed):
        return "Tarih yok"
    return f"{parsed.day:02d}.{parsed.month:02d}"


def matrix_bucket(row: pd.Series) -> str:
    category = str(row.get("ai_category", ""))
    initiative_type = str(row.get("initiative_type", ""))
    if category == "KOBİ AI Çözümü" or initiative_type == "SaaS / İş Birliği":
        return "KOBİ & SaaS"
    if category == "Müşteri Asistanı":
        return "Müşteri AI"
    if category == "Pazarlama & Deneyim" or initiative_type == "AI Kampanyası":
        return "Pazarlama"
    if category in {"Çalışan Verimliliği", "Risk & Operasyon"}:
        return "İç Kullanım"
    if category == "Ekosistem & Girişimcilik":
        return "Ekosistem"
    return "Yönetişim"


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .ai-kpi-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 1rem;
            margin: 0 0 1.4rem;
        }

        .ai-kpi,
        .ai-bank-card,
        .ai-panel,
        .ai-matrix-wrap {
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-radius: 14px;
            box-shadow: var(--ak-shadow-soft);
        }

        .ai-kpi {
            min-height: 116px;
            padding: 1.05rem 1.15rem;
        }

        .ai-kpi-label,
        .ai-label,
        .ai-detail-label {
            color: var(--ak-muted);
            font-size: 0.68rem;
            font-weight: 850;
            letter-spacing: 0.11em;
            text-transform: uppercase;
        }

        .ai-kpi-value {
            color: var(--ak-text);
            font-size: 2.35rem;
            font-weight: 900;
            line-height: 1;
            margin-top: 0.52rem;
        }

        .ai-kpi-note {
            color: var(--ak-secondary);
            font-size: 0.8rem;
            line-height: 1.4;
            margin-top: 0.5rem;
        }

        .ai-section-head {
            align-items: flex-end;
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin: 1.55rem 0 0.75rem;
        }

        .ai-section-title {
            color: var(--ak-text);
            font-size: 1.35rem;
            font-weight: 900;
            letter-spacing: 0;
        }

        .ai-section-copy {
            color: var(--ak-secondary);
            font-size: 0.86rem;
            margin-top: 0.2rem;
        }

        .ai-count-pill,
        .ai-tag,
        .ai-relevance,
        .ai-evidence {
            align-items: center;
            background: var(--ak-soft);
            border: 1px solid var(--ak-border);
            border-radius: 999px;
            color: var(--ak-text);
            display: inline-flex;
            font-size: 0.69rem;
            font-weight: 800;
            padding: 0.2rem 0.55rem;
            white-space: nowrap;
        }

        .ai-relevance-high {
            background: var(--ak-chip-bg);
            border-color: var(--ak-chip-border);
            color: var(--ak-chip-text);
        }

        .ai-bank-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
        }

        .ai-insight-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
        }

        .ai-insight-card {
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-top: 2px solid var(--ak-border-strong);
            border-radius: 14px;
            box-shadow: var(--ak-shadow-soft);
            min-height: 148px;
            padding: 1rem 1.1rem;
        }

        .ai-insight-card-featured {
            border-top-color: var(--ak-red);
        }

        .ai-insight-title {
            color: var(--ak-text);
            font-size: 0.98rem;
            font-weight: 900;
            line-height: 1.35;
            margin-top: 0.4rem;
        }

        .ai-insight-copy {
            color: var(--ak-secondary);
            font-size: 0.84rem;
            line-height: 1.55;
            margin-top: 0.5rem;
        }

        .ai-bank-card {
            min-height: 186px;
            padding: 1.1rem 1.15rem;
        }

        .ai-bank-head {
            align-items: flex-start;
            display: flex;
            justify-content: space-between;
            gap: 0.8rem;
            margin-bottom: 0.9rem;
        }

        .ai-bank-name {
            color: var(--ak-text);
            font-size: 1.05rem;
            font-weight: 900;
        }

        .ai-bank-stat-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            border-bottom: 1px solid var(--ak-border);
            border-top: 1px solid var(--ak-border);
            margin-bottom: 0.85rem;
        }

        .ai-bank-stat {
            padding: 0.7rem 0.35rem;
        }

        .ai-bank-stat + .ai-bank-stat {
            border-left: 1px solid var(--ak-border);
        }

        .ai-bank-stat strong {
            color: var(--ak-text);
            display: block;
            font-size: 1.15rem;
            font-variant-numeric: tabular-nums;
        }

        .ai-bank-stat span {
            color: var(--ak-muted);
            display: block;
            font-size: 0.63rem;
            font-weight: 800;
            letter-spacing: 0.06em;
            margin-top: 0.14rem;
            text-transform: uppercase;
        }

        .ai-bank-highlight {
            color: var(--ak-secondary);
            font-size: 0.82rem;
            line-height: 1.48;
        }

        .ai-matrix-wrap {
            overflow-x: auto;
        }

        .ai-matrix {
            border-collapse: collapse;
            min-width: 1160px;
            table-layout: fixed;
            width: 100%;
        }

        .ai-matrix th {
            background: var(--ak-soft);
            border-bottom: 1px solid var(--ak-border-strong);
            color: var(--ak-muted);
            font-size: 0.65rem;
            font-weight: 850;
            letter-spacing: 0.09em;
            padding: 0.75rem;
            text-align: left;
            text-transform: uppercase;
        }

        .ai-matrix td {
            border-bottom: 1px solid var(--ak-border);
            border-right: 1px solid var(--ak-border);
            color: var(--ak-text);
            padding: 0.75rem;
            vertical-align: top;
        }

        .ai-matrix tr:last-child td {
            border-bottom: 0;
        }

        .ai-matrix td:last-child,
        .ai-matrix th:last-child {
            border-right: 0;
        }

        .ai-matrix-bank {
            font-size: 0.88rem;
            font-weight: 900;
            width: 130px;
        }

        .ai-matrix-item {
            color: var(--ak-text) !important;
            display: block;
            font-size: 0.75rem;
            font-weight: 750;
            line-height: 1.38;
            padding: 0.25rem 0;
            text-decoration: none !important;
        }

        .ai-matrix-item + .ai-matrix-item {
            border-top: 1px solid var(--ak-border);
            margin-top: 0.25rem;
            padding-top: 0.48rem;
        }

        .ai-matrix-item:hover {
            color: var(--ak-red-dark) !important;
            text-decoration: underline !important;
        }

        .ai-matrix-empty {
            color: var(--ak-muted);
            font-size: 0.75rem;
        }

        .ai-panel {
            margin-bottom: 0.85rem;
            padding: 1.05rem 1.1rem;
        }

        .ai-panel-head {
            align-items: flex-start;
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.85rem;
        }

        .ai-panel-title {
            color: var(--ak-text);
            font-size: 1.2rem;
            font-weight: 900;
            line-height: 1.3;
            margin-top: 0.2rem;
        }

        .ai-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            justify-content: flex-end;
        }

        .ai-summary {
            background: var(--ak-soft);
            border: 1px solid var(--ak-border);
            border-left: 2px solid var(--ak-red);
            border-radius: 10px;
            color: var(--ak-text);
            font-size: 0.9rem;
            line-height: 1.58;
            margin-bottom: 0.85rem;
            padding: 0.85rem 0.95rem;
        }

        .ai-detail-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.8rem;
        }

        .ai-detail-block {
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-radius: 10px;
            padding: 0.9rem;
        }

        .ai-detail-copy {
            color: var(--ak-secondary);
            font-size: 0.85rem;
            line-height: 1.58;
            margin-top: 0.45rem;
        }

        .ai-source a {
            color: var(--ak-text) !important;
            font-weight: 800;
            text-decoration: none !important;
        }

        .ai-source a:hover {
            color: var(--ak-red-dark) !important;
            text-decoration: underline !important;
        }

        @media (max-width: 1100px) {
            .ai-kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
            .ai-bank-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .ai-insight-grid { grid-template-columns: 1fr; }
        }

        @media (max-width: 700px) {
            .ai-kpi-grid,
            .ai-bank-grid,
            .ai-detail-grid { grid-template-columns: 1fr; }
            .ai-section-head,
            .ai-panel-head { align-items: flex-start; flex-direction: column; }
            .ai-tags { justify-content: flex-start; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(frame: pd.DataFrame, tier_label: str) -> None:
    customer_products = frame[frame["delivery_model"].isin(["Banka ürünü", "Platform entegrasyonu"])]
    sme_items = frame[frame["sme_relevance"].eq("Yüksek")]
    saas_items = frame[frame["delivery_model"].eq("Partner SaaS")]
    latest_checked = max((parse_date(value) for value in frame["last_verified"]), default=pd.NaT)
    cards = [
        ("Bakılan banka", f"{frame['institution_name'].nunique():02d}", f"{tier_label} Türkiye"),
        ("AI çalışması", f"{len(frame):02d}", "Doğrulanmış kayıt"),
        ("Müşteri ürünü", f"{len(customer_products):02d}", "Ürün ve kanal"),
        ("KOBİ ilgisi yüksek", f"{len(sme_items):02d}", f"SaaS iş birliği: {len(saas_items):02d}"),
        ("Son kontrol", short_date(latest_checked), "Resmî kaynak doğrulaması"),
    ]
    cards_html = "".join(
        (
            '<div class="ai-kpi">'
            f'<div class="ai-kpi-label">{esc(label)}</div>'
            f'<div class="ai-kpi-value">{esc(value)}</div>'
            f'<div class="ai-kpi-note">{esc(note)}</div>'
            "</div>"
        )
        for label, value, note in cards
    )
    st.markdown(f'<div class="ai-kpi-grid">{cards_html}</div>', unsafe_allow_html=True)


def render_section_header(title: str, copy: str, count: int) -> None:
    st.markdown(
        (
            '<div class="ai-section-head">'
            f'<div><div class="ai-section-title">{esc(title)}</div>'
            f'<div class="ai-section-copy">{esc(copy)}</div></div>'
            f'<span class="ai-count-pill">{count} kayıt</span>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_bank_cards(frame: pd.DataFrame, banks: list[str], tier_label: str) -> None:
    cards: list[str] = []
    for bank in banks:
        bank_frame = frame[frame["institution_name"].eq(bank)].copy()
        direct_sme = int(bank_frame["sme_relevance"].eq("Yüksek").sum())
        customer = int(bank_frame["delivery_model"].isin(["Banka ürünü", "Platform entegrasyonu"]).sum())
        internal = int(bank_frame["delivery_model"].eq("İç kullanım").sum())
        highlight_rows = bank_frame.sort_values(
            "sme_relevance",
            key=lambda series: series.map({"Yüksek": 0, "Orta": 1, "Dolaylı": 2, "Düşük": 3}).fillna(4),
        )
        highlight = highlight_rows.iloc[0]["initiative_name"] if not highlight_rows.empty else "Kayıt yok"
        cards.append(
            '<div class="ai-bank-card">'
            '<div class="ai-bank-head">'
            f'<div><div class="ai-label">{esc(tier_label)}</div><div class="ai-bank-name">{esc(bank)}</div></div>'
            f'<span class="ai-count-pill">{len(bank_frame)} çalışma</span>'
            "</div>"
            '<div class="ai-bank-stat-grid">'
            f'<div class="ai-bank-stat"><strong>{direct_sme}</strong><span>KOBİ</span></div>'
            f'<div class="ai-bank-stat"><strong>{customer}</strong><span>Müşteri AI</span></div>'
            f'<div class="ai-bank-stat"><strong>{internal}</strong><span>İç kullanım</span></div>'
            "</div>"
            f'<div class="ai-bank-highlight"><strong>Öne çıkan:</strong> {esc(highlight)}</div>'
            "</div>"
        )
    st.markdown(f'<div class="ai-bank-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_insights(frame: pd.DataFrame, bank_order: list[str]) -> None:
    customer_ai = frame[frame.apply(matrix_bucket, axis=1).eq("Müşteri AI")]
    customer_banks = customer_ai["institution_name"].nunique()
    direct_sme = frame[frame["sme_relevance"].eq("Yüksek")]
    direct_sme_banks = ", ".join(
        bank for bank in bank_order if bank in set(direct_sme["institution_name"])
    ) or "Henüz doğrulanmış banka yok"
    partner_saas = frame[frame["delivery_model"].eq("Partner SaaS")]
    campaign_count = int(frame["initiative_type"].eq("AI Kampanyası").sum())

    insights = [
        (
            "Patern",
            "Asistan yarışı ürünleşiyor",
            f"{customer_banks} banka müşteri asistanı veya mesajlaşma tabanlı AI sunuyor. Ayrışma artık chatbot sahibi olmaktan çok işlem tamamlama ve üçüncü taraf kanallara taşınma derinliğinde.",
            False,
        ),
        (
            "KOBİ fırsat alanı",
            "Doğrudan KOBİ AI teklifi hâlâ sınırlı",
            f"KOBİ ilgisi yüksek {len(direct_sme)} çalışma {direct_sme_banks} tarafında görülüyor. Nakit akışı, tahsilat ve muhasebe copilot'ı için belirgin ürün boşluğu var.",
            True,
        ),
        (
            "Dağıtım modeli",
            "SaaS ortaklıkları yeni rekabet katmanı",
            f"İlk taramada {len(partner_saas)} partner SaaS kaydı ve {campaign_count} doğrulanmış AI harcama kampanyası var. Akbank'ın Usersdot modeli farklı KOBİ yazılımlarına genişletilebilir.",
            False,
        ),
    ]
    cards = "".join(
        (
            f'<div class="ai-insight-card{" ai-insight-card-featured" if featured else ""}">'
            f'<div class="ai-label">{esc(label)}</div>'
            f'<div class="ai-insight-title">{esc(title)}</div>'
            f'<div class="ai-insight-copy">{esc(copy)}</div>'
            "</div>"
        )
        for label, title, copy, featured in insights
    )
    st.markdown(f'<div class="ai-insight-grid">{cards}</div>', unsafe_allow_html=True)


def render_tier_view(frame: pd.DataFrame, tier_label: str, banks: list[str]) -> None:
    if frame.empty:
        st.info(f"Seçili filtrelerle {tier_label} için eşleşen AI çalışması yok.")
        return

    render_kpis(frame, tier_label)

    render_section_header(
        "Benchmark özeti",
        f"{tier_label} taramasından çıkan ortak paternler ve Akbank için açık alanlar.",
        3,
    )
    render_insights(frame, banks)

    render_section_header(
        f"{tier_label} görünümü",
        "Banka bazında müşteri AI, kurum içi kullanım ve KOBİ bağlantısının hızlı özeti.",
        len(frame),
    )
    render_bank_cards(frame, banks, tier_label)

    render_section_header(
        "AI yetenek matrisi",
        "Aynı yetenek alanındaki çalışmalar bankalar arasında yan yana okunur; başlıklar resmî kaynağa gider.",
        len(frame),
    )
    render_matrix(frame, banks)

    render_section_header(
        "Çalışma detayları",
        "Her kayıtta çözüm, AI yetkinliği, KOBİ ilgisi ve Akbank benchmark notu birlikte gösterilir.",
        len(frame),
    )
    render_details(frame)


def render_matrix(frame: pd.DataFrame, banks: list[str]) -> None:
    header = "".join(f"<th>{esc(bucket)}</th>" for bucket in MATRIX_BUCKETS)
    rows: list[str] = []
    for bank in banks:
        bank_frame = frame[frame["institution_name"].eq(bank)].copy()
        bank_frame["_bucket"] = bank_frame.apply(matrix_bucket, axis=1)
        cells: list[str] = []
        for bucket in MATRIX_BUCKETS:
            bucket_frame = bank_frame[bank_frame["_bucket"].eq(bucket)]
            links = []
            for _, row in bucket_frame.head(2).iterrows():
                source = esc(row.get("source_url"))
                title = esc(row.get("initiative_name"))
                links.append(
                    f'<a class="ai-matrix-item" href="{source}" target="_blank" rel="noopener noreferrer">{title}</a>'
                    if source
                    else f'<span class="ai-matrix-item">{title}</span>'
                )
            if len(bucket_frame) > 2:
                links.append(f'<span class="ai-matrix-empty">+{len(bucket_frame) - 2} çalışma</span>')
            cells.append(f'<td>{"".join(links) if links else "<span class=\"ai-matrix-empty\">Kayıt yok</span>"}</td>')
        rows.append(f'<tr><td class="ai-matrix-bank">{esc(bank)}</td>{"".join(cells)}</tr>')
    st.markdown(
        (
            '<div class="ai-matrix-wrap"><table class="ai-matrix">'
            f'<thead><tr><th>Banka</th>{header}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
        ),
        unsafe_allow_html=True,
    )


def render_details(frame: pd.DataFrame) -> None:
    relevance_order = {"Yüksek": 0, "Orta": 1, "Dolaylı": 2, "Düşük": 3}
    detail_frame = frame.copy()
    detail_frame["_relevance_rank"] = detail_frame["sme_relevance"].map(relevance_order).fillna(4)
    detail_frame["_launch_date"] = pd.to_datetime(detail_frame["launch_date"], errors="coerce")
    detail_frame = detail_frame.sort_values(
        ["_relevance_rank", "_launch_date", "institution_name"],
        ascending=[True, False, True],
        na_position="last",
    )
    for _, row in detail_frame.iterrows():
        relevance = str(row.get("sme_relevance", ""))
        relevance_class = " ai-relevance-high" if relevance == "Yüksek" else ""
        source = str(row.get("source_url", "")).strip()
        with st.expander(
            f'{row.get("institution_name")} · {row.get("initiative_name")} · KOBİ ilgisi: {relevance}',
            expanded=False,
        ):
            st.markdown(
                f"""
                <div class="ai-panel">
                  <div class="ai-panel-head">
                    <div>
                      <div class="ai-label">{esc(row.get("institution_name"))} · {esc(row.get("initiative_type"))}</div>
                      <div class="ai-panel-title">{esc(row.get("initiative_name"))}</div>
                    </div>
                    <div class="ai-tags">
                      <span class="ai-tag">{esc(row.get("ai_category"))}</span>
                      <span class="ai-relevance{relevance_class}">KOBİ: {esc(relevance)}</span>
                      <span class="ai-evidence">Kanıt: {esc(row.get("evidence_level"))}</span>
                    </div>
                  </div>
                  <div class="ai-summary">{esc(row.get("description"))}</div>
                  <div class="ai-detail-grid">
                    <div class="ai-detail-block">
                      <div class="ai-detail-label">Çözdüğü ihtiyaç</div>
                      <div class="ai-detail-copy">{esc(row.get("customer_problem"))}</div>
                      <div class="ai-detail-copy"><strong>AI yetkinliği:</strong> {esc(row.get("ai_capability"))}</div>
                      <div class="ai-detail-copy"><strong>Sunum modeli:</strong> {esc(row.get("delivery_model"))}</div>
                    </div>
                    <div class="ai-detail-block">
                      <div class="ai-detail-label">Benchmark notu</div>
                      <div class="ai-detail-copy">{esc(row.get("akbank_relevance"))}</div>
                      <div class="ai-detail-copy"><strong>Partner:</strong> {esc(row.get("partner_name") or "Yok / belirtilmemiş")}</div>
                      <div class="ai-detail-copy"><strong>Lansman:</strong> {esc(format_date(row.get("launch_date")))}</div>
                      <div class="ai-detail-copy ai-source"><strong>Kaynak:</strong> {f'<a href="{esc(source)}" target="_blank" rel="noopener noreferrer">resmî kaynağı aç</a>' if source else "Kaynak yok"}</div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


initiatives = read_initiatives()
if initiatives.empty:
    st.info("Henüz banka AI çalışması verisi yok.")
    st.stop()
    raise SystemExit

inject_css()
latest_verified = max((parse_date(value) for value in initiatives["last_verified"]), default=pd.NaT)
render_page_header(
    "Bankaların AI Çalışmaları",
    "Tier 1 ve Tier 2 bankaların AI ürünleri, KOBİ çözümleri, SaaS iş birlikleri, kampanyaları ve kurum içi yetkinlikleri.",
    updated_at=format_date(latest_verified),
)

with st.sidebar:
    st.header("AI Benchmark Filtreleri")
    selected_banks_by_tier: dict[str, list[str]] = {}
    for tier_label, tier_banks in BANK_ORDER_BY_TIER.items():
        available_banks = [bank for bank in tier_banks if bank in set(initiatives["institution_name"])]
        selected_banks_by_tier[tier_label] = st.multiselect(
            f"{tier_label} bankalar",
            available_banks,
            default=available_banks,
            key=f"ai_banks_{tier_label.lower().replace(' ', '_')}",
        )
    categories = sorted(initiatives["ai_category"].unique())
    selected_categories = st.multiselect("AI alanı", categories, default=categories)
    initiative_types = sorted(initiatives["initiative_type"].unique())
    selected_types = st.multiselect("Çalışma türü", initiative_types, default=initiative_types)
    relevance_options = [value for value in ["Yüksek", "Orta", "Dolaylı", "Düşük"] if value in set(initiatives["sme_relevance"])]
    selected_relevance = st.multiselect("KOBİ ilgisi", relevance_options, default=relevance_options)
    evidence_options = [value for value in ["Yüksek", "Orta", "Düşük"] if value in set(initiatives["evidence_level"])]
    selected_evidence = st.multiselect("Kanıt seviyesi", evidence_options, default=evidence_options)

filtered = initiatives[
    initiatives["ai_category"].isin(selected_categories)
    & initiatives["initiative_type"].isin(selected_types)
    & initiatives["sme_relevance"].isin(selected_relevance)
    & initiatives["evidence_level"].isin(selected_evidence)
].copy()

tier_tabs = st.tabs(
    [
        f"Tier 1 · {len(BANK_ORDER_BY_TIER['Tier 1'])} banka",
        f"Tier 2 · {len(BANK_ORDER_BY_TIER['Tier 2'])} banka",
    ]
)

for tab, tier_label in zip(tier_tabs, BANK_ORDER_BY_TIER):
    with tab:
        selected_banks = selected_banks_by_tier[tier_label]
        tier_frame = filtered[
            filtered["institution_tier"].eq(tier_label)
            & filtered["institution_name"].isin(selected_banks)
        ].copy()
        render_tier_view(tier_frame, tier_label, selected_banks)
