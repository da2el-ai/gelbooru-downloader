"""CLI エントリーポイント"""

import argparse
import asyncio
import sys
import logging
from pathlib import Path
from typing import List

from . import __version__
from .api import GelbooruAPI
from .database import Database, print_statistics
from .downloader import download_query, DownloadResult
from .utils import (
  Config,
  load_query_list,
  apply_default_exclude_tags,
  generate_output_dir_name,
  setup_logging
)

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
  """コマンドライン引数パーサーを作成"""
  parser = argparse.ArgumentParser(
    prog='gelbooru-dl',
    description='Gelbooru画像ダウンローダー - 機械学習データセット作成用CLIツール',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
使用例:
  # 単一クエリ
  gelbooru-dl --query "tags=blonde_hair&limit=100"
  
  # 複数クエリ
  gelbooru-dl --query "tags=blonde_hair&limit=100" --query "tags=1girl+solo&limit=50"
  
  # ファイルから読み込み
  gelbooru-dl -f search.txt
  
  # ドライラン（実際にダウンロードしない）
  gelbooru-dl -f search.txt --dry-run
  
  # 統計情報表示
  gelbooru-dl --stats
  
詳細: https://github.com/yourusername/gelbooru-downloader
    """
  )
  
  parser.add_argument(
    '--version',
    action='version',
    version=f'%(prog)s {__version__}'
  )
  
  # クエリ指定
  parser.add_argument(
    '--query',
    action='append',
    dest='queries',
    metavar='QUERY',
    help='URLクエリパラメータ形式で検索条件を指定（複数指定可）'
  )
  
  parser.add_argument(
    '-f', '--file',
    type=Path,
    metavar='PATH',
    help='検索クエリリストファイル'
  )
  
  # 出力設定
  parser.add_argument(
    '-o', '--output',
    type=Path,
    metavar='DIR',
    help='出力ディレクトリ (デフォルト: ./download)'
  )
  
  parser.add_argument(
    '-c', '--config',
    type=Path,
    default=Path('config.json'),
    metavar='PATH',
    help='設定ファイル (デフォルト: ./config.json)'
  )
  
  # ダウンロード設定
  parser.add_argument(
    '-d', '--delay',
    type=int,
    metavar='MILLISEC',
    help='リクエスト間隔（ミリ秒、デフォルト: 1000）'
  )
  
  # 動作モード
  parser.add_argument(
    '--dry-run',
    action='store_true',
    help='実際にダウンロードせず、取得内容を表示'
  )
  
  parser.add_argument(
    '--init-config',
    action='store_true',
    help='デフォルト設定ファイルを作成'
  )
  
  parser.add_argument(
    '--stats',
    action='store_true',
    help='データベースの統計情報を表示'
  )
  
  # ログ設定
  parser.add_argument(
    '--log-level',
    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    default='INFO',
    metavar='LEVEL',
    help='ログレベル (DEBUG/INFO/WARNING/ERROR、デフォルト: INFO)'
  )
  
  parser.add_argument(
    '--log-file',
    type=Path,
    metavar='PATH',
    help='ログファイルパス'
  )
  
  return parser


def handle_init_config(config_path: Path) -> int:
  """設定ファイル初期化を処理"""
  if config_path.exists():
    print(f"エラー: 設定ファイルが既に存在します: {config_path}")
    response = input("上書きしますか？ (y/n): ")
    if response.lower() != 'y':
      print("キャンセルしました")
      return 0
  
  Config.create_sample_config(config_path)
  print(f"設定ファイルを作成しました: {config_path}")
  print("設定ファイルを編集して、API KeyやUser IDを設定してください")
  return 0


def handle_stats(config: Config) -> int:
  """統計情報表示を処理"""
  output_dir = Path(config.get('output_dir', './download'))
  db_path = output_dir / 'download.db'
  
  if not db_path.exists():
    print(f"エラー: データベースが見つかりません: {db_path}")
    print("まだダウンロードを実行していないか、出力ディレクトリが異なります")
    return 1
  
  print_statistics(db_path)
  return 0


async def handle_download(args: argparse.Namespace, config: Config) -> int:
  """ダウンロード処理を実行"""
  # クエリリストを収集
  queries: List[str] = []
  
  # コマンドライン引数からクエリを取得
  if args.queries:
    queries.extend(args.queries)
  
  # ファイルからクエリを読み込み
  if args.file:
    file_queries = load_query_list(args.file)
    queries.extend(file_queries)
  
  if not queries:
    print("エラー: 検索クエリが指定されていません")
    print("--query または -f オプションでクエリを指定してください")
    print("詳細は --help を参照してください")
    return 1
  
  # 設定値を取得
  output_base_dir = args.output or Path(config.get('output_dir', './download'))
  delay_ms = args.delay or config.get('delay_ms', 1000)
  max_retries = config.get('max_retries', 3)
  retry_delay = config.get('retry_delay', 1.0)
  default_exclude_tags = config.get('default_exclude_tags', [])
  
  # データベースを初期化
  db_path = output_base_dir / 'download.db'
  database = Database(db_path)
  
  # API初期化
  api = GelbooruAPI(
    api_key=config.get('api_key'),
    user_id=config.get('user_id'),
    display_all_site_content=config.get('display_all_site_content', True)
  )
  
  try:
    async with api:
      # 各クエリを処理
      for query_idx, query in enumerate(queries, start=1):
        print(f"\n{'='*60}")
        print(f"クエリ {query_idx}/{len(queries)}")
        print(f"{'='*60}")
        
        # デフォルト除外タグを適用
        if default_exclude_tags:
          logger.info(f"デフォルト除外タグ: {', '.join(default_exclude_tags)}")
          query_with_exclude = apply_default_exclude_tags(query, default_exclude_tags)
          logger.info(f"元のクエリ: {query}")
          logger.info(f"実際のクエリ: {query_with_exclude}")
          query = query_with_exclude
        
        # 出力ディレクトリを生成
        output_dir_name = generate_output_dir_name(query)
        output_dir = output_base_dir / output_dir_name
        
        # ドライラン情報表示
        if args.dry_run:
          print(f"\n[DRY RUN] クエリ: {query}")
          print(f"出力先: {output_dir}")
          print("※ 実際のダウンロードは行われません\n")
        
        # ダウンロード実行
        result = await download_query(
          api=api,
          database=database,
          query=query,
          output_dir=output_dir,
          delay_ms=delay_ms,
          max_retries=max_retries,
          retry_delay=retry_delay,
          dry_run=args.dry_run
        )
        
        # 結果表示
        print(f"\nクエリ {query_idx} 完了:")
        print(f"  {result}")
        
        if not args.dry_run and result.downloaded > 0:
          print(f"  保存先: {output_dir}")
  
  finally:
    database.close()
  
  print(f"\n{'='*60}")
  print("すべてのクエリが完了しました")
  print(f"{'='*60}")
  
  return 0


def main() -> int:
  """メインエントリーポイント"""
  parser = create_parser()
  args = parser.parse_args()
  
  # ログ設定
  setup_logging(
    log_level=args.log_level,
    log_file=args.log_file
  )
  
  # 設定ファイル初期化
  if args.init_config:
    return handle_init_config(args.config)
  
  # 設定読み込み
  config = Config(args.config if args.config.exists() else None)
  
  # 統計情報表示
  if args.stats:
    return handle_stats(config)
  
  # ダウンロード処理
  try:
    return asyncio.run(handle_download(args, config))
  except KeyboardInterrupt:
    print("\n\n中断されました")
    return 130
  except Exception as e:
    logger.exception(f"予期しないエラーが発生しました: {e}")
    return 1


if __name__ == '__main__':
  sys.exit(main())
