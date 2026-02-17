# Gelbooru Downloader 仕様書

## 概要
Gelbooruからタグ検索した画像をダウンロードし、WD14形式のキャプションファイルと共に保存するCLIアプリケーション

## 用途
機械学習の学習データセット作成

## 機能要件

### 基本機能
- URLクエリパラメータ形式で検索条件を指定
- 画像をダウンロードし、タグをキャプションファイル（.txt）に保存
- SQLiteでダウンロード済み画像を管理し、重複ダウンロードを防止
- デフォルト除外タグを設定可能

### 画像とキャプション
- **ファイル名規則**: `{post_id}_{md5}.{拡張子}`
  - 例: `12345_abc123def456.jpg`
- **キャプションファイル**: 画像と同名の.txtファイル
  - 例: `12345_abc123def456.txt`
- **キャプション形式**: WD14形式（タグを「`, `」区切り）
  - 例: `1girl, solo, blonde_hair, blue_eyes, long_hair, smile, rating:safe`
- **タグの順序**: Gelbooru APIのレスポンス順序をそのまま保持
- **タグの表記**: Gelbooruのタグをそのまま使用（変換なし）

### 検索クエリ指定方法

#### 1. コマンドラインオプション
```bash
gelbooru-dl --query "tags=blonde_hair+-cat_ears&limit=100"
```

#### 2. ファイルから読み込み
`search.txt`に1行1クエリで記載：
```
# Gelbooru検索クエリリスト
# 1行1クエリ、URLクエリパラメータ形式

tags=blonde_hair+-cat_ears&limit=100
tags=1girl+solo&limit=50
tags=landscape+rating:safe&limit=200

# コメント行（#始まり）と空行は無視
```

実行：
```bash
gelbooru-dl -f search.txt
```

### デフォルト除外タグ
- `config.json`に記載した除外タグは**常に適用**
- クエリに除外タグが含まれていても、追加で適用
- 例：
  - `config.json`: `"default_exclude_tags": ["comic", "3d"]`
  - クエリ: `tags=blonde_hair+-cat_ears&limit=100`
  - 実際の検索: `tags=blonde_hair+-cat_ears+-comic+-3d&limit=100`

### ページネーション処理
- Gelbooru APIは1リクエストあたり最大100件
- ユーザーが`limit=1000`を指定した場合、自動的に複数ページを取得
- 処理フロー：
  1. `limit=1000`を検出
  2. `limit=100&pid=0` → `limit=100&pid=1` → ... → `limit=100&pid=9`
  3. 合計1000件を取得
- `limit`指定がない場合は`config.json`の`default_limit`を使用

### ダウンロード済み判定
- SQLiteデータベースで管理
- テーブル構成（シンプル版）:
  ```sql
  CREATE TABLE downloaded_posts (
      post_id INTEGER PRIMARY KEY,
      downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  
  CREATE INDEX idx_downloaded_at ON downloaded_posts(downloaded_at);
  ```
- 既にダウンロード済みの画像（post_id）はスキップ

## コマンドラインインターフェース

```bash
gelbooru-dl [オプション]

オプション:
  --query <QUERY>           URLクエリパラメータ形式で検索条件を指定（複数指定可）
  -f, --file <PATH>         検索クエリリストファイル
  -o, --output <DIR>        出力ディレクトリ (デフォルト: ./download)
  -c, --config <PATH>       設定ファイル (デフォルト: ./config.json)
  -d, --delay <MILLISEC>    リクエスト間隔（ミリ秒、デフォルト: 1000）
  --dry-run                 実際にダウンロードせず、取得内容を表示
  --init-config             デフォルト設定ファイルを作成
  --stats                   データベースの統計情報を表示
  --log-level <LEVEL>       ログレベル (DEBUG/INFO/WARNING/ERROR、デフォルト: INFO)
  --log-file <PATH>         ログファイルパス
  -h, --help                ヘルプを表示
```

### 使用例
```bash
# 単一クエリ
gelbooru-dl --query "tags=blonde_hair&limit=100"

# 複数クエリ
gelbooru-dl --query "tags=blonde_hair&limit=100" --query "tags=1girl+solo&limit=50"

# ファイルから読み込み
gelbooru-dl -f search.txt

# ドライラン（実際にダウンロードしない）
gelbooru-dl -f search.txt --dry-run

# 出力先指定
gelbooru-dl -f search.txt -o /path/to/dataset

# リクエスト間隔を2秒に設定
gelbooru-dl -f search.txt -d 2000

# 設定ファイル指定
gelbooru-dl -f search.txt -c my_config.json

# デフォルト設定作成
gelbooru-dl --init-config

# 統計情報表示
gelbooru-dl --stats
```

## ファイル・ディレクトリ構成

### 出力ディレクトリ構造
```
download/
├── download.db                                      # SQLite（共通）
├── 20260217-143052_tags=blonde_hair/
│   ├── 12345_abc123def456.jpg
│   ├── 12345_abc123def456.txt
│   ├── 67890_def456abc123.png
│   └── 67890_def456abc123.txt
└── 20260217-150330_tags=1girl+solo/
    ├── 11111_aaa111bbb222.jpg
    ├── 11111_aaa111bbb222.txt
    └── ...
```

### ディレクトリ名規則
- 形式: `yyyymmdd-hhmmss_{クエリ文字列}`
- 例: `20260217-143052_tags=blonde_hair+-cat_ears&limit=100`
- クエリ文字列が50文字を超える場合は切り捨て
  - 例: `20260217-143052_tags=1girl+solo+blonde_hair+blue...(50文字)`
- 同じクエリを再実行した場合でも、タイムスタンプで区別して新規ディレクトリを作成

### ファイル名規則
- 形式: `{post_id}_{md5}.{拡張子}`
- 例: `12345_abc123def456.jpg`、`12345_abc123def456.txt`

### 検索クエリリストファイル (search.txt)
```
# Gelbooru検索クエリリスト
# 1行1クエリ、URLクエリパラメータ形式

# 基本的な検索
tags=blonde_hair&limit=100

# 除外タグ付き
tags=blonde_hair+-cat_ears&limit=100

# 複数タグのAND検索
tags=1girl+solo+blonde_hair&limit=50

# rating指定
tags=landscape+rating:safe&limit=200

# 大量取得（自動的にページネーション）
tags=scenery&limit=1000

# コメント行と空行は無視
```

### 設定ファイル (config.json)
```json
{
  "api_key": "",
  "user_id": "",
  "display_all_site_content": true,
  "output_dir": "./download",
  "delay_ms": 1000,
  "max_retries": 3,
  "retry_delay": 1.0,
  "default_exclude_tags": [
    "comic",
    "3d",
    "photo",
    "cosplay"
  ],
  "default_limit": 100
}
```

**設定項目:**
- `api_key` (オプション): Gelbooru API Key（レート制限緩和）
- `user_id` (オプション): Gelbooru User ID（レート制限緩和）
- `display_all_site_content` (推奨: true): 全コンテンツ表示を有効化（fringeBenefits cookie）
- `output_dir`: ダウンロード先ディレクトリ
- `delay_ms`: リクエスト間隔（ミリ秒）
- `max_retries`: ダウンロード失敗時のリトライ回数
- `retry_delay`: リトライ間隔（秒）
- `default_exclude_tags`: デフォルトで除外するタグ（常に適用）
- `default_limit`: limitが未指定の場合のデフォルト値

## プロジェクト構成

```
gelbooru-downloader/
├── gelbooru_downloader/
│   ├── __init__.py
│   ├── api.py              # Gelbooru APIラッパー（再利用可能、自前実装）
│   ├── database.py         # SQLite操作
│   ├── downloader.py       # ダウンロードロジック
│   ├── cli.py              # CLIエントリーポイント
│   └── utils.py            # ユーティリティ関数
├── test/                   # テストコード
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_database.py
│   ├── test_downloader.py
│   ├── test_utils.py
│   └── test_cli.py
├── pyproject.toml          # パッケージ設定・依存関係管理
├── config.json.sample      # 設定ファイルのサンプル
├── search.txt.sample       # 検索クエリリストのサンプル
├── .gitignore
└── README.md
```

## 技術仕様

### 使用言語・ライブラリ
- Python 3.8+
- aiohttp: 非同期HTTP通信
- aiofiles: 非同期ファイルIO
- SQLite3: ダウンロード履歴管理
- argparse: CLI引数解析

### api.py の設計方針
- **自前実装**（python-gelbooruは使用しない）
- aiohttp使用、直接Gelbooru APIを叩く
- **他のスクリプトから独立して利用可能なモジュール**として設計
- 提供する主な機能:
  - 認証管理（API Key/User ID）
  - fringeBenefits cookie設定（display_all_site_content）
  - 検索実行（URLクエリパラメータをそのまま渡せる）
  - ページネーション自動処理（limit > 100の場合）
  - レスポンスのJSONパース

### Gelbooru API仕様

#### エンドポイント
```
https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1
```

#### パラメータ
- `tags`: 検索タグ（`+`で複数、`-`で除外）
  - 例: `blonde_hair+solo+-cat_ears`
- `limit`: 取得件数（デフォルト100、最大100）
- `pid`: ページ番号（0始まり）
- `api_key`: API Key（オプション、レート制限緩和）
- `user_id`: User ID（オプション、レート制限緩和）
- `json=1`: JSON形式でレスポンス

#### レスポンス例（推測）
```json
{
  "post": [
    {
      "id": 12345,
      "md5": "abc123def456",
      "file_url": "https://img3.gelbooru.com/images/ab/c1/abc123def456.jpg",
      "tags": "1girl solo blonde_hair blue_eyes long_hair smile",
      "rating": "safe",
      "score": 150,
      "width": 1920,
      "height": 1080
    }
  ]
}
```

### タグの変換処理
- APIレスポンス: `"1girl solo blonde_hair blue_eyes"`（スペース区切り）
- キャプションファイル: `"1girl, solo, blonde_hair, blue_eyes"`（`, `区切り）
- 変換ロジック: `tags.replace(' ', ', ')`

### エラーハンドリング
- ネットワークエラー: 設定回数までリトライ、それでも失敗したらスキップ
- 認証エラー: エラーメッセージを表示して終了
- 削除済み画像: スキップして続行
- 不正なクエリ: エラーメッセージを表示して中断

### レート制限対応
- リクエスト間隔: `--delay`オプションまたは`config.json`で設定
- デフォルト: 1000ms（1秒）
- 推奨: 1000-2000ms
- API Key/User ID設定でレート制限緩和

### 進捗表示
- クエリ情報表示
- ダウンロード進捗: `進捗: 45/100 (45.0%) - ID: 12345 (1girl, blonde_hair, ...)`
- 完了メッセージ: 各クエリの完了時に統計表示

### --dry-run の出力

```
[DRY RUN] クエリ: tags=blonde_hair&limit=100
除外タグ（config.json）: comic, 3d, photo
実際のクエリ: tags=blonde_hair+-comic+-3d+-photo&limit=100

検索結果: 500件
ダウンロード対象: 450件
スキップ（既存）: 50件

出力先: ./download/20260217-143052_tags=blonde_hair

ダウンロードされるファイル（最初の10件）:
  [1] 12345_abc123.jpg (1girl, blonde_hair, blue_eyes, ...)
  [2] 67890_def456.jpg (1girl, blonde_hair, long_hair, ...)
  [3] 11111_aaa111.jpg (1girl, blonde_hair, smile, ...)
  ...

※ 実際のダウンロードは行われていません
```

## 統計情報表示

```bash
gelbooru-dl --stats
```

出力例：
```
==================================================
ダウンロード統計
==================================================
総ダウンロード数: 1,250件
初回ダウンロード: 2026-02-15 10:30:45
最終ダウンロード: 2026-02-17 14:22:18

最近のダウンロード（最大10件）:
  [2026-02-17 14:22:18] ID: 12345
  [2026-02-17 14:22:10] ID: 12344
  [2026-02-17 14:22:05] ID: 12343
  ...
==================================================
```

## 実装の優先順位

### Phase 1: コア機能（最優先）
- [x] api.py - Gelbooru APIラッパー（自前実装、モジュール化）
- [x] database.py - SQLite管理（シンプル版）
- [x] downloader.py - ダウンロードロジック
- [x] utils.py - ユーティリティ関数（クエリパース、設定読み込み等）
- [x] cli.py - CLIエントリーポイント

### Phase 2: 基本機能
- [x] URLクエリパラメータのパース
- [x] ページネーション処理（limit > 100）
- [x] デフォルト除外タグの適用
- [x] キャプションファイル生成
- [x] 進捗表示

### Phase 3: 追加機能
- [x] --dry-run
- [x] --stats
- [x] エラーハンドリング
- [x] ログ出力

## 注意事項

- Gelbooru APIの利用規約を遵守してください
- レート制限を避けるため、リクエスト間隔は1秒以上を推奨
- API Key/User IDを設定すると、レート制限が緩和されます
- 大量ダウンロードは避け、適切な間隔を設定してください
- 学習データ用途では、著作権やライセンスに注意してください

## 今後の拡張案（オプション）

- [ ] 並列ダウンロード対応
- [ ] メタデータJSON保存オプション
- [ ] タグフィルタリング（特定カテゴリのみ）
- [ ] ダウンロードレポート生成
- [ ] 中断・再開機能の強化
