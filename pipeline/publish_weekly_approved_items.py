from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

from publish_approved_clusters_to_weekly_developments import publish_approved_clusters
from publish_management_awareness_to_weekly_developments import publish_approved_management_awareness
from publish_recent_items_to_weekly_developments import publish_approved_recent_items


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def write_report(run_id: str, item_count: int, cluster_count: int, awareness_count: int) -> Path:
    path = DATA_DIR / f"weekly_publish_report_{run_id}.md"
    total = item_count + cluster_count + awareness_count
    path.write_text(
        "\n".join(
            [
                "# Weekly Approved Items Publish Report",
                "",
                f"- Run ID: `{run_id}`",
                f"- Published individual items: {item_count}",
                f"- Published clusters: {cluster_count}",
                f"- Published management-awareness items: {awareness_count}",
                f"- Total published rows: {total}",
                "",
                "Only approved, unpublished rows were considered. Weekly discovery is intentionally not part of this command.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish approved weekly radar items after analyst review.")
    parser.add_argument("--run-id", default=f"publish_{now_stamp()}", help="Optional publish run id.")
    args = parser.parse_args()

    item_count = publish_approved_recent_items()
    cluster_count = publish_approved_clusters()
    awareness_count = publish_approved_management_awareness()
    report = write_report(args.run_id, item_count, cluster_count, awareness_count)

    print(f"published individual items: {item_count}")
    print(f"published clusters: {cluster_count}")
    print(f"published management-awareness items: {awareness_count}")
    print(f"report: {report.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
