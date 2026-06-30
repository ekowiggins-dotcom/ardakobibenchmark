import streamlit as st


def sidebar_filters(institutions, scores=None, key_prefix="global"):
    st.sidebar.header("Filtreler")
    type_options = sorted(institutions["institution_type"].dropna().unique())
    country_options = sorted(institutions["country"].dropna().unique())

    selected_types = st.sidebar.multiselect(
        "Kurum tipi",
        type_options,
        default=type_options,
        key=f"{key_prefix}_types",
    )
    selected_countries = st.sidebar.multiselect(
        "Ülke",
        country_options,
        default=country_options,
        key=f"{key_prefix}_countries",
    )

    filtered_institutions = institutions[
        institutions["institution_type"].isin(selected_types)
        & institutions["country"].isin(selected_countries)
    ]

    selected_confidence = None
    filtered_scores = scores
    if scores is not None and "confidence_level" in scores.columns:
        confidence_options = sorted(scores["confidence_level"].dropna().unique())
        selected_confidence = st.sidebar.multiselect(
            "Güven seviyesi",
            confidence_options,
            default=confidence_options,
            key=f"{key_prefix}_confidence",
        )
        filtered_scores = scores[
            scores["institution_id"].isin(filtered_institutions["institution_id"])
            & scores["confidence_level"].isin(selected_confidence)
        ]

    return filtered_institutions, filtered_scores, selected_confidence
