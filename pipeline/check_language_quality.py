from __future__ import annotations

from datetime import datetime
from pathlib import Path

from run_fresh_four_bank_mvp import DATA_DIR, ROOT_DIR, build_language_quality_report


def main() -> None:
    report_path = DATA_DIR / f"language_quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    build_language_quality_report(report_path)
    print(f"Language quality report: {report_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
