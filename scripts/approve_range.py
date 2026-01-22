#!/usr/bin/env python3
"""期間指定で投稿を承認するスクリプト"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# パス定義
QUEUE_PATH = PROJECT_ROOT / "queue.json"


def load_queue() -> list[dict]:
    """キューを読み込み"""
    if not QUEUE_PATH.exists():
        return []
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue: list[dict]) -> None:
    """キューを保存"""
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def parse_date(date_str: str) -> datetime:
    """日付文字列をパース"""
    return datetime.strptime(date_str, "%Y-%m-%d")


def is_in_range(date_str: str, from_date: datetime, to_date: datetime) -> bool:
    """日付が範囲内かチェック"""
    try:
        date = parse_date(date_str)
        return from_date <= date <= to_date
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(description="Approve posts in date range")
    parser.add_argument(
        "--from",
        dest="from_date",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be approved without making changes",
    )
    args = parser.parse_args()

    # 日付パース
    try:
        from_date = parse_date(args.from_date)
        to_date = parse_date(args.to_date)
    except ValueError as e:
        print(f"Invalid date format: {e}")
        sys.exit(1)

    if from_date > to_date:
        print("Error: --from date must be before or equal to --to date")
        sys.exit(1)

    print(f"Approving posts from {args.from_date} to {args.to_date}")

    # キュー読み込み
    queue = load_queue()
    if not queue:
        print("Queue is empty")
        sys.exit(0)

    # 対象を検索・更新
    approved_count = 0
    for item in queue:
        date_str = item.get("date", "")
        status = item.get("status", "")

        if status == "draft" and is_in_range(date_str, from_date, to_date):
            if args.dry_run:
                print(f"  Would approve: {date_str} slot={item.get('slot')} hook={item.get('hook', '')[:30]}...")
            else:
                item["status"] = "approved"
            approved_count += 1

    # 結果
    if args.dry_run:
        print(f"\n[DRY RUN] Would approve {approved_count} posts")
    else:
        if approved_count > 0:
            save_queue(queue)
            print(f"\n✅ Approved {approved_count} posts")
        else:
            print("\nNo posts to approve in the specified range")


if __name__ == "__main__":
    main()
