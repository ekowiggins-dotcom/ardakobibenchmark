import pandas as pd

from utils.translations import to_tr


STRATEGIC_DIMENSIONS = [
    "KOBİ Mevduat Önermesi",
    "Gömülü Finans Olgunluğu",
    "Ödemeler ve Üye İşyeri Edinimi",
    "Dijital KOBİ Yolculuğu",
    "Nakit Yönetimi",
    "KOBİ Kredi Bağlantısı",
    "Ekosistem İş Birlikleri",
    "Fiyatlama Şeffaflığı",
    "BD Kullanılabilirliği",
    "Stratejik Tehdit Seviyesi",
]


def score_pivot(scores: pd.DataFrame) -> pd.DataFrame:
    normalized = scores.copy()
    normalized["dimension"] = normalized["dimension"].apply(to_tr)
    return normalized.pivot_table(
        index="institution_id",
        columns="dimension",
        values="score_1_to_5",
        aggfunc="mean",
    ).reindex(columns=STRATEGIC_DIMENSIONS)


def overall_scores(scores: pd.DataFrame, institutions: pd.DataFrame) -> pd.DataFrame:
    overall = (
        scores.groupby("institution_id", as_index=False)["score_1_to_5"]
        .mean()
        .rename(columns={"score_1_to_5": "overall_score"})
    )
    return overall.merge(
        institutions[
            ["institution_id", "institution_name", "institution_type", "country", "region"]
        ],
        on="institution_id",
        how="left",
    ).sort_values("overall_score", ascending=False)


def dimension_ranking(
    scores: pd.DataFrame, institutions: pd.DataFrame, dimension: str
) -> pd.DataFrame:
    normalized_dimension = to_tr(dimension)
    normalized = scores.copy()
    normalized["dimension"] = normalized["dimension"].apply(to_tr)
    ranked = normalized[normalized["dimension"] == normalized_dimension].copy()
    ranked = ranked.merge(
        institutions[
            ["institution_id", "institution_name", "institution_type", "country", "region"]
        ],
        on="institution_id",
        how="left",
    )
    return ranked.sort_values("score_1_to_5", ascending=False)


def top_in_dimension(scores: pd.DataFrame, institutions: pd.DataFrame, dimension: str) -> pd.Series:
    ranking = dimension_ranking(scores, institutions, dimension)
    return ranking.iloc[0]


def strategic_gap_text(scores: pd.DataFrame, institutions: pd.DataFrame) -> str:
    deposit_top = top_in_dimension(scores, institutions, "SME Deposit Proposition")
    embedded_top = top_in_dimension(scores, institutions, "Embedded Finance Maturity")
    payments_top = top_in_dimension(scores, institutions, "Payments & Merchant Acquiring")
    threat_top = top_in_dimension(scores, institutions, "Strategic Threat Level")

    return (
        f"{deposit_top['institution_name']} örnek mevduat benchmark’ında öne çıkarken "
        f"{embedded_top['institution_name']} en güçlü gömülü finans referansını oluşturuyor. "
        f"{payments_top['institution_name']} ödemeler benchmark’ında yakından izlenmesi gereken kurum. "
        f"En yüksek stratejik tehdit sinyali {threat_top['institution_name']} tarafında; bu da ödeme "
        "odaklı ve iş akışı odaklı önerilerin geleneksel bankalarla birlikte takip edilmesi gerektiğini gösteriyor."
    )


def confidence_filtered(scores: pd.DataFrame, selected_confidence: list[str]) -> pd.DataFrame:
    if not selected_confidence:
        return scores
    return scores[scores["confidence_level"].isin(selected_confidence)]
