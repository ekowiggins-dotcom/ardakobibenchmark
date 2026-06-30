from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RECENT_DEVELOPMENT_START_DATE = "2026-05-01"
HIGH_ENOUGH_CONFIDENCE = {"Yüksek", "Orta"}


def load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")


def bool_from_env(name: str, default: bool = False) -> bool:
    load_env()
    raw = os.getenv(name, "")
    if not raw:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "evet", "y"}


def resolve_start_date(cli_start_date: str | None = None) -> str:
    load_env()
    raw = (cli_start_date or os.getenv("RECENT_DEVELOPMENT_START_DATE") or DEFAULT_RECENT_DEVELOPMENT_START_DATE).strip()
    parsed = pd.to_datetime(raw, errors="coerce")
    if pd.isna(parsed):
        return DEFAULT_RECENT_DEVELOPMENT_START_DATE
    return parsed.date().isoformat()


def _clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _first_present(row, columns: list[str]) -> tuple[str, str]:
    for column in columns:
        value = _clean(row.get(column, ""))
        if value:
            return column, value
    return "", ""


def evaluate_recency(
    row,
    start_date: str | date,
    allow_undated: bool = False,
    allow_low_confidence: bool = False,
    allow_end_date_recency: bool = False,
) -> dict[str, object]:
    cutoff = pd.to_datetime(start_date, errors="coerce")
    if pd.isna(cutoff):
        cutoff = pd.to_datetime(DEFAULT_RECENT_DEVELOPMENT_START_DATE)
    cutoff_date = cutoff.date()

    confidence = _clean(row.get("date_confidence", "")) or "Yok"
    active_campaign = False
    active_campaign_reason = ""
    basis_column, normalized = _first_present(
        row,
        ["publication_date", "announcement_date", "campaign_start_date", "recency_basis_date", "normalized_item_date"],
    )
    campaign_end_date = _clean(row.get("campaign_end_date", ""))
    if (
        basis_column == "recency_basis_date"
        and campaign_end_date
        and normalized == campaign_end_date
        and not _clean(row.get("publication_date", ""))
        and not _clean(row.get("announcement_date", ""))
        and not _clean(row.get("campaign_start_date", ""))
    ):
        basis_column = "campaign_end_date"

    if not normalized and campaign_end_date:
        basis_column = "campaign_end_date"
        normalized = campaign_end_date

    if not normalized:
        if allow_undated:
            return {
                "is_recent": True,
                "recency_reason": "Tarih yok; manuel izinle geçirildi",
                "recency_cutoff": cutoff_date.isoformat(),
                "recency_basis_date": "",
                "recency_basis_reason": "Tarih yok; manuel izinle geçirildi.",
                "is_active_campaign": False,
                "active_campaign_reason": "",
            }
        return {
            "is_recent": False,
            "recency_reason": "Tarih yok; varsayılan kapıdan geçmedi",
            "recency_cutoff": cutoff_date.isoformat(),
            "recency_basis_date": "",
            "recency_basis_reason": "Tarih yok; varsayılan kapıdan geçmedi.",
            "is_active_campaign": False,
            "active_campaign_reason": "",
        }

    item_date = pd.to_datetime(normalized, errors="coerce")
    if pd.isna(item_date):
        return {
            "is_recent": False,
            "recency_reason": "Tarih ayrıştırılamadı",
            "recency_cutoff": cutoff_date.isoformat(),
            "recency_basis_date": normalized,
            "recency_basis_reason": "Tarih ayrıştırılamadı.",
            "is_active_campaign": False,
            "active_campaign_reason": "",
        }

    if confidence not in HIGH_ENOUGH_CONFIDENCE and not allow_low_confidence:
        return {
            "is_recent": False,
            "recency_reason": f"Düşük tarih güveni: {confidence}",
            "recency_cutoff": cutoff_date.isoformat(),
            "recency_basis_date": item_date.date().isoformat(),
            "recency_basis_reason": f"Tarih bulundu ancak güven seviyesi düşük: {confidence}.",
            "is_active_campaign": False,
            "active_campaign_reason": "",
        }

    if basis_column == "campaign_end_date" and not allow_end_date_recency:
        return {
            "is_recent": False,
            "recency_reason": "Sadece kampanya bitiş tarihi bulundu; yeni gelişme kanıtı değil",
            "recency_cutoff": cutoff_date.isoformat(),
            "recency_basis_date": item_date.date().isoformat(),
            "recency_basis_reason": "Sadece kampanya bitiş tarihi bulundu; varsayılan recency kanıtı sayılmadı.",
            "is_active_campaign": item_date.date() >= cutoff_date,
            "active_campaign_reason": "Kampanya bitiş tarihi kesim tarihinden sonra; aktif eski kampanya olabilir.",
        }

    if item_date.date() < cutoff_date:
        end_date = pd.to_datetime(campaign_end_date, errors="coerce")
        if pd.notna(end_date) and end_date.date() >= cutoff_date:
            active_campaign = True
            active_campaign_reason = "Recency baz tarihi eski; kampanya bitiş tarihi kesim tarihinden sonra görünüyor."
        return {
            "is_recent": False,
            "recency_reason": f"Kesim tarihinden eski: {item_date.date().isoformat()} < {cutoff_date.isoformat()}",
            "recency_cutoff": cutoff_date.isoformat(),
            "recency_basis_date": item_date.date().isoformat(),
            "recency_basis_reason": _basis_reason_for_column(basis_column),
            "is_active_campaign": active_campaign,
            "active_campaign_reason": active_campaign_reason,
        }

    if basis_column == "campaign_end_date" and allow_end_date_recency:
        return {
            "is_recent": True,
            "recency_reason": "Sadece kampanya bitiş tarihi bulundu; manuel izinle geçirildi",
            "recency_cutoff": cutoff_date.isoformat(),
            "recency_basis_date": item_date.date().isoformat(),
            "recency_basis_reason": "Sadece kampanya bitiş tarihi bulundu; manuel izinle geçirildi.",
            "is_active_campaign": True,
            "active_campaign_reason": "Kampanya bitiş tarihi kesim tarihinden sonra.",
        }

    return {
        "is_recent": True,
        "recency_reason": f"Kesim tarihi ve tarih güveni uygun: {item_date.date().isoformat()}",
        "recency_cutoff": cutoff_date.isoformat(),
        "recency_basis_date": item_date.date().isoformat(),
        "recency_basis_reason": _basis_reason_for_column(basis_column),
        "is_active_campaign": bool(campaign_end_date),
        "active_campaign_reason": "Kampanya tarih aralığı bulundu." if campaign_end_date else "",
    }


def _basis_reason_for_column(column: str) -> str:
    return {
        "publication_date": "Yayın tarihi bulundu; recency için kullanıldı.",
        "announcement_date": "Duyuru/basın tarihi bulundu; recency için kullanıldı.",
        "campaign_start_date": "Kampanya başlangıç tarihi bulundu; recency için kullanıldı.",
        "recency_basis_date": "Recency basis date alanı kullanıldı.",
        "normalized_item_date": "Eski normalized_item_date alanı kullanıldı.",
        "campaign_end_date": "Sadece kampanya bitiş tarihi bulundu.",
    }.get(column, "Recency için bulunan tarih kullanıldı.")
