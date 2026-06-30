from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig").fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def clean(value: object, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def decide_individual(row: pd.Series) -> str:
    text = " ".join(
        clean(row.get(column), "")
        for column in [
            "item_title",
            "headline",
            "summary",
            "core_assessment",
            "strategic_relevance",
            "strategic_theme",
            "recommended_action",
        ]
    ).casefold()
    high_signal_terms = [
        "kobi",
        "pos",
        "ödeme",
        "tahsilat",
        "api",
        "mevduat",
        "kredi",
        "nakit yönetimi",
        "kampanya",
        "iş birliği",
        "girişimci",
        "ticari",
    ]
    low_signal_terms = ["ödül", "kültür", "rapor", "sendikasyon", "sermaye tahvili"]
    if clean(row.get("review_status"), "") == "Onaylandı":
        return "Onaylandı"
    if any(term in text for term in high_signal_terms):
        return "Onayla"
    if any(term in text for term in low_signal_terms):
        return "Arşivle"
    return "Ek Araştırma Gerekli"


def decide_cluster(row: pd.Series) -> str:
    text = " ".join(
        clean(row.get(column), "")
        for column in ["cluster_title", "cluster_summary", "cluster_core_assessment", "why_it_matters"]
    ).casefold()
    if clean(row.get("review_status"), "") == "Onaylandı":
        return "Onaylandı"
    if any(term in text for term in ["ticari kart", "pos", "ödeme", "kobi", "kampanya"]):
        return "Onayla"
    return "Ek Araştırma Gerekli"


def md_row(row: pd.Series, fields: list[str]) -> list[str]:
    lines = []
    for field in fields:
        lines.append(f"- {field}: {clean(row.get(field))}")
    return lines


def append_section(lines: list[str], title: str, df: pd.DataFrame, fields: list[str], decision_fn) -> None:
    lines.append(f"\n## {title}\n")
    if df.empty:
        lines.append("Kayıt yok.\n")
        return
    for _, row in df.iterrows():
        lines.append(f"### {clean(row.get(fields[0]))}")
        lines.extend(md_row(row, fields))
        lines.append(f"- önerilen_demo_kararı: {decision_fn(row)}")
        lines.append("")


def main() -> None:
    review = read_csv(DATA_DIR / "recent_item_review_queue.csv")
    clusters = read_csv(DATA_DIR / "development_cluster_review_queue.csv")
    awareness = read_csv(DATA_DIR / "management_awareness_queue.csv")
    archive = read_csv(DATA_DIR / "recent_item_archive.csv")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = DATA_DIR / f"demo_radar_candidate_pack_{timestamp}.md"
    lines: list[str] = [
        "# Demo Yönetici Radarı Aday Paketi",
        "",
        f"Oluşturulma zamanı: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Bu paket sadece analist seçimi için hazırlanır; CSV kuyruklarını veya yayın dosyasını değiştirmez.",
        "",
        "## Özet",
        "",
        f"- Tekil inceleme adayı: {len(review)}",
        f"- Patern / küme adayı: {len(clusters)}",
        f"- Yönetici bilgilendirme adayı: {len(awareness)}",
        f"- Düşük öncelikli arşiv: {len(archive)}",
    ]

    append_section(
        lines,
        "Tekil Stratejik / BD Adayları",
        review,
        [
            "review_id",
            "institution_name",
            "item_title",
            "headline",
            "strategic_theme",
            "impact_on_us",
            "recommended_action",
            "review_status",
            "core_assessment",
            "strategic_relevance",
        ],
        decide_individual,
    )

    append_section(
        lines,
        "Patern / Küme Adayları",
        clusters,
        [
            "cluster_id",
            "institution_name",
            "cluster_title",
            "impact_on_us",
            "recommended_action",
            "review_status",
            "cluster_core_assessment",
            "why_it_matters",
            "management_takeaway",
            "item_count",
        ],
        decide_cluster,
    )

    append_section(
        lines,
        "Yönetici Bilgilendirme / İtibar Adayları",
        awareness,
        [
            "awareness_id",
            "institution_name",
            "item_title",
            "headline",
            "impact_on_us",
            "recommended_action",
            "review_status",
            "core_assessment",
            "awareness_reason",
        ],
        lambda row: "Yönetici Bilgilendirme",
    )

    lines.append("\n## Düşük Öncelikli Gürültü\n")
    if archive.empty:
        lines.append("Kayıt yok.\n")
    else:
        for _, row in archive.iterrows():
            lines.append(f"### {clean(row.get('item_title'))}")
            lines.extend(
                md_row(
                    row,
                    [
                        "summary_id",
                        "recent_item_id",
                        "institution_name",
                        "headline",
                        "impact_on_us",
                        "recommended_action",
                        "triage_reason",
                    ],
                )
            )
            lines.append("- önerilen_demo_kararı: Arşivle")
            lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Candidate pack created: {output_path}")
    print(f"Individual candidates: {len(review)}")
    print(f"Cluster candidates: {len(clusters)}")
    print(f"Management awareness candidates: {len(awareness)}")
    print(f"Archived low-priority items: {len(archive)}")


if __name__ == "__main__":
    main()
