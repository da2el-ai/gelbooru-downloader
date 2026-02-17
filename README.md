# Gelbooru Downloader

Gelbooruから画像とタグをダウンロードし、機械学習用データセットを作成するCLIツール

## 特徴

- 🔍 **柔軟な検索**: URLクエリパラメータ形式で検索条件を指定
- 📝 **WD14形式キャプション**: タグを自動的にキャプションファイル(.txt)に保存
- 🗄️ **重複防止**: SQLiteで既にダウンロード済みの画像をスキップ
- 🚫 **デフォルト除外タグ**: 不要なタグを設定ファイルで一括除外
- 📄 **バッチ処理**: ファイルから複数のクエリを一括実行
- 🔄 **自動ページネーション**: 大量ダウンロード時にAPIの制限を自動処理
- 🌐 **非同期処理**: aiohttpとaiofilesによる高速ダウンロード

## インストール

### 要件

- Python 3.8以上

### インストール方法

```bash
# リポジトリをクローン
git clone https://github.com/da2el-ai/gelbooru-downloader.git
cd gelbooru-downloader

# 仮想環境を作成（推奨）
python -m venv venv

# 仮想環境をアクティベート
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 依存パッケージをインストール
pip install -e .

# または開発モードでインストール
pip install -e ".[dev]"
```

### APIキーとユーザーIDを記入

`config.json`を作成します。

```bash
gelbooru-dl --init-config
```

API KeyとUser IDを記入してください。<br>
[Gelbooruの設定ページ](https://gelbooru.com/index.php?page=account&s=options) `API Access Credentials` から取得できます。<br>


下記のように記載されているので `&api_key=` 以降を `api_key` に、`&user_id=` 以降を `user_id` に転記します。

```
&api_key=XXXXXXXXXXXXXXXXXX&user_id=ZZZZZZZZZ
```
👇
```json
{
  "api_key": "XXXXXXXXXXXXXXXXXX",
  "user_id": "ZZZZZZZZZ",
  ...
```

## クイックスタート


### 2. 基本的な使い方

```bash
# `blonde_hair` をダウンロード
gelbooru-dl --query "tags=blonde_hair"

# `blonde_hair` と `1girl solo` をダウンロード
# 後者は50件を上限指定している
gelbooru-dl --query "tags=blonde_hair" --query "tags=1girl+solo&limit=50"

# ファイルからクエリを読み込み
gelbooru-dl -f search.txt

# ドライラン（実際にダウンロードせず確認）
gelbooru-dl -f search.txt --dry-run
```

#### ポイント

- `limit` が指定されてなければ config.json の `default_limit` が適用されます。
- config.json の `default_exclude_tags` に記載されている除外タグも自動的に適用されます。


## 使い方

### コマンドラインオプション

```
gelbooru-dl [オプション]

オプション:
  --query <QUERY>           検索クエリ（複数指定可）
  -f, --file <PATH>         検索クエリリストファイル
  -o, --output <DIR>        出力ディレクトリ (デフォルト: ./download)
  -c, --config <PATH>       設定ファイル (デフォルト: ./config.json)
  -d, --delay <MILLISEC>    リクエスト間隔（ミリ秒、デフォルト: 1000）
  --dry-run                 ドライラン
  --init-config             デフォルト設定ファイルを作成
  --stats                   統計情報を表示
  --log-level <LEVEL>       ログレベル (DEBUG/INFO/WARNING/ERROR)
  --log-file <PATH>         ログファイルパス
  -h, --help                ヘルプを表示
```

### 検索クエリの書き方

URLクエリパラメータ形式で指定します。

```bash
# 基本的な検索
tags=blonde_hair

# 複数タグは `+` で繋ぐ（AND検索）
tags=1girl+solo+blonde_hair

# 除外タグは `-` を付ける。この場合は `cat_ears` を除外している
tags=blonde_hair+-cat_ears

# `limit` で上限指定
tags=1girl+solo+blonde_hair&limit=300

# rating指定
tags=landscape+rating:safe&limit=200
```

### クエリリストファイル

`search.txt`を作成して、1行1クエリで記載：

```
# コメント行（#始まり）と空行は無視されます

tags=blonde_hair&limit=100
tags=1girl+solo&limit=50
tags=landscape+rating:safe&limit=200
```

クエリリストファイルを指定して実行。

```bash
gelbooru-dl -f search.txt
```

### 出力形式

ダウンロードされたファイルは以下のように保存されます：

```
download/
├── download.db                                    # データベース
├── 20260217-143052_tags=blonde_hair&limit=100/
│   ├── 12345_abc123def456.jpg                    # 画像ファイル
│   ├── 12345_abc123def456.txt                    # キャプションファイル
│   ├── 67890_def456abc123.png
│   └── 67890_def456abc123.txt
└── 20260217-150330_tags=1girl+solo&limit=50/
    └── ...
```

**ファイル名規則**: `{post_id}_{md5}.{拡張子}`

**キャプション形式**: WD14形式（タグを`, `区切り）

例: `1girl, solo, blonde_hair, blue_eyes, long_hair, smile, rating:safe`
　
#### データベースについて

データベースはダウンロードした画像のIDを記録しています。これは同じファイルを重複してダウンロードしないための対策です。



### デフォルト除外タグ

`config.json`で設定した除外タグは、すべてのクエリに自動的に適用されます：

```json
{
  "default_exclude_tags": ["comic", "3d", "photo", "cosplay"]
}
```

クエリ: `tags=blonde_hair&limit=100`  
実際の検索: `tags=blonde_hair+-comic+-3d+-photo+-cosplay&limit=100`

### 統計情報表示

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
  ...
==================================================
```

## 設定ファイル

`config.json`:

```json
{
  "api_key": "",                      // Gelbooru API Key（オプション）
  "user_id": "",                      // Gelbooru User ID（オプション）
  "display_all_site_content": true,   // 全コンテンツ表示（推奨）
  "output_dir": "./download",         // 出力ディレクトリ
  "delay_ms": 1000,                   // リクエスト間隔（ミリ秒）
  "max_retries": 3,                   // リトライ回数
  "retry_delay": 1.0,                 // リトライ間隔（秒）
  "default_exclude_tags": [           // デフォルト除外タグ
    "comic",
    "3d",
    "photo",
    "cosplay"
  ],
  "default_limit": 100                // デフォルト取得件数
}
```

## 開発

### テストの実行

```bash
# テストをインストール
pip install -e ".[dev]"

# テスト実行
pytest

# カバレッジ付き
pytest --cov=gelbooru_downloader
```

### プロジェクト構造

```
gelbooru-downloader/
├── gelbooru_downloader/
│   ├── __init__.py
│   ├── api.py              # Gelbooru APIラッパー
│   ├── database.py         # SQLite管理
│   ├── downloader.py       # ダウンロードロジック
│   ├── cli.py              # CLIエントリーポイント
│   └── utils.py            # ユーティリティ関数
├── test/                   # テストコード
├── pyproject.toml          # パッケージ設定
├── config.json.sample      # 設定ファイルサンプル
└── search.txt.sample       # クエリリストサンプル
```

## 注意事項

- **利用規約**: Gelbooru APIの利用規約を遵守してください
- **レート制限**: リクエスト間隔は1秒以上を推奨
- **API Key**: API Key/User IDを設定するとレート制限が緩和されます
- **著作権**: 学習データの利用時は著作権やライセンスに注意してください

## ライセンス

MIT License

## 貢献

Issue、Pull Requestは大歓迎です！

## 関連リンク

- [Gelbooru](https://gelbooru.com/)
- [Gelbooru API Documentation](https://gelbooru.com/index.php?page=wiki&s=view&id=18780)
