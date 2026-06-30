from __future__ import annotations

import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

TERMS = [
    "Executive Overview",
    "Deposit Benchmark",
    "Embedded Finance Benchmark",
    "Payments POS Benchmark",
    "Compare Institutions",
    "Battlecards",
    "Source Tracker",
    "Weekly Developments Radar",
    "Review Queue",
    "Benchmark Fact Review",
    "Product Feature",
    "Product Requirement",
    "Digital SME Journey",
    "Payments & POS",
    "SME Lending",
    "SME Deposits",
    "Cash Management",
    "Strategic Relevance",
    "Source",
    "Review",
    "Save",
    "Pending",
    "Approved",
    "Rejected",
    "Medium",
    "High",
    "Low",
    "Monitor",
    "Respond",
]

SCAN_GLOBS = [
    "app.py",
    "pages/*.py",
    "data/*.csv",
    "pipeline/*.py",
    "README.md",
]

ALLOW_PATTERNS = [
    re.compile(r"https?://"),
    re.compile(r"^\s*(from|import)\s+"),
    re.compile(r"README\.md.*(python |streamlit |pip )"),
    re.compile(r"#\s*internal", re.IGNORECASE),
    re.compile(r"(ALLOWED_|CANONICAL_TRANSLATIONS|TERMS|LABELS|STATUS_LABELS|STATUS_BY_VALUE|PHRASE_TRANSLATIONS|CONTROLLED_VALUE_TRANSLATIONS)"),
    re.compile(r"(review_status|source_id|source_type|source_url|source_name|open_questions_json|confidence_level|impact_on_us|recommended_action)"),
    re.compile(r"(Product Feature|Pending|Approved|Rejected|High|Medium|Low).*[=:]"),
    re.compile(r"(Onayla|Reddet|Beklemede Bırak).*(Approved|Rejected|Pending)"),
    re.compile(r"approved_at.*Approved"),
    re.compile(r"args\.status == \"Approved\""),
]


def is_acceptable_internal(path: Path, line: str) -> bool:
    text = f"{path.name}:{line}"
    if "archive/old_pages" in str(path):
        return True
    if path.name == "check_turkish_readiness.py":
        return True
    if path.name == "summarize_recent_items.py" and re.search(r'^\s*"[^"]+":\s*"[^"]+",?\s*$', line):
        return True
    if path.name in {
        "benchmark_facts.csv",
        "benchmark_fact_review_queue.csv",
        "llm_extractions.csv",
        "review_queue.csv",
    } and any(status in line for status in ["Pending", "Approved", "Rejected", "Needs More Research"]):
        return True
    return any(pattern.search(text) or pattern.search(line) for pattern in ALLOW_PATTERNS)


def scan_file(path: Path):
    findings = []
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    except Exception:
        return findings
    for idx, line in enumerate(lines, start=1):
        for term in TERMS:
            if term in line:
                findings.append(
                    {
                        "path": path,
                        "line_no": idx,
                        "term": term,
                        "line": line.strip(),
                        "acceptable": is_acceptable_internal(path, line),
                    }
                )
    return findings


def main() -> None:
    paths = []
    for pattern in SCAN_GLOBS:
        paths.extend(ROOT_DIR.glob(pattern))
    findings = []
    for path in sorted(set(paths)):
        findings.extend(scan_file(path))

    needs_fix = [item for item in findings if not item["acceptable"]]
    acceptable = [item for item in findings if item["acceptable"]]

    print(f"remaining_english_terms: {len(findings)}")
    print(f"acceptable_internal_terms: {len(acceptable)}")
    print(f"needs_fix_terms: {len(needs_fix)}")
    if needs_fix:
        print("\nNEEDS_FIX")
        for item in needs_fix:
            rel = item["path"].relative_to(ROOT_DIR)
            print(f"{rel}:{item['line_no']} | {item['term']} | {item['line']}")
    if acceptable:
        print("\nACCEPTABLE_INTERNAL")
        for item in acceptable[:80]:
            rel = item["path"].relative_to(ROOT_DIR)
            print(f"{rel}:{item['line_no']} | {item['term']} | {item['line']}")
        if len(acceptable) > 80:
            print(f"... {len(acceptable) - 80} more acceptable internal terms")


if __name__ == "__main__":
    main()
