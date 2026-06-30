from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

import pandas as pd


CLUSTER_COLUMNS = [
    "cluster_id",
    "institution_name",
    "cluster_title",
    "cluster_summary",
    "cluster_core_assessment",
    "strategic_theme",
    "product_area",
    "development_type",
    "recommended_action",
    "impact_on_us",
    "importance_level",
    "confidence_level",
    "cluster_start_date",
    "cluster_end_date",
    "item_count",
    "item_ids",
    "item_titles",
    "source_urls",
    "created_at",
    "review_status",
    "analyst_note",
]

PATTERNS = [
    {
        "key": "commercial_card_campaigns",
        "title": "{institution} ticari kart aktivasyonunu Haziran kampanyalarıyla destekliyor",
        "summary": "{institution} ticari kart kullanımını artırmak için birden fazla kart/MaxiPuan kampanyasını aynı dönemde yürütüyor.",
        "core": "Tekil kampanyalar küçük; birlikte ticari kart aktivasyonu için net rekabet sinyali.",
        "theme": "Kampanyalar",
        "product_area": "Ödemeler ve POS",
        "development_type": "Kampanya",
        "action": "BD Konuşma Notlarına Ekle",
        "impact": "Orta",
        "importance": "Orta",
        "keywords": [
            "ticari kart",
            "ticari kredi kart",
            "ticari bankamatik",
            "maximum business",
            "maxipuan",
            "yurt dışı harcama",
            "yurt disi harcama",
            "maximum",
        ],
    },
    {
        "key": "pos_okc_device_finance",
        "title": "{institution} mobil ÖKC/POS edinimini kampanya finansmanıyla kolaylaştırıyor",
        "summary": "{institution} POS, mobil ÖKC veya üye işyeri cihaz edinimini taksit/vade avantajıyla destekleyen kampanyalar yürütüyor.",
        "core": "Cihaz edinimi kampanyası KOBİ üye işyeri kazanımı ve POS aktivasyonu açısından izlenmeli.",
        "theme": "Ödemeler ve POS",
        "product_area": "Ödemeler ve POS",
        "development_type": "Kampanya",
        "action": "İzle",
        "impact": "Orta",
        "importance": "Orta",
        "keywords": ["pos", "ökc", "okc", "mobil ökc", "cihaz", "ingenico", "paygo", "hugin", "üye işyeri", "uye isyeri", "taksit"],
    },
    {
        "key": "esg_sustainability_finance",
        "title": "{institution} KOBİ finansmanında sürdürülebilirlik temasını kullanıyor",
        "summary": "{institution} sürdürülebilirlik, çevre veya enerji verimliliği başlıklarını finansman mesajına bağlıyor.",
        "core": "Sürdürülebilirlik teması niş olabilir; ilgili KOBİ segmentlerinde konuşma açıcı olarak izlenmeli.",
        "theme": "KOBİ Kredileri",
        "product_area": "KOBİ Kredileri",
        "development_type": "Pazar Sinyali",
        "action": "İzle",
        "impact": "Düşük",
        "importance": "Orta",
        "keywords": ["sürdürülebilirlik", "esg", "atık su", "atik su", "çevre", "yeşil finansman", "leasing", "enerji verimliliği", "arıtma"],
    },
]

STOPWORDS = {
    "ve",
    "ile",
    "icin",
    "için",
    "bir",
    "yeni",
    "özel",
    "kampanyası",
    "kampanya",
    "bankası",
    "turkiye",
    "türkiye",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+", _clean(text).casefold())
    return {token for token in raw if len(token) >= 4 and token not in STOPWORDS}


def _contains_pattern(text: str, pattern: dict) -> bool:
    lower = _clean(text).casefold()
    hits = sum(1 for keyword in pattern["keywords"] if keyword.casefold() in lower)
    return hits >= 2 if pattern["key"] == "commercial_card_campaigns" else hits >= 1


def _cluster_id(institution: str, key: str, item_ids: list[str]) -> str:
    digest = hashlib.sha1(f"{institution}:{key}:{','.join(sorted(item_ids))}".encode("utf-8")).hexdigest()[:12]
    return f"CL-{digest}"


def _json_list(values: list[str]) -> str:
    return json.dumps([value for value in values if _clean(value)], ensure_ascii=False)


def _date_bounds(group: pd.DataFrame) -> tuple[str, str]:
    dates = pd.to_datetime(
        group.get("recency_basis_date", group.get("normalized_item_date", "")),
        errors="coerce",
    ).dropna()
    if dates.empty:
        return "", ""
    return dates.min().date().isoformat(), dates.max().date().isoformat()


def _keyword_fallback_groups(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    groups: list[tuple[str, pd.DataFrame]] = []
    used: set[str] = set()
    candidates = df.copy()
    for idx, row in candidates.iterrows():
        item_id = _clean(row.get("recent_item_id", ""))
        if not item_id or item_id in used:
            continue
        row_tokens = _tokens(" ".join(_clean(row.get(col, "")) for col in ["item_title", "headline", "summary", "core_assessment"]))
        if len(row_tokens) < 3:
            continue
        similar = []
        for jdx, other in candidates.iterrows():
            other_id = _clean(other.get("recent_item_id", ""))
            if not other_id or other_id in used:
                continue
            if _clean(row.get("institution_name")) != _clean(other.get("institution_name")):
                continue
            if _clean(row.get("strategic_theme")) != _clean(other.get("strategic_theme")) and _clean(row.get("product_area")) != _clean(other.get("product_area")):
                continue
            other_tokens = _tokens(" ".join(_clean(other.get(col, "")) for col in ["item_title", "headline", "summary", "core_assessment"]))
            overlap = len(row_tokens & other_tokens)
            union = len(row_tokens | other_tokens) or 1
            if overlap >= 3 and overlap / union >= 0.22:
                similar.append(jdx)
        if len(similar) >= 2:
            cluster = candidates.loc[similar].copy()
            groups.append(("keyword_overlap", cluster))
            used.update(cluster["recent_item_id"].astype(str))
    return groups


def _build_cluster(institution: str, key: str, group: pd.DataFrame, pattern: dict | None = None) -> dict[str, object]:
    item_ids = group["recent_item_id"].dropna().astype(str).tolist()
    item_titles = group["item_title"].dropna().astype(str).tolist()
    urls = group["item_url"].dropna().astype(str).tolist()
    start_date, end_date = _date_bounds(group)

    if pattern:
        title = pattern["title"].format(institution=institution)
        summary = pattern["summary"].format(institution=institution)
        core = pattern["core"]
        theme = pattern["theme"]
        product_area = pattern["product_area"]
        development_type = pattern["development_type"]
        action = pattern["action"]
        impact = pattern["impact"]
        importance = pattern["importance"]
    else:
        theme = group.get("strategic_theme", pd.Series(["Kampanyalar"])).mode().iloc[0] if "strategic_theme" in group else "Kampanyalar"
        product_area = group.get("product_area", pd.Series(["Diğer"])).mode().iloc[0] if "product_area" in group else "Diğer"
        development_type = group.get("development_type", pd.Series(["Pazar Sinyali"])).mode().iloc[0] if "development_type" in group else "Pazar Sinyali"
        title = f"{institution}: benzer {product_area} gelişmeleri aynı dönemde yoğunlaşıyor"
        summary = "Benzer tema ve ürün alanındaki birden fazla gelişme aynı dönemde kümeleniyor."
        core = "Patern var ancak stratejik gücü analist kontrolü gerektiriyor."
        action = "İzle"
        impact = "Orta"
        importance = "Orta"

    return {
        "cluster_id": _cluster_id(institution, key, item_ids),
        "institution_name": institution,
        "cluster_title": title,
        "cluster_summary": summary,
        "cluster_core_assessment": core,
        "strategic_theme": theme,
        "product_area": product_area,
        "development_type": development_type,
        "recommended_action": action,
        "impact_on_us": impact,
        "importance_level": importance,
        "confidence_level": "Orta",
        "cluster_start_date": start_date,
        "cluster_end_date": end_date,
        "item_count": len(group),
        "item_ids": _json_list(item_ids),
        "item_titles": _json_list(item_titles),
        "source_urls": _json_list(urls),
        "created_at": utc_now(),
        "review_status": "Beklemede",
        "analyst_note": "",
    }


def cluster_recent_developments(df: pd.DataFrame, window_days: int = 45) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=CLUSTER_COLUMNS)

    work = df.copy()
    for column in ["recent_item_id", "institution_name", "item_title", "headline", "summary", "core_assessment", "recency_basis_date", "normalized_item_date"]:
        if column not in work.columns:
            work[column] = ""
    work["_cluster_date"] = pd.to_datetime(work["recency_basis_date"].where(work["recency_basis_date"].astype(str).str.len() > 0, work["normalized_item_date"]), errors="coerce")
    work = work[pd.notna(work["_cluster_date"])].copy()

    rows = []
    used_items: set[str] = set()
    for institution, inst_df in work.groupby("institution_name", dropna=False):
        institution_name = _clean(institution)
        for pattern in PATTERNS:
            text = inst_df.apply(
                lambda row: " ".join(_clean(row.get(col, "")) for col in ["item_title", "headline", "summary", "core_assessment"]),
                axis=1,
            )
            pattern_df = inst_df[text.apply(lambda value: _contains_pattern(value, pattern))].copy()
            if len(pattern_df) < 2:
                continue
            min_date = pattern_df["_cluster_date"].min()
            max_date = pattern_df["_cluster_date"].max()
            if pd.notna(min_date) and pd.notna(max_date) and (max_date - min_date).days > window_days:
                continue
            rows.append(_build_cluster(institution_name, pattern["key"], pattern_df, pattern))
            used_items.update(pattern_df["recent_item_id"].astype(str))

        fallback_source = inst_df[~inst_df["recent_item_id"].astype(str).isin(used_items)].copy()
        for key, group in _keyword_fallback_groups(fallback_source):
            rows.append(_build_cluster(institution_name, key, group, None))
            used_items.update(group["recent_item_id"].astype(str))

    if not rows:
        return pd.DataFrame(columns=CLUSTER_COLUMNS)
    return pd.DataFrame(rows).reindex(columns=CLUSTER_COLUMNS)
