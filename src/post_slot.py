#!/usr/bin/env python3
"""X自動投稿スクリプト - スロット指定で投稿を実行"""

import argparse
import os
import sys
from pathlib import Path

import requests
from requests_oauthlib import OAuth1

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import (
    PostAPIError,
    PostValidationError,
    calculate_fingerprint,
    check_fingerprint_duplicate,
    check_forbidden_words,
    check_hook_duplicate,
    extract_hook,
    load_queue,
    log_error,
    log_info,
    log_warning,
    save_queue,
    today_jst,
    utc_iso,
    validate_text_length,
)

# X API設定
X_API_BASE_URL = "https://api.x.com"
X_TWEET_ENDPOINT = f"{X_API_BASE_URL}/2/tweets"

# キューファイルパス
QUEUE_PATH = PROJECT_ROOT / "queue.json"


def get_oauth1_session() -> OAuth1:
    """OAuth1認証セッションを取得"""
    api_key = os.environ.get("X_API_KEY")
    api_key_secret = os.environ.get("X_API_KEY_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_key_secret, access_token, access_token_secret]):
        raise PostAPIError(
            "Missing X API credentials. "
            "Set X_API_KEY, X_API_KEY_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET"
        )

    return OAuth1(
        api_key,
        client_secret=api_key_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
    )


def find_target_post(queue: list[dict], slot: str) -> dict | None:
    """当日スロットで status=approved の最初の投稿を探す"""
    today = today_jst()
    for item in queue:
        if (
            item.get("date") == today
            and item.get("slot") == slot
            and item.get("status") == "approved"
        ):
            return item
    return None


def validate_post(item: dict, queue: list[dict]) -> None:
    """投稿の妥当性を検証"""
    text = item.get("text", "")

    # 文字数チェック
    is_valid, length = validate_text_length(text)
    if not is_valid:
        raise PostValidationError(f"Text too long: {length} chars (max 260)")

    # 禁止語チェック
    forbidden = check_forbidden_words(text)
    if forbidden:
        raise PostValidationError(f"Forbidden words found: {forbidden}")

    # fingerprint重複チェック
    fingerprint = item.get("fingerprint") or calculate_fingerprint(text)
    if check_fingerprint_duplicate(fingerprint, queue, limit=50):
        raise PostValidationError(f"Duplicate fingerprint detected")

    # hook重複チェック
    hook = extract_hook(item)
    if check_hook_duplicate(hook, queue, limit=14):
        raise PostValidationError(f"Duplicate hook detected: {hook[:30]}...")


def post_tweet(text: str, auth: OAuth1) -> str:
    """ツイートを投稿し、tweet_idを返す"""
    payload = {"text": text}
    headers = {"Content-Type": "application/json"}

    response = requests.post(
        X_TWEET_ENDPOINT,
        json=payload,
        auth=auth,
        headers=headers,
    )

    if response.status_code == 201:
        data = response.json()
        tweet_id = data.get("data", {}).get("id")
        return tweet_id
    else:
        raise PostAPIError(
            f"Failed to post tweet: {response.status_code} - {response.text}"
        )


def update_posted_item(item: dict, tweet_id: str) -> None:
    """投稿後のアイテムを更新"""
    item["status"] = "posted"
    item["tweet_id"] = tweet_id
    item["posted_at_utc"] = utc_iso()


def main():
    parser = argparse.ArgumentParser(description="Post to X from queue")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be posted without actually posting",
    )
    args = parser.parse_args()

    # スロット取得
    slot = os.environ.get("SLOT", "17")
    if slot not in ("17", "19"):
        log_error(f"Invalid SLOT: {slot}. Must be '17' or '19'")
        sys.exit(1)

    log_info(f"Starting post_slot for slot={slot}, date={today_jst()}")

    # キュー読み込み
    queue = load_queue(QUEUE_PATH)
    if not queue:
        log_warning("Queue is empty")
        sys.exit(0)

    # 対象投稿を検索
    target = find_target_post(queue, slot)
    if not target:
        log_info(f"No approved post found for today ({today_jst()}) slot {slot}")
        sys.exit(0)

    log_info(f"Found target post: {target.get('hook', target.get('text', '')[:30])}")

    # バリデーション
    try:
        validate_post(target, queue)
        log_info("Validation passed")
    except PostValidationError as e:
        log_error(f"Validation failed: {e}")
        sys.exit(1)

    # dry-runモード
    if args.dry_run:
        log_info("=== DRY RUN MODE ===")
        log_info(f"Date: {target.get('date')}")
        log_info(f"Slot: {target.get('slot')}")
        log_info(f"Pillar: {target.get('pillar')}")
        log_info(f"Format: {target.get('format')}")
        log_info(f"Hook: {target.get('hook')}")
        log_info(f"Text ({len(target.get('text', ''))} chars):")
        print("-" * 40)
        print(target.get("text", ""))
        print("-" * 40)
        log_info("Would post this tweet (dry-run, not actually posting)")
        sys.exit(0)

    # 実際に投稿
    try:
        auth = get_oauth1_session()
        tweet_id = post_tweet(target.get("text", ""), auth)
        log_info(f"Successfully posted tweet: {tweet_id}")

        # アイテム更新
        update_posted_item(target, tweet_id)

        # キュー保存
        save_queue(QUEUE_PATH, queue)
        log_info("Queue updated and saved")

    except PostAPIError as e:
        log_error(f"API error: {e}")
        sys.exit(1)
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
