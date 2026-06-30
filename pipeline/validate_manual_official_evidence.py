from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from utils.mastercard_blocked_mode import (
    DATA_DIR,
    MANUAL_INBOX_COLUMNS,
    MANUAL_VERIFIED_COLUMNS,
    clean,
    existing_manual_duplicate_keys,
    passes_manual_official_evidence_gate,
    read_csv,
    write_csv,
)


INBOX_PATH = DATA_DIR / "mastercard_manual_official_evidence_inbox.csv"
VERIFIED_PATH = DATA_DIR / "mastercard_manual_verified_candidates.csv"
RECENT_ITEMS_PATH = DATA_DIR / "recent_items.csv"


def ensure_files() -> None:
    if not INBOX_PATH.exists():
        write_csv(INBOX_PATH, pd.DataFrame(columns=MANUAL_INBOX_COLUMNS), MANUAL_INBOX_COLUMNS)
    if not VERIFIED_PATH.exists():
        write_csv(VERIFIED_PATH, pd.DataFrame(columns=MANUAL_VERIFIED_COLUMNS), MANUAL_VERIFIED_COLUMNS)


def update_inbox_row(inbox: pd.DataFrame, idx: int, passed: bool, reason: str) -> pd.DataFrame:
    output = inbox.copy()
    if "intake_status" not in output.columns:
        output["intake_status"] = ""
    if "validation_error" not in output.columns:
        output["validation_error"] = ""
    output.loc[idx, "intake_status"] = "Verified" if passed else "Rejected"
    output.loc[idx, "validation_error"] = reason
    return output


def merge_verified(existing: pd.DataFrame, rows: list[dict[str, str]]) -> tuple[pd.DataFrame, int, int]:
    if not rows:
        return existing, 0, 0
    output = existing.copy()
    added = 0
    updated = 0
    for row in rows:
        intake_id = clean(row.get("intake_id"))
        if "intake_id" in output.columns and intake_id:
            matches = output.index[output["intake_id"].astype(str).eq(intake_id)].tolist()
        else:
            matches = []
        if matches:
            for column, value in row.items():
                output.loc[matches[0], column] = value
            updated += 1
        else:
            output = pd.concat([output, pd.DataFrame([row])], ignore_index=True)
            added += 1
    return output, added, updated


def validate(args: argparse.Namespace) -> dict[str, int]:
    ensure_files()
    inbox = read_csv(INBOX_PATH)
    verified = read_csv(VERIFIED_PATH)
    recent_items = read_csv(RECENT_ITEMS_PATH)
    if inbox.empty:
        return {"inbox_rows": 0, "checked": 0, "verified": 0, "rejected": 0, "written": 0, "updated": 0}

    for column in MANUAL_INBOX_COLUMNS:
        if column not in inbox.columns:
            inbox[column] = ""
    if args.institution:
        inbox = inbox[inbox["institution_name"].astype(str).eq(args.institution)].copy()
    if args.intake_id:
        inbox = inbox[inbox["intake_id"].astype(str).eq(args.intake_id)].copy()
    inbox = inbox[inbox["intake_status"].astype(str).isin(["", "New", "Validation Required", "Rejected", "Verified"])].copy()
    if args.limit:
        inbox = inbox.head(args.limit)

    existing_urls, existing_titles = existing_manual_duplicate_keys(verified, recent_items)
    verified_rows: list[dict[str, str]] = []
    checked = rejected = passed_count = 0
    full_inbox = read_csv(INBOX_PATH)

    for idx, row in inbox.iterrows():
        checked += 1
        passed, reason, candidate = passes_manual_official_evidence_gate(row, existing_urls, existing_titles)
        if args.debug:
            print(f"{row.get('intake_id', '') or idx}: passed={passed} reason={reason} title={row.get('proposed_title', '')}")
        if passed:
            passed_count += 1
            verified_rows.append(candidate)
            existing_urls.add(candidate["canonical_url"])
            existing_titles.add(candidate["title"].casefold())
        else:
            rejected += 1
        if not args.dry_run and idx in full_inbox.index:
            full_inbox = update_inbox_row(full_inbox, idx, passed, reason)

    added = updated = 0
    if not args.dry_run:
        merged, added, updated = merge_verified(verified, verified_rows)
        write_csv(VERIFIED_PATH, merged, MANUAL_VERIFIED_COLUMNS)
        write_csv(INBOX_PATH, full_inbox, MANUAL_INBOX_COLUMNS)

    return {
        "inbox_rows": len(inbox),
        "checked": checked,
        "verified": passed_count,
        "rejected": rejected,
        "written": added,
        "updated": updated,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate analyst-supplied official Mastercard evidence without calling Claude.")
    parser.add_argument("--institution", default="Mastercard")
    parser.add_argument("--intake-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    result = validate(args)
    print("Manual official evidence validation complete")
    for key, value in result.items():
        print(f"{key}: {value}")
    print(f"inbox: {INBOX_PATH.relative_to(ROOT_DIR)}")
    print(f"verified_candidates: {VERIFIED_PATH.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
