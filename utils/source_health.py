from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd


HEALTHY = "Sağlıklı"
WARNING = "Uyarı"
ERROR = "Hatalı"
STALE = "Uzun Süredir Güncellenmedi"
MANUAL = "Manuel Kontrol Gerekli"
COMPLETE = "Tam Kapsama"
PARTIAL = "Kısmi Kapsama"
NO_COVERAGE = "Kapsama Yok"


@dataclass(frozen=True)
class SourceHealth:
    status: str
    reason: str


def _clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _parse_dt(value) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def classify_source_health(
    *,
    latest_status: str = "",
    status_code: str | int = "",
    content_length: int | str = 0,
    candidate_item_count: int | str = 0,
    consecutive_failures: int | str = 0,
    last_success_at: str = "",
    last_changed_at: str = "",
    collection_method: str = "",
    extraction_mode: str = "",
    stale_days: int = 120,
    now: datetime | None = None,
) -> SourceHealth:
    """Classify one active source using operational thresholds.

    This function is intentionally small and deterministic so the weekly runner
    and tests can share the same source-health logic.
    """

    now = now or datetime.now(timezone.utc)
    latest_status = _clean(latest_status).casefold()
    method = _clean(collection_method).casefold()
    mode = _clean(extraction_mode).casefold()
    try:
        failures = int(float(consecutive_failures or 0))
    except Exception:
        failures = 0
    try:
        http_status = int(float(status_code)) if _clean(status_code) else 0
    except Exception:
        http_status = 0
    try:
        length = int(float(content_length or 0))
    except Exception:
        length = 0
    raw_candidate_count = _clean(candidate_item_count)
    try:
        candidates = int(float(raw_candidate_count)) if raw_candidate_count else -1
    except Exception:
        candidates = -1

    if method in {"manual", "browser", "browser_required", "js"} or "manual" in mode:
        return SourceHealth(MANUAL, "Kaynak manuel veya tarayıcı tabanlı kontrol gerektiriyor.")

    if failures >= 3:
        return SourceHealth(ERROR, f"{failures} ardışık başarısız kontrol var.")
    if http_status in {403, 404, 500, 502, 503, 504}:
        return SourceHealth(ERROR if failures >= 2 else WARNING, f"HTTP {http_status} döndü.")
    if latest_status == "error":
        return SourceHealth(ERROR if failures >= 2 else WARNING, "Son kontrol hata ile sonuçlandı.")
    if latest_status == "fetched" and length <= 50:
        return SourceHealth(ERROR, "Çıkarılan içerik boş veya çok kısa.")
    if failures in {1, 2}:
        return SourceHealth(WARNING, f"{failures} ardışık başarısız kontrol var.")
    if latest_status == "fetched" and candidates == 0 and mode in {"weekly_development", "both"}:
        return SourceHealth(WARNING, "Haftalık gelişme kaynağından aday link çıkmadı.")

    last_changed = _parse_dt(last_changed_at)
    last_success = _parse_dt(last_success_at)
    reference_dt = last_changed or last_success
    if reference_dt is not None:
        age_days = (now - reference_dt).days
        if age_days >= stale_days:
            return SourceHealth(STALE, f"{age_days} gündür değişiklik görülmedi.")

    if latest_status == "fetched" and 200 <= http_status < 400:
        return SourceHealth(HEALTHY, "Son kontrol başarılı.")
    if latest_status == "fetched":
        return SourceHealth(WARNING, "Kaynak çekildi ancak HTTP durumu doğrulanamadı.")
    return SourceHealth(WARNING, "Kaynak için yeterli sağlık sinyali yok.")


def classify_coverage_completeness(
    *,
    valid_weekly_sources: int | str = 0,
    valid_benchmark_sources: int | str = 0,
    browser_required_sources: int | str = 0,
    manual_sources: int | str = 0,
    mvp_active_sources: int | str = 0,
) -> SourceHealth:
    """Classify institution-level coverage for the private-bank expansion matrix."""

    def as_int(value) -> int:
        try:
            return int(float(_clean(value) or 0))
        except Exception:
            return 0

    weekly = as_int(valid_weekly_sources)
    benchmark = as_int(valid_benchmark_sources)
    browser = as_int(browser_required_sources)
    manual = as_int(manual_sources)
    mvp = as_int(mvp_active_sources)

    if mvp > 0:
        return SourceHealth(COMPLETE, "En az bir doğrulanmış haftalık kaynak MVP akışında aktif.")
    if weekly > 0:
        return SourceHealth(PARTIAL, "Haftalık kaynak doğrulandı ancak MVP aktif değil.")
    if benchmark > 0:
        return SourceHealth(PARTIAL, "Benchmark kaynağı var; tarihli haftalık gelişme kaynağı yok.")
    if browser > 0:
        return SourceHealth(MANUAL, "Kaynak browser/JS tabanlı collector gerektiriyor.")
    if manual > 0:
        return SourceHealth(MANUAL, "Kurum manuel izleme kapsamında.")
    return SourceHealth(NO_COVERAGE, "Uygun kaynak doğrulanmadı.")
