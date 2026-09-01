from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
OFFERS_PATH = DATA_DIR / "new_customer_offers.csv"
TIMEZONE = ZoneInfo("Europe/Istanbul")

CHECK_COLUMNS = [
    "last_http_status",
    "last_check_status",
    "last_check_error",
    "last_check_run_id",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.7,en;q=0.6",
}


@dataclass
class CheckResult:
    offer_id: str
    institution_name: str
    offer_title: str
    url: str
    status_code: str
    check_status: str
    error: str

    @property
    def successful(self) -> bool:
        return self.check_status == "Erişildi"


def today_istanbul() -> datetime:
    return datetime.now(TIMEZONE)


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    return pd.to_datetime(str(value or "").strip(), errors="coerce")


def run_id_default() -> str:
    return "new_customer_daily_" + today_istanbul().strftime("%Y%m%d_%H%M%S")


def read_offers() -> pd.DataFrame:
    if not OFFERS_PATH.exists():
        raise FileNotFoundError(f"{OFFERS_PATH.relative_to(ROOT_DIR)} bulunamadı.")
    df = pd.read_csv(OFFERS_PATH, dtype=str, encoding="utf-8-sig").fillna("")
    for column in CHECK_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df


def source_status(session: requests.Session, url: str, timeout: int) -> tuple[str, str, str]:
    if not url:
        return "", "Hata", "Kaynak URL boş."
    try:
        response = session.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        code = str(response.status_code)
        if 200 <= response.status_code < 400:
            return code, "Erişildi", ""
        return code, "Hata", f"HTTP {response.status_code}"
    except requests.Timeout:
        return "", "Hata", f"Timeout: {timeout}s"
    except requests.RequestException as exc:
        return "", "Hata", str(exc)[:300]


def refreshed_status(current_status: str, valid_until: object, today: pd.Timestamp) -> str:
    current_status = str(current_status or "").strip() or "Belirsiz"
    expiry = parse_date(valid_until)
    if pd.isna(expiry):
        return current_status
    if expiry.normalize() < today:
        return "Süresi doldu"
    if current_status == "Süresi doldu":
        return "Aktif"
    return current_status


def write_report(run_id: str, results: list[CheckResult], expired_updates: int) -> Path:
    path = DATA_DIR / f"weekly_operations_report_{run_id}.md"
    total = len(results)
    successful = sum(1 for result in results if result.successful)
    failed = total - successful
    lines = [
        "# Yeni Müşteri Teklifleri Günlük Kontrol",
        "",
        "## Özet",
        "",
        f"- run ID: `{run_id}`",
        f"- kontrol zamanı: {today_istanbul().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- kontrol edilen teklif: {total}",
        f"- erişilen kaynak: {successful}",
        f"- başarısız kaynak: {failed}",
        f"- süresi doldu olarak güncellenen teklif: {expired_updates}",
        "",
        "## Kaynak Sonuçları",
        "",
    ]
    if not results:
        lines.append("- Kontrol edilecek teklif bulunamadı.")
    for result in results:
        error = f" | hata: {result.error}" if result.error else ""
        lines.append(
            f"- {result.offer_id} | {result.institution_name} | {result.check_status} | "
            f"HTTP {result.status_code or '-'} | {result.offer_title}{error}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Yeni müşteri teklif kaynaklarını günlük kontrol eder.")
    parser.add_argument("--run-id", default=run_id_default())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    offers = read_offers()
    candidates = offers.copy()
    if args.limit is not None:
        candidates = candidates.head(args.limit)

    today = pd.Timestamp(today_istanbul().date())
    today_label = today.strftime("%Y-%m-%d")
    results: list[CheckResult] = []
    expired_updates = 0
    session = requests.Session()

    print(f"Run ID: {args.run_id}")
    print(f"Total offers loaded: {len(offers)}")
    print(f"Offers selected for daily check: {len(candidates)}")
    print(f"Dry run: {args.dry_run}")

    for index, row in candidates.iterrows():
        offer_id = str(row.get("offer_id", "")).strip()
        institution_name = str(row.get("institution_name", "")).strip()
        offer_title = str(row.get("offer_title", "")).strip()
        url = str(row.get("source_url", "")).strip()
        print(f"Checking {offer_id} | {institution_name} | {url}")

        if args.dry_run:
            status_code, check_status, error = "", "Dry Run", ""
        else:
            status_code, check_status, error = source_status(session, url, args.timeout)
            previous_status = str(offers.at[index, "status"]).strip()
            next_status = refreshed_status(previous_status, offers.at[index, "valid_until"], today)
            if next_status != previous_status:
                expired_updates += 1
                offers.at[index, "status"] = next_status
            offers.at[index, "last_checked"] = today_label
            offers.at[index, "last_http_status"] = status_code
            offers.at[index, "last_check_status"] = check_status
            offers.at[index, "last_check_error"] = error
            offers.at[index, "last_check_run_id"] = args.run_id

        results.append(
            CheckResult(
                offer_id=offer_id,
                institution_name=institution_name,
                offer_title=offer_title,
                url=url,
                status_code=status_code,
                check_status=check_status,
                error=error,
            )
        )

    if not args.dry_run:
        offers.to_csv(OFFERS_PATH, index=False, encoding="utf-8-sig")
        report_path = write_report(args.run_id, results, expired_updates)
    else:
        report_path = Path("")

    successful = sum(1 for result in results if result.successful)
    failed = len(results) - successful if not args.dry_run else 0
    print("\nNew customer offer check complete")
    print(f"offers_loaded: {len(offers)}")
    print(f"offers_checked: {len(results)}")
    print(f"sources_succeeded: {successful}")
    print(f"sources_failed: {failed}")
    print(f"expired_status_updates: {expired_updates}")
    print(f"report_path: {report_path.relative_to(ROOT_DIR) if report_path else '-'}")


if __name__ == "__main__":
    main()
