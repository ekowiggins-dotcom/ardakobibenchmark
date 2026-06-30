import plotly.express as px


BANK_COLORS = {
    "Turkish Bank": "#1f77b4",
    "Türk Bankası": "#1f77b4",
    "Public Bank": "#0f766e",
    "Kamu Bankası": "#0f766e",
    "Participation Bank": "#7c3aed",
    "Katılım Bankası": "#7c3aed",
    "Payment Institution": "#d97706",
    "Ödeme Kuruluşu": "#d97706",
    "Card Scheme": "#334155",
    "Kart Şeması": "#334155",
    "Global Fintech": "#dc2626",
    "Global Fintek": "#dc2626",
    "Global Bank": "#475569",
    "Global Banka": "#475569",
}


def bar_scores(df, x_col, y_col, title, color_col="institution_type", height=420):
    fig = px.bar(
        df,
        x=x_col,
        y=y_col,
        color=color_col if color_col in df.columns else None,
        color_discrete_map=BANK_COLORS,
        text=df[y_col].round(1),
        title=title,
        height=height,
    )
    fig.update_layout(
        xaxis_title="",
        yaxis_title="Skor",
        legend_title="Kurum tipi",
        margin=dict(l=10, r=10, t=60, b=20),
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    return fig


def heatmap(pivot_df, title):
    fig = px.imshow(
        pivot_df,
        text_auto=".1f",
        aspect="auto",
        color_continuous_scale=["#f8fafc", "#bfdbfe", "#2563eb"],
        zmin=1,
        zmax=5,
        title=title,
        height=max(420, 26 * len(pivot_df)),
    )
    fig.update_layout(margin=dict(l=10, r=10, t=60, b=20), coloraxis_colorbar_title="Skor")
    return fig


def horizontal_rank(df, label_col, score_col, title, color_col="institution_type"):
    ranked = df.sort_values(score_col, ascending=True)
    fig = px.bar(
        ranked,
        x=score_col,
        y=label_col,
        orientation="h",
        color=color_col if color_col in ranked.columns else None,
        color_discrete_map=BANK_COLORS,
        text=ranked[score_col].round(1),
        title=title,
        height=max(360, 24 * len(ranked)),
    )
    fig.update_layout(
        xaxis_title="Skor",
        yaxis_title="",
        legend_title="Kurum tipi",
        margin=dict(l=10, r=10, t=60, b=20),
    )
    return fig
