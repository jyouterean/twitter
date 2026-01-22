#!/usr/bin/env python3
"""投稿キュー生成スクリプト - テンプレート×辞書で投稿を自動生成"""

import argparse
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import calculate_fingerprint, normalize_text

# パス定義
CONTENT_DIR = PROJECT_ROOT / "content"
TEMPLATES_PATH = CONTENT_DIR / "templates.json"
LEXICON_PATH = CONTENT_DIR / "lexicon.json"
QUEUE_PATH = PROJECT_ROOT / "queue.json"

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# スロットごとのフォーマット優先度
SLOT_FORMATS = {
    "17": ["checklist", "template", "howto"],
    "19": ["story", "criteria", "question"],
}


def load_templates() -> dict:
    """テンプレートを読み込み"""
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_lexicon() -> dict:
    """辞書を読み込み"""
    with open(LEXICON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_queue() -> list[dict]:
    """既存のキューを読み込み"""
    if QUEUE_PATH.exists():
        with open(QUEUE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_queue(queue: list[dict]) -> None:
    """キューを保存"""
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def generate_hook(template: dict, pillar_data: dict, common: dict) -> str:
    """フックを生成"""
    hook_patterns = template.get("hook_patterns", [])
    if not hook_patterns:
        return ""

    pattern = random.choice(hook_patterns)

    # 変数置換
    replacements = {
        "{pillar_topic}": pillar_data.get("topic", ""),
        "{count}": random.choice(common.get("counts", ["5"])),
        "{action}": random.choice(pillar_data.get("actions", ["対応"])),
        "{option_a}": pillar_data.get("options", {}).get("option_a", "A"),
        "{option_b}": pillar_data.get("options", {}).get("option_b", "B"),
    }

    for key, value in replacements.items():
        pattern = pattern.replace(key, value)

    return pattern


def generate_items(template: dict, pillar_data: dict, item_type: str) -> str:
    """チェックリストやステップを生成"""
    items_format = template.get(f"{item_type}_format", "bullet")
    item_count = template.get(f"{item_type}_count", [4])
    count = random.choice(item_count) if isinstance(item_count, list) else item_count

    # アイテムソースを決定
    if item_type == "items":
        source_keys = ["check_items", "cautions"]
    elif item_type == "steps":
        source_keys = ["actions", "check_items"]
    else:
        source_keys = ["check_items"]

    all_items = []
    for key in source_keys:
        all_items.extend(pillar_data.get(key, []))

    if len(all_items) < count:
        count = len(all_items)

    selected = random.sample(all_items, count) if all_items else []

    # フォーマット
    if items_format == "checkbox":
        return "\n".join([f"☑ {item}" for item in selected])
    elif items_format == "numbered":
        return "\n".join([f"①②③④⑤⑥"[i] + f" {item}" for i, item in enumerate(selected)])
    else:  # bullet
        return "\n".join([f"・{item}" for item in selected])


def generate_closing(template: dict) -> str:
    """クロージングを生成"""
    closing_patterns = template.get("closing_patterns", [])
    if closing_patterns:
        return random.choice(closing_patterns)
    return ""


def generate_story_body(pillar_data: dict) -> str:
    """ストーリー本文を生成"""
    story_elements = pillar_data.get("story_elements", [])
    examples = pillar_data.get("examples", [])

    parts = []
    if story_elements:
        parts.append(random.choice(story_elements))
    if examples:
        parts.append(random.choice(examples))

    return "\n".join(parts) if parts else "実際にあった話です。"


def generate_criteria_body(pillar_data: dict) -> str:
    """判断基準本文を生成"""
    cautions = pillar_data.get("cautions", [])
    check_items = pillar_data.get("check_items", [])

    items = random.sample(cautions + check_items, min(3, len(cautions) + len(check_items)))
    return "\n".join([f"・{item}" for item in items])


def generate_options(pillar_data: dict) -> str:
    """選択肢を生成"""
    options = pillar_data.get("options", {})
    actions = pillar_data.get("actions", [])

    if options:
        return f"A: {options.get('option_a', 'A')}\nB: {options.get('option_b', 'B')}"
    elif len(actions) >= 2:
        selected = random.sample(actions, 2)
        return f"A: {selected[0]}\nB: {selected[1]}"
    return "A: する\nB: しない"


def generate_lesson(template: dict) -> str:
    """教訓を生成"""
    lesson_patterns = template.get("lesson_patterns", [])
    if lesson_patterns:
        return random.choice(lesson_patterns)
    return ""


def generate_post_text(template: dict, pillar_data: dict, common: dict) -> tuple[str, str]:
    """投稿テキストを生成し、(hook, full_text)を返す"""
    structure = template.get("structure", "{hook}")
    format_type = template.get("format", "")

    hook = generate_hook(template, pillar_data, common)

    # 構造に応じた本文生成
    parts = {
        "{hook}": hook,
        "{closing}": generate_closing(template),
        "{items}": generate_items(template, pillar_data, "items"),
        "{steps}": generate_items(template, pillar_data, "steps"),
        "{template_body}": generate_story_body(pillar_data),
        "{comparison}": generate_criteria_body(pillar_data),
        "{story_body}": generate_story_body(pillar_data),
        "{lesson}": generate_lesson(template),
        "{criteria_body}": generate_criteria_body(pillar_data),
        "{options}": generate_options(pillar_data),
        "{context}": generate_closing(template),
        "{insight}": generate_story_body(pillar_data),
        "{case_description}": generate_story_body(pillar_data),
        "{advice}": template.get("advice_patterns", ["専門家に相談を"])[0] if template.get("advice_patterns") else "専門家に相談を",
    }

    text = structure
    for placeholder, content in parts.items():
        text = text.replace(placeholder, content)

    return hook, normalize_text(text)


def generate_hashtags(lexicon: dict, pillar_key: str) -> str:
    """ハッシュタグを生成"""
    hashtags_config = lexicon.get("hashtags", {})
    required = hashtags_config.get("required", [])
    pillar_tags = hashtags_config.get("pillar", {}).get(pillar_key, [])

    # 必須 + pillar別（1つランダム選択）
    tags = required.copy()
    if pillar_tags:
        tags.append(random.choice(pillar_tags))

    return " ".join(tags)


def generate_single_post(
    date: str,
    slot: str,
    templates: dict,
    lexicon: dict,
    used_hooks: set,
) -> dict | None:
    """単一の投稿を生成"""
    slot_templates = templates.get("templates", {}).get(slot, [])
    pillars = lexicon.get("pillars", {})
    common = lexicon.get("common", {})

    if not slot_templates or not pillars:
        return None

    # ランダムにテンプレートとpillarを選択
    template = random.choice(slot_templates)
    pillar_key = random.choice(list(pillars.keys()))
    pillar_data = pillars[pillar_key]

    # 投稿生成（hook被り回避のため最大5回リトライ）
    for _ in range(5):
        hook, text = generate_post_text(template, pillar_data, common)
        normalized_hook = normalize_text(hook)

        if normalized_hook not in used_hooks:
            used_hooks.add(normalized_hook)
            break
    else:
        # リトライ超過時も生成は続行
        pass

    # ハッシュタグを追加
    hashtags = generate_hashtags(lexicon, pillar_key)
    if hashtags:
        text = f"{text}\n\n{hashtags}"

    fingerprint = calculate_fingerprint(text)

    return {
        "date": date,
        "slot": slot,
        "pillar": pillar_key,
        "format": template.get("format", ""),
        "hook": hook,
        "text": text,
        "status": "draft",
        "fingerprint": fingerprint,
        "tweet_id": None,
        "posted_at_utc": None,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate post queue")
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD), defaults to today JST",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to generate (default: 30)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing queue instead of replacing",
    )
    args = parser.parse_args()

    # シード設定
    if args.seed is not None:
        random.seed(args.seed)

    # 開始日
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=JST)
    else:
        start_date = datetime.now(JST)

    # テンプレートと辞書を読み込み
    templates = load_templates()
    lexicon = load_lexicon()

    # 既存キュー（append時のhook被りチェック用）
    existing_queue = load_existing_queue() if args.append else []
    used_hooks = set()
    for item in existing_queue:
        if item.get("hook"):
            used_hooks.add(normalize_text(item["hook"]))

    # 生成
    new_posts = []
    for day_offset in range(args.days):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")

        for slot in ["17", "19"]:
            post = generate_single_post(
                date_str, slot, templates, lexicon, used_hooks
            )
            if post:
                new_posts.append(post)
                print(f"Generated: {date_str} slot={slot} hook={post['hook'][:30]}...")

    # 保存
    if args.append:
        final_queue = existing_queue + new_posts
    else:
        final_queue = new_posts

    save_queue(final_queue)
    print(f"\nGenerated {len(new_posts)} posts, saved to {QUEUE_PATH}")


if __name__ == "__main__":
    main()
