from __future__ import annotations

import html
import re
from collections import Counter
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.recent_mvp import (
    MANAGEMENT_AWARENESS_COLUMNS,
    build_unified_developments,
    clean_text,
    read_csv_safe,
)
from utils.institution_aliases import institution_group
from utils.ui_theme import PALETTE, apply_akbank_theme, render_page_header


st.set_page_config(page_title="Tüm Gelişmeler", layout="wide")
apply_akbank_theme()


THEME_SHORT_LABELS = {
    "Ekosistem İş Birlikleri": "Ekosistem İş Bir.",
    "Global İyi Uygulamalar": "Global İyi Uyg.",
    "Global İyi Uygulama": "Global İyi Uyg.",
    "Dijital KOBİ Yolculuğu": "Dijital KOBİ",
    "Digital SME Journey": "Dijital KOBİ",
    "Kurumsal Konumlandırma": "Kurumsal Konum.",
    "Ödemeler ve POS": "Ödemeler & POS",
    "Payments & POS": "Ödemeler & POS",
    "Nakit Yönetimi": "Nakit Yönetimi",
    "Cash Management": "Nakit Yönetimi",
    "KOBİ Kredileri": "KOBİ Kredileri",
    "SME Lending": "KOBİ Kredileri",
    "Gömülü Finans": "Gömülü Finans",
    "Embedded Finance": "Gömülü Finans",
    "Regülasyon": "Regülasyon",
    "Regulation": "Regülasyon",
    "Kampanyalar": "Kampanyalar",
    "SME Deposits": "KOBİ Mevduat",
}

TURKISH_STOPWORDS = {
    "acaba",
    "ama",
    "ancak",
    "artık",
    "aslında",
    "alternatif",
    "arasında",
    "ayrıca",
    "aynı",
    "bazı",
    "belki",
    "ben",
    "benzer",
    "bile",
    "bir",
    "biraz",
    "birçok",
    "biri",
    "biz",
    "bu",
    "buna",
    "bunda",
    "bundan",
    "bunu",
    "dair",
    "çok",
    "çünkü",
    "da",
    "dan",
    "daha",
    "de",
    "den",
    "defa",
    "değil",
    "diye",
    "dış",
    "edecek",
    "eden",
    "ederek",
    "edilen",
    "ediliyor",
    "etti",
    "ettiği",
    "en",
    "finance",
    "genel",
    "gibi",
    "göre",
    "hem",
    "haber",
    "hem",
    "her",
    "için",
    "ilgili",
    "ilişkin",
    "ile",
    "ilk",
    "in",
    "ise",
    "kadar",
    "kapsamında",
    "karşı",
    "kurum",
    "kurumsal",
    "olarak",
    "olan",
    "önce",
    "oldu",
    "olduğu",
    "olmak",
    "olması",
    "olduğunu",
    "sahip",
    "seçildi",
    "sonra",
    "sonuç",
    "şu",
    "tarafın",
    "tarafında",
    "tarafından",
    "türki",
    "türkiye",
    "üzerinden",
    "ve",
    "veya",
    "yönelik",
    "ya",
    "yani",
    "yeni",
    "nin",
    "nın",
    "nun",
    "nün",
    "dir",
    "dır",
    "dur",
    "dür",
    "tir",
    "tır",
    "tur",
    "tür",
    "banka",
    "bank",
    "bankası",
    "banker",
    "gelişme",
    "madde",
    "içerik",
    "yönetici",
    "gönderilen",
    "global",
    "awards",
    "award",
    "akbank",
    "garanti",
    "bbva",
    "yapı",
    "qnb",
    "finansbank",
    "aldı",
    "düzenlenen",
    "itibarını",
    "platform",
    "platformu",
    "pratik",
    "önemi",
    "sinyali",
    "şekerbank",
    "the",
    "türk",
    "üretmiyor",
}

CONCEPT_ALIASES = {
    "kobiler": "kobi",
    "kobiye": "kobi",
    "kobinin": "kobi",
    "kobilere": "kobi",
    "kobi'lere": "kobi",
    "kobilerin": "kobi",
    "müşteriler": "müşteri",
    "müşterilere": "müşteri",
    "müşterilerinin": "müşteri",
    "ödemeler": "ödeme",
    "ödemeyi": "ödeme",
    "tahsilatı": "tahsilat",
    "tahsilatta": "tahsilat",
    "finansmanı": "finansman",
    "finansmana": "finansman",
    "dijitalleşme": "dijital",
    "dijitalleşmeyi": "dijital",
    "dönüşümü": "dönüşüm",
    "dönüşüme": "dönüşüm",
    "işbirliği": "iş birliği",
    "entegrasyonu": "entegrasyon",
    "entegrasyonları": "entegrasyon",
    "kartları": "kart",
    "kartı": "kart",
    "ödülleri": "ödül",
    "ödülü": "ödül",
    "ödüller": "ödül",
    "finansmanı": "finansman",
    "nakdi": "nakit",
    "nakdin": "nakit",
    "yönetimi": "yönetim",
    "müşteri": "müşteri",
    "musteri": "müşteri",
    "kobİ": "kobi",
    "kobı": "kobi",
    "pos": "pos",
}

PHRASE_ALIASES = {
    "iş birliği": "işbirliği",
    "iş birlikleri": "işbirliği",
    "üye işyeri": "üyeişyeri",
    "üye işyerleri": "üyeişyeri",
    "açık bankacılık": "açıkbankacılık",
    "gömülü finans": "gömülüfinans",
}

DISPLAY_WORDS = {
    "işbirliği": "iş birliği",
    "üyeişyeri": "üye işyeri",
    "açıkbankacılık": "açık bankacılık",
    "gömülüfinans": "gömülü finans",
}


def inject_page_css() -> None:
    st.markdown(
        f"""
        <style>
        .ak-kpi-grid {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 1rem;
            margin: 0.35rem 0 1.35rem;
        }}

        .ak-metric-card {{
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-left: 2px solid var(--ak-border);
            border-radius: 14px;
            box-shadow: var(--ak-shadow-soft);
            padding: 1.15rem 1.2rem;
            min-height: 116px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}

        .ak-kpi-label {{
            color: var(--ak-secondary);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.65rem;
        }}

        .ak-kpi-value {{
            color: var(--ak-text);
            font-size: 2.45rem;
            font-weight: 900;
            line-height: 1;
        }}

        .ak-kpi-range {{
            color: var(--ak-muted);
            font-size: 0.5625rem;
            font-weight: 800;
            letter-spacing: 0.18em;
            line-height: 1.35;
            margin-top: 0.35rem;
            text-transform: uppercase;
        }}

        @media (max-width: 1100px) {{
            .ak-kpi-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
        }}

        .ak-section-title {{
            color: var(--ak-text);
            font-size: 1.18rem;
            font-weight: 850;
            margin: 0.2rem 0 0.35rem;
        }}

        .ak-section-caption {{
            color: var(--ak-secondary);
            font-size: 0.92rem;
            margin: -0.15rem 0 0.75rem;
        }}

        div[data-testid="stPlotlyChart"] {{
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-radius: 14px;
            box-shadow: var(--ak-shadow-soft);
            padding: 0.75rem 0.75rem 0.25rem;
        }}

        .ak-wordcloud-card {{
            background: var(--ak-surface);
            border: 1px solid var(--ak-border);
            border-radius: 14px;
            box-shadow: var(--ak-shadow-soft);
            padding: 1.1rem;
            margin-bottom: 1rem;
        }}

        .ak-wordcloud-fallback {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem 0.9rem;
            align-items: center;
            min-height: 210px;
            padding: 0.4rem 0.2rem;
        }}

        .ak-word {{
            display: inline-flex;
            align-items: center;
            color: var(--ak-text);
            font-weight: 850;
            line-height: 1.1;
        }}

        .ak-word-red {{
            color: var(--ak-red-dark);
        }}

        </style>
        """,
        unsafe_allow_html=True,
    )


def theme_short_label(value: str) -> str:
    value = clean_text(value, "Belirsiz")
    return THEME_SHORT_LABELS.get(value, value if len(value) <= 18 else f"{value[:16].rstrip()}…")


def plot_layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["text_main"], family="Arial, sans-serif"),
        margin=dict(l=18, r=18, t=22, b=18),
        showlegend=False,
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=PALETTE["border"],
        tickfont=dict(color=PALETTE["text_secondary"]),
        ticks="",
    )
    fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        linecolor=PALETTE["border"],
        tickfont=dict(color=PALETTE["text_secondary"]),
        ticks="",
    )
    return fig


def render_section_title(title: str, caption: str = "") -> None:
    caption_html = f'<div class="ak-section-caption">{html.escape(caption)}</div>' if caption else ""
    st.markdown(
        f'<div class="ak-section-title">{html.escape(title)}</div>{caption_html}',
        unsafe_allow_html=True,
    )


def render_kpis(filtered: pd.DataFrame) -> None:
    queue_count = int(filtered["status"].astype(str).eq("İncelemede").sum())
    weekly_count = int(filtered["status"].astype(str).eq("Yayınlandı").sum())
    archive_count = int(filtered["status"].astype(str).eq("Düşük Öncelik / Arşiv").sum())
    archive_ratio = f"{(archive_count / len(filtered) * 100):.0f}%" if len(filtered) else "0%"
    cards = [
        ("Yakaladığımız Gelişme", f"{len(filtered):02d}" if len(filtered) < 100 else str(len(filtered)), "Son 30 gün"),
        ("İnceleme Altında", f"{queue_count:02d}" if queue_count < 100 else str(queue_count), "Toplam"),
        ("Özete Eklenen", f"{weekly_count:02d}" if weekly_count < 100 else str(weekly_count), "Toplam"),
        ("Arşivlenen", f"{archive_count:02d}" if archive_count < 100 else str(archive_count), "Yıl başından beri"),
        ("PR / Arşiv Oranı", archive_ratio, "Yıl başından beri"),
    ]
    card_html = "".join(
        (
            '<div class="ak-metric-card">'
            f'<div class="ak-kpi-label">{html.escape(label)}</div>'
            f'<div class="ak-kpi-value">{html.escape(value)}</div>'
            f'<div class="ak-kpi-range">{html.escape(time_range)}</div>'
            "</div>"
        )
        for label, value, time_range in cards
    )
    st.markdown(f'<div class="ak-kpi-grid">{card_html}</div>', unsafe_allow_html=True)


def institution_chart(filtered: pd.DataFrame) -> go.Figure:
    counts = filtered["institution_name"].replace("", "Belirsiz").value_counts().reset_index()
    counts.columns = ["Kurum", "Gelişme"]
    counts = counts.sort_values("Gelişme", ascending=True)
    max_value = counts["Gelişme"].max() if not counts.empty else 0
    colors = [PALETTE["primary_red"] if value == max_value else PALETTE["border_strong"] for value in counts["Gelişme"]]
    fig = go.Figure(
        go.Bar(
            x=counts["Gelişme"],
            y=counts["Kurum"],
            orientation="h",
            text=counts["Gelişme"],
            textposition="outside",
            textfont=dict(color=PALETTE["text_muted"], family="Arial, sans-serif"),
            marker=dict(color=colors, line=dict(color=PALETTE["border"], width=1)),
            hovertemplate="<b>%{y}</b><br>Gelişme: %{x}<extra></extra>",
        )
    )
    fig = plot_layout(fig, height=max(320, 34 * len(counts) + 70))
    fig.update_xaxes(title="", rangemode="tozero")
    fig.update_yaxes(title="")
    return fig


def theme_chart(filtered: pd.DataFrame) -> go.Figure:
    counts = filtered["strategic_theme"].replace("", "Belirsiz").value_counts().reset_index()
    counts.columns = ["Tema", "Gelişme"]
    counts["Kısa Tema"] = counts["Tema"].apply(theme_short_label)
    counts = counts.sort_values("Gelişme", ascending=True)
    max_value = counts["Gelişme"].max() if not counts.empty else 0
    colors = [PALETTE["primary_red"] if value == max_value else PALETTE["border_strong"] for value in counts["Gelişme"]]
    fig = go.Figure(
        go.Bar(
            x=counts["Gelişme"],
            y=counts["Kısa Tema"],
            orientation="h",
            text=counts["Gelişme"],
            textposition="outside",
            textfont=dict(color=PALETTE["text_muted"], family="Arial, sans-serif"),
            customdata=counts["Tema"],
            marker=dict(color=colors, line=dict(color=PALETTE["border"], width=1)),
            hovertemplate="<b>%{customdata}</b><br>Gelişme: %{x}<extra></extra>",
        )
    )
    fig = plot_layout(fig, height=max(320, 34 * len(counts) + 70))
    fig.update_xaxes(title="", rangemode="tozero")
    fig.update_yaxes(title="")
    return fig


def trend_chart(filtered: pd.DataFrame) -> go.Figure:
    trend = filtered.copy()
    trend["date"] = trend["date_dt"].dt.date
    counts = trend.groupby("date").size().reset_index(name="Gelişme")
    max_value = counts["Gelişme"].max() if not counts.empty else 0
    colors = [PALETTE["primary_red"] if value == max_value else PALETTE["text_secondary"] for value in counts["Gelişme"]]
    fig = go.Figure(
        go.Bar(
            x=counts["date"],
            y=counts["Gelişme"],
            text=counts["Gelişme"],
            textposition="outside",
            textfont=dict(color=PALETTE["text_muted"], family="Arial, sans-serif"),
            marker=dict(color=colors, line=dict(color=PALETTE["border"], width=1)),
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Gelişme: %{y}<extra></extra>",
        )
    )
    fig = plot_layout(fig, height=340)
    fig.update_xaxes(title="", tickformat="%d %b", showgrid=False, ticks="")
    fig.update_yaxes(
        title="",
        rangemode="tozero",
        dtick=1,
        showgrid=True,
        gridcolor=PALETTE["border"],
        griddash="dot",
        ticks="",
    )
    return fig


def normalize_word(token: str) -> str:
    token = token.strip("'-’`")
    token = re.sub(r"^(nin|nın|nun|nün|in|ın|un|ün)$", "", token)
    token = re.sub(r"(nin|nın|nun|nün|in|ın|un|ün)$", "", token)
    token = re.sub(r"(dir|dır|dur|dür|tir|tır|tur|tür)$", "", token)
    token = CONCEPT_ALIASES.get(token, token)
    for suffix in (
        "lerinin",
        "larının",
        "lere",
        "lara",
        "leri",
        "ları",
        "lerden",
        "lardan",
        "den",
        "dan",
        "ten",
        "tan",
        "yle",
        "yla",
        "ye",
        "ya",
        "ler",
        "lar",
    ):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            token = token[: -len(suffix)]
            break
    return CONCEPT_ALIASES.get(token, token)


def management_awareness_texts(awareness: pd.DataFrame, filtered: pd.DataFrame) -> pd.Series:
    if awareness.empty:
        return pd.Series(dtype=str)
    filtered_ids = set(filtered["recent_item_id"].dropna().astype(str))
    scoped = awareness[awareness["recent_item_id"].astype(str).isin(filtered_ids)].copy()
    text_columns = ["headline", "summary", "strategic_relevance", "analyst_note"]
    for column in text_columns:
        if column not in scoped.columns:
            scoped[column] = ""
    return scoped[text_columns].fillna("").agg(" ".join, axis=1)


def word_frequencies(awareness: pd.DataFrame, filtered: pd.DataFrame) -> Counter:
    texts = " ".join(management_awareness_texts(awareness, filtered).astype(str).tolist()).casefold()
    texts = re.sub(r"<[^>]+>", " ", texts)
    texts = re.sub(r"https?://\\S+|www\\.\\S+", " ", texts)
    for phrase, alias in PHRASE_ALIASES.items():
        texts = texts.replace(phrase, alias)
    texts = re.sub(r"[^a-zçğıöşü0-9\\s]", " ", texts)
    texts = re.sub(r"\\d+", " ", texts)
    counter: Counter = Counter()
    for raw in texts.split():
        token = normalize_word(raw)
        if not token or len(token) < 3 or token in TURKISH_STOPWORDS:
            continue
        if token.isnumeric() or any(char.isdigit() for char in token):
            continue
        if token in TURKISH_STOPWORDS:
            continue
        counter[DISPLAY_WORDS.get(token, token)] += 1
    return counter


def render_wordcloud(counter: Counter) -> None:
    with st.container(border=True):
        render_section_title(
            "Özete Eklenen Gelişmelerde Öne Çıkan Kelimeler",
            "Özete eklenen maddelerde en sık tekrar eden anlamlı kavramları gösterir.",
        )
        if not counter:
            st.info("Seçili filtrelerde yöneticiye gönderilen gelişme bulunmadığı için kelime bulutu oluşturulamadı.")
            return
        try:
            import matplotlib.pyplot as plt
            from wordcloud import WordCloud

            color_cycle = [
                PALETTE["primary_red"],
                PALETTE["primary_red_dark"],
                PALETTE["text_main"],
                PALETTE["text_secondary"],
                PALETTE["border_strong"],
            ]

            def color_func(*args, **kwargs) -> str:
                return color_cycle[hash(args[0]) % len(color_cycle)]

            cloud = WordCloud(
                width=1400,
                height=320,
                background_color="white",
                prefer_horizontal=0.95,
                collocations=False,
                random_state=7,
                max_words=38,
                min_word_length=3,
                relative_scaling=0.45,
                color_func=color_func,
                margin=12,
            ).generate_from_frequencies(counter)
            fig, ax = plt.subplots(figsize=(14, 3.2), dpi=130)
            ax.imshow(cloud, interpolation="bilinear")
            ax.axis("off")
            buffer = BytesIO()
            fig.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0, transparent=False)
            plt.close(fig)
            st.image(buffer.getvalue(), use_container_width=True)
        except Exception:
            max_count = max(counter.values()) or 1
            words = []
            for idx, (word, count) in enumerate(counter.most_common(32)):
                size = 0.95 + (count / max_count) * 1.85
                color_class = " ak-word-red" if idx % 3 == 0 else ""
                words.append(
                    f'<span class="ak-word{color_class}" style="font-size:{size:.2f}rem">{html.escape(word)}</span>'
                )
            st.markdown(f'<div class="ak-wordcloud-fallback">{" ".join(words)}</div>', unsafe_allow_html=True)


inject_page_css()
render_page_header(
    "Tüm Gelişmeler",
    "Çıkarılan, özetlenen, incelenen, arşivlenen ve yöneticiye gönderilen tüm recent-development maddeleri.",
)

items = build_unified_developments()
awareness = read_csv_safe("management_awareness_queue.csv", MANAGEMENT_AWARENESS_COLUMNS)

if items.empty:
    st.info("Henüz çıkarılmış gelişme yok. Önce recent item pipeline’ını çalıştırın.")
    st.stop()
    raise SystemExit

items["date_dt"] = items["date_dt"].fillna(pd.Timestamp.utcnow().tz_localize(None))
items["institution_group"] = items["institution_name"].apply(institution_group)

with st.sidebar:
    st.header("Gelişme Filtreleri")
    institution_groups = sorted(items["institution_group"].dropna().astype(str).unique())
    institutions = sorted(items["institution_name"].dropna().astype(str).unique())
    statuses = sorted(items["status"].dropna().astype(str).unique())
    themes = sorted(items["strategic_theme"].dropna().astype(str).unique())
    product_areas = sorted(items["product_area"].dropna().astype(str).unique())
    development_types = sorted(items["development_type"].dropna().astype(str).unique())
    impacts = sorted(items["impact_on_us"].dropna().astype(str).unique())
    actions = sorted(items["recommended_action"].dropna().astype(str).unique())
    confidences = sorted(items["confidence_level"].dropna().astype(str).unique())
    source_types = sorted(items["source_type"].dropna().astype(str).unique())
    date_confidences = sorted(items["date_confidence"].dropna().astype(str).unique())
    candidate_types = sorted(items["development_candidate_type"].dropna().astype(str).unique())
    min_date = items["date_dt"].min().date()
    max_date = items["date_dt"].max().date()

    recent_mode = st.radio("Recency", ["Sadece recent", "Tümü"], horizontal=True)
    actual_only = st.checkbox("Sadece actual development", value=True)
    start_filter = st.date_input("Start date", value=pd.to_datetime("2026-05-01").date())
    selected_institution_groups = st.multiselect("Kurum grubu", institution_groups, default=institution_groups)
    selected_institutions = st.multiselect("Kurum", institutions, default=institutions)
    selected_statuses = st.multiselect("Durum", statuses, default=statuses)
    selected_themes = st.multiselect("Tema", themes, default=themes)
    selected_product_areas = st.multiselect("Ürün alanı", product_areas, default=product_areas)
    selected_development_types = st.multiselect("Gelişme tipi", development_types, default=development_types)
    selected_impacts = st.multiselect("Etki", impacts, default=impacts)
    selected_actions = st.multiselect("Aksiyon", actions, default=actions)
    selected_confidences = st.multiselect("Güven", confidences, default=confidences)
    selected_date_confidences = st.multiselect("Tarih güveni", date_confidences, default=date_confidences)
    selected_candidate_types = st.multiselect("Aday tipi", candidate_types, default=candidate_types)
    selected_source_types = st.multiselect("Kaynak tipi", source_types, default=source_types)
    selected_range = st.date_input("Tarih aralığı", value=(min_date, max_date), min_value=min_date, max_value=max_date)

if isinstance(selected_range, tuple) and len(selected_range) == 2:
    start_date, end_date = selected_range
else:
    start_date, end_date = min_date, max_date

filtered = items[
    items["institution_group"].isin(selected_institution_groups)
    & items["institution_name"].isin(selected_institutions)
    & items["status"].isin(selected_statuses)
    & items["strategic_theme"].isin(selected_themes)
    & items["product_area"].isin(selected_product_areas)
    & items["development_type"].isin(selected_development_types)
    & items["impact_on_us"].isin(selected_impacts)
    & items["recommended_action"].isin(selected_actions)
    & items["confidence_level"].isin(selected_confidences)
    & items["date_confidence"].isin(selected_date_confidences)
    & items["development_candidate_type"].isin(selected_candidate_types)
    & items["source_type"].isin(selected_source_types)
    & (items["date_dt"].dt.date >= start_date)
    & (items["date_dt"].dt.date <= end_date)
].copy()
if recent_mode == "Sadece recent":
    filtered = filtered[filtered["is_recent"].astype(str).str.casefold().isin(["true", "1", "yes", "evet"])].copy()
if actual_only:
    filtered = filtered[filtered["is_actual_development"].astype(str).str.casefold().isin(["true", "1", "yes", "evet"])].copy()
if "normalized_item_date" in filtered.columns:
    normalized_dates = pd.to_datetime(filtered["normalized_item_date"], errors="coerce")
    filtered = filtered[normalized_dates.dt.date >= start_filter].copy()

if filtered.empty:
    st.warning("Seçili filtrelerle eşleşen gelişme yok.")
    st.stop()
    raise SystemExit

render_kpis(filtered)

render_section_title("Kuruma göre gelişme sayısı", "Filtrelenen gelişmelerin kurum kırılımı.")
st.plotly_chart(institution_chart(filtered), use_container_width=True, config={"displayModeBar": False})

render_section_title("Temaya göre gelişme sayısı", "Uzun tema adları kısaltıldı; tam adlar hover içinde görünür.")
st.plotly_chart(theme_chart(filtered), use_container_width=True, config={"displayModeBar": False})

word_counter = word_frequencies(awareness, filtered)
render_section_title("Zaman içinde gelişme sayısı", "Filtrelenen maddelerin tarih bazlı akışı.")
st.plotly_chart(trend_chart(filtered), use_container_width=True, config={"displayModeBar": False})

render_wordcloud(word_counter)

st.subheader("Gelişme Listesi")
table_cols = [
    "item_title",
    "institution_name",
    "item_date",
    "status",
    "strategic_theme",
    "product_area",
    "development_type",
    "impact_on_us",
    "recommended_action",
    "confidence_level",
    "date_confidence",
    "development_candidate_type",
]
st.dataframe(
    filtered[table_cols].rename(
        columns={
            "item_title": "Aday başlık",
            "institution_name": "Kurum",
            "item_date": "Tarih",
            "status": "Durum",
            "strategic_theme": "Tema",
            "product_area": "Ürün alanı",
            "development_type": "Gelişme tipi",
            "impact_on_us": "Etki",
            "recommended_action": "Aksiyon",
            "confidence_level": "Güven",
            "date_confidence": "Tarih güveni",
            "development_candidate_type": "Aday tipi",
        }
    ),
    use_container_width=True,
    hide_index=True,
)
