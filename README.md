# X Auto Post Bot

X（旧Twitter）への自動投稿ボット。GitHub Actions + Python + queue.json による投稿キュー管理システム。

## 特徴

- 毎日 17:00 JST と 19:00 JST に自動投稿
- X API Free プラン対応（投稿のみ、reads不使用）
- queue.json による投稿キュー管理と履歴管理
- 重複・禁止語の自動検知
- テンプレート×辞書による投稿自動生成
- ローカル検証用の dry-run モード

## ディレクトリ構成

```
.
├─ README.md
├─ queue.json              # 投稿キュー
├─ requirements.txt
├─ .gitignore
├─ content/
│  ├─ templates.json       # 投稿テンプレート
│  ├─ lexicon.json         # 辞書（可変フレーズ）
│  └─ rules.md             # 禁止語・ルール
├─ scripts/
│  ├─ generate_queue.py    # キュー生成
│  ├─ validate_queue.py    # バリデーション
│  └─ approve_range.py     # 期間承認
├─ src/
│  ├─ post_slot.py         # 投稿メインスクリプト
│  └─ utils.py             # ユーティリティ
└─ .github/
   └─ workflows/
      └─ x_autopost.yml    # GitHub Actions
```

## セットアップ

### 1. X API 認証情報の取得

1. [X Developer Portal](https://developer.x.com/) でアプリを作成
2. OAuth 1.0a User Context を有効化
3. 以下のキーを取得：
   - API Key
   - API Key Secret
   - Access Token
   - Access Token Secret

### 2. GitHub Secrets の設定

リポジトリの Settings → Secrets and variables → Actions で以下を設定：

| Secret Name | 説明 |
|------------|------|
| `X_API_KEY` | API Key |
| `X_API_KEY_SECRET` | API Key Secret |
| `X_ACCESS_TOKEN` | Access Token |
| `X_ACCESS_TOKEN_SECRET` | Access Token Secret |

### 3. GitHub Actions の有効化

1. リポジトリの Actions タブへ移動
2. ワークフローを有効化

## ローカル実行

### 環境構築

```bash
# 仮想環境作成（推奨）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージインストール
pip install -r requirements.txt
```

### 投稿キューの生成

```bash
# 今日から30日分を生成
python scripts/generate_queue.py

# 開始日と日数を指定
python scripts/generate_queue.py --start 2025-02-01 --days 30

# シード固定（再現性確保）
python scripts/generate_queue.py --seed 42

# 既存キューに追記
python scripts/generate_queue.py --append --days 7
```

### バリデーション

```bash
python scripts/validate_queue.py
```

成功時は exit code 0、失敗時は exit code 1 を返します。

### 期間承認

```bash
# 期間を指定して承認
python scripts/approve_range.py --from 2025-01-23 --to 2025-01-31

# dry-run で確認のみ
python scripts/approve_range.py --from 2025-01-23 --to 2025-01-31 --dry-run
```

### 投稿テスト（dry-run）

```bash
# 環境変数でスロット指定
export SLOT=17
python src/post_slot.py --dry-run

# または19時スロット
export SLOT=19
python src/post_slot.py --dry-run
```

### 実際の投稿（ローカル）

```bash
# 環境変数設定
export X_API_KEY="your_api_key"
export X_API_KEY_SECRET="your_api_key_secret"
export X_ACCESS_TOKEN="your_access_token"
export X_ACCESS_TOKEN_SECRET="your_access_token_secret"
export SLOT=17

# 投稿実行
python src/post_slot.py
```

## 運用フロー

### 月次運用

1. 毎月末に翌月分のキューを生成
   ```bash
   python scripts/generate_queue.py --start 2025-02-01 --days 28
   ```

2. 生成内容を目視確認（queue.json を開いてチェック）

3. 問題なければ一括承認
   ```bash
   python scripts/approve_range.py --from 2025-02-01 --to 2025-02-28
   ```

4. コミット＆プッシュ
   ```bash
   git add queue.json
   git commit -m "Add February posts"
   git push
   ```

### 週次運用（推奨）

- 週1回、翌週の投稿を確認
- 必要に応じて queue.json を手動編集
- 変更があればコミット＆プッシュ

## queue.json スキーマ

```json
{
  "date": "2025-01-23",
  "slot": "17",
  "pillar": "unpaid",
  "format": "checklist",
  "hook": "未払い対策で失敗しないための5つのチェックリスト",
  "text": "投稿本文...",
  "status": "draft|approved|posted",
  "fingerprint": "sha256hash...",
  "tweet_id": null,
  "posted_at_utc": null
}
```

### status の意味

| status | 説明 |
|--------|------|
| `draft` | 下書き。自動投稿されない |
| `approved` | 承認済み。自動投稿の対象 |
| `posted` | 投稿完了 |

## 投稿ルール

### 文字数

- 上限: 260文字（安全マージン）
- 推奨: 180〜230文字

### 禁止語

`content/rules.md` に定義。主な禁止語：

- 収益保証系: 「必ず稼げる」「保証」「確実に」
- エンゲージメントベイト: 「RTして」「いいねして」「拡散希望」
- トレンド便乗: 「トレンド」「バズ」
- 煽り表現: 「炎上」「情弱」

### 重複ガード

- fingerprint: 直近50件の posted と一致で拒否
- hook: 直近14件の posted と一致で拒否

## トラブルシューティング

### 投稿されない

1. queue.json に当日の approved 投稿があるか確認
2. GitHub Secrets が正しく設定されているか確認
3. Actions のログを確認

### バリデーションエラー

1. エラーメッセージを確認
2. 該当のインデックスを queue.json で修正
3. 再度バリデーション実行

### API エラー

1. 認証情報が正しいか確認
2. X API の制限に達していないか確認
3. X Developer Portal でアプリのステータスを確認

## ライセンス

MIT
