#!/usr/bin/env python3
"""キューバリデーションスクリプト - queue.jsonの整合性をチェック"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import (
    MAX_TEXT_LENGTH,
    check_forbidden_words,
    extract_hook,
    normalize_text,
)

# パス定義
QUEUE_PATH = PROJECT_ROOT / "queue.json"

# 必須フィールド
REQUIRED_FIELDS = ["date", "slot", "pillar", "format", "hook", "text", "status", "fingerprint"]

# 有効な値
VALID_SLOTS = ["17", "19"]
VALID_PILLARS = ["unpaid", "unitprice", "tax", "vehicle", "ops", "risk", "case"]
VALID_FORMATS = ["checklist", "template", "howto", "story", "criteria", "question"]
VALID_STATUSES = ["draft", "approved", "posted"]


def load_queue() -> list[dict]:
    """キューを読み込み"""
    if not QUEUE_PATH.exists():
        return []
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_date_format(date_str: str) -> bool:
    """日付形式をチェック（YYYY-MM-DD）"""
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    return bool(re.match(pattern, date_str))


def validate_schema(item: dict, index: int) -> list[str]:
    """スキーマをチェック"""
    errors = []

    # 必須フィールドチェック
    for field in REQUIRED_FIELDS:
        if field not in item:
            errors.append(f"[{index}] Missing required field: {field}")

    # 日付形式
    date = item.get("date", "")
    if date and not validate_date_format(date):
        errors.append(f"[{index}] Invalid date format: {date} (expected YYYY-MM-DD)")

    # スロット
    slot = item.get("slot", "")
    if slot and slot not in VALID_SLOTS:
        errors.append(f"[{index}] Invalid slot: {slot} (expected 17 or 19)")

    # ピラー
    pillar = item.get("pillar", "")
    if pillar and pillar not in VALID_PILLARS:
        errors.append(f"[{index}] Invalid pillar: {pillar}")

    # フォーマット
    format_type = item.get("format", "")
    if format_type and format_type not in VALID_FORMATS:
        errors.append(f"[{index}] Invalid format: {format_type}")

    # ステータス
    status = item.get("status", "")
    if status and status not in VALID_STATUSES:
        errors.append(f"[{index}] Invalid status: {status}")

    return errors


def validate_text_length(item: dict, index: int) -> list[str]:
    """テキスト長をチェック"""
    errors = []
    text = item.get("text", "")
    length = len(text)

    if length > MAX_TEXT_LENGTH:
        errors.append(f"[{index}] Text too long: {length} chars (max {MAX_TEXT_LENGTH})")

    if length < 10:
        errors.append(f"[{index}] Text too short: {length} chars (suspicious)")

    return errors


def validate_forbidden(item: dict, index: int) -> list[str]:
    """禁止語をチェック"""
    errors = []
    text = item.get("text", "")
    forbidden = check_forbidden_words(text)

    if forbidden:
        errors.append(f"[{index}] Forbidden words found: {forbidden}")

    return errors


def validate_duplicates(queue: list[dict]) -> list[str]:
    """重複をチェック"""
    errors = []

    # fingerprint重複
    fingerprints = [item.get("fingerprint") for item in queue if item.get("fingerprint")]
    fp_counter = Counter(fingerprints)
    for fp, count in fp_counter.items():
        if count > 1:
            indices = [i for i, item in enumerate(queue) if item.get("fingerprint") == fp]
            errors.append(f"Duplicate fingerprint at indices {indices}: {fp[:16]}...")

    # 同日同スロット重複（approved/draftのみ）
    date_slot_pairs = []
    for i, item in enumerate(queue):
        if item.get("status") in ["approved", "draft"]:
            pair = (item.get("date"), item.get("slot"))
            date_slot_pairs.append((i, pair))

    pair_counter = Counter([p[1] for p in date_slot_pairs])
    for pair, count in pair_counter.items():
        if count > 1:
            indices = [p[0] for p in date_slot_pairs if p[1] == pair]
            errors.append(f"Duplicate date/slot at indices {indices}: {pair}")

    return errors


def validate_hook_duplicates(queue: list[dict]) -> list[str]:
    """連続するhook被りをチェック（警告レベル）"""
    warnings = []

    hooks = [(i, normalize_text(extract_hook(item))) for i, item in enumerate(queue)]
    hook_counter = Counter([h[1] for h in hooks])

    for hook, count in hook_counter.items():
        if count > 3 and hook:
            indices = [h[0] for h in hooks if h[1] == hook]
            warnings.append(f"Hook appears {count} times at indices {indices[:5]}...: {hook[:30]}...")

    return warnings


def main():
    print("Validating queue.json...")

    queue = load_queue()

    if not queue:
        print("Queue is empty")
        sys.exit(0)

    print(f"Found {len(queue)} items")

    all_errors = []
    all_warnings = []

    # 各アイテムのバリデーション
    for i, item in enumerate(queue):
        all_errors.extend(validate_schema(item, i))
        all_errors.extend(validate_text_length(item, i))
        all_errors.extend(validate_forbidden(item, i))

    # キュー全体のバリデーション
    all_errors.extend(validate_duplicates(queue))
    all_warnings.extend(validate_hook_duplicates(queue))

    # 結果表示
    if all_warnings:
        print("\n⚠️  Warnings:")
        for warning in all_warnings:
            print(f"  {warning}")

    if all_errors:
        print("\n❌ Errors:")
        for error in all_errors:
            print(f"  {error}")
        print(f"\nValidation FAILED with {len(all_errors)} errors")
        sys.exit(1)
    else:
        print("\n✅ Validation PASSED")

        # 統計情報
        statuses = Counter([item.get("status") for item in queue])
        print(f"\nStatus breakdown:")
        for status, count in statuses.items():
            print(f"  {status}: {count}")

        sys.exit(0)


if __name__ == "__main__":
    main()
