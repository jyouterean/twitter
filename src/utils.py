"""X自動投稿ボット用ユーティリティ"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# タイムゾーン定義
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# 禁止語リスト（rules.mdと同期）
FORBIDDEN_WORDS = [
    # 収益・保証系
    "必ず稼げる",
    "保証",
    "確実に",
    "誰でも月収",
    "絶対に",
    "100%",
    "ノーリスク",
    # エンゲージメントベイト系
    "RTして",
    "リツイートして",
    "いいねして",
    "フォローして",
    "拡散希望",
    "広めて",
    "シェアして",
    # トレンド便乗系
    "トレンド",
    "バズ",
    "バズる",
    # 煽り・過激表現系
    "炎上",
    "バカ",
    "情弱",
    "養分",
    "終わってる",
    # スパム的表現
    "無料プレゼント",
    "期間限定で無料",
    "今だけ無料",
    "LINE登録",
    "DM送って",
]

# 文字数制限
MAX_TEXT_LENGTH = 260


def now_jst() -> datetime:
    """現在時刻をJSTで取得"""
    return datetime.now(JST)


def now_utc() -> datetime:
    """現在時刻をUTCで取得"""
    return datetime.now(UTC)


def today_jst() -> str:
    """今日の日付をYYYY-MM-DD形式で取得（JST基準）"""
    return now_jst().strftime("%Y-%m-%d")


def utc_iso() -> str:
    """現在時刻をUTC ISO形式で取得"""
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_text(text: str) -> str:
    """テキストを正規化（空白圧縮、前後トリム）"""
    # 連続する空白を1つに
    text = re.sub(r"[ \t]+", " ", text)
    # 連続する改行を2つまでに
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 前後の空白を除去
    return text.strip()


def calculate_fingerprint(text: str) -> str:
    """正規化したテキストのSHA256ハッシュを計算"""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_hook(item: dict) -> str:
    """投稿アイテムからhookを抽出（hookフィールド優先、なければtextの1行目）"""
    if item.get("hook"):
        return normalize_text(item["hook"])
    text = item.get("text", "")
    first_line = text.split("\n")[0] if text else ""
    return normalize_text(first_line)


def check_forbidden_words(text: str) -> list[str]:
    """禁止語をチェックし、見つかった禁止語のリストを返す"""
    found = []
    text_lower = text.lower()
    for word in FORBIDDEN_WORDS:
        if word.lower() in text_lower:
            found.append(word)
    return found


def validate_text_length(text: str) -> tuple[bool, int]:
    """テキスト長を検証（OK, 文字数）を返す"""
    length = len(text)
    return length <= MAX_TEXT_LENGTH, length


def load_queue(queue_path: Path) -> list[dict]:
    """queue.jsonを読み込む"""
    if not queue_path.exists():
        return []
    with open(queue_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue_path: Path, queue: list[dict]) -> None:
    """queue.jsonを保存"""
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def get_posted_items(queue: list[dict], limit: int = 50) -> list[dict]:
    """status=postedのアイテムを取得（直近limit件）"""
    posted = [item for item in queue if item.get("status") == "posted"]
    # posted_at_utcでソート（降順）してlimit件
    posted.sort(key=lambda x: x.get("posted_at_utc", ""), reverse=True)
    return posted[:limit]


def check_fingerprint_duplicate(
    fingerprint: str, queue: list[dict], limit: int = 50
) -> bool:
    """fingerprintが直近limit件のpostedと重複しているかチェック"""
    posted = get_posted_items(queue, limit)
    for item in posted:
        if item.get("fingerprint") == fingerprint:
            return True
    return False


def check_hook_duplicate(hook: str, queue: list[dict], limit: int = 14) -> bool:
    """hookが直近limit件のpostedと重複しているかチェック"""
    posted = get_posted_items(queue, limit)
    normalized_hook = normalize_text(hook)
    for item in posted:
        if normalize_text(extract_hook(item)) == normalized_hook:
            return True
    return False


def format_log(level: str, message: str) -> str:
    """ログメッセージをフォーマット"""
    timestamp = now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"[{timestamp}] [{level.upper()}] {message}"


def log_info(message: str) -> None:
    """INFOログを出力"""
    print(format_log("INFO", message))


def log_error(message: str) -> None:
    """ERRORログを出力"""
    print(format_log("ERROR", message))


def log_warning(message: str) -> None:
    """WARNINGログを出力"""
    print(format_log("WARNING", message))


class PostValidationError(Exception):
    """投稿バリデーションエラー"""

    pass


class PostAPIError(Exception):
    """投稿API呼び出しエラー"""

    pass
