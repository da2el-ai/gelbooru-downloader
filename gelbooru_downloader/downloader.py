"""ダウンロードロジック"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import aiohttp
import aiofiles

from .api import GelbooruAPI, GelbooruAPIError
from .database import Database
from .utils import format_tags_for_caption, format_file_size

logger = logging.getLogger(__name__)


class DownloadResult:
  """ダウンロード結果"""
  
  def __init__(self):
    self.total = 0          # 総件数
    self.downloaded = 0     # ダウンロード成功
    self.skipped = 0        # スキップ（既存）
    self.failed = 0         # 失敗
    self.failed_ids = []    # 失敗したpost_id
  
  def __str__(self) -> str:
    return (
      f"合計: {self.total}件 | "
      f"ダウンロード: {self.downloaded}件 | "
      f"スキップ: {self.skipped}件 | "
      f"失敗: {self.failed}件"
    )


class Downloader:
  """画像ダウンローダー"""
  
  def __init__(
    self,
    api: GelbooruAPI,
    database: Database,
    output_dir: Path,
    max_retries: int = 3,
    retry_delay: float = 1.0
  ):
    """
    ダウンローダーを初期化する
    
    Args:
      api: Gelbooru APIクライアント
      database: データベース
      output_dir: 出力ディレクトリ
      max_retries: ダウンロード失敗時のリトライ回数
      retry_delay: リトライ間隔（秒）
    """
    self.api = api
    self.database = database
    self.output_dir = output_dir
    self.max_retries = max_retries
    self.retry_delay = retry_delay
  
  async def download_posts(
    self,
    posts: List[Dict[str, Any]],
    dry_run: bool = False,
    show_progress: bool = True
  ) -> DownloadResult:
    """
    投稿リストをダウンロードする
    
    Args:
      posts: 投稿データのリスト
      dry_run: ドライランモード（実際にダウンロードしない）
      show_progress: 進捗表示
    
    Returns:
      ダウンロード結果
    """
    result = DownloadResult()
    result.total = len(posts)
    
    if not posts:
      logger.info("ダウンロードする投稿がありません")
      return result
    
    # 出力ディレクトリを作成
    if not dry_run:
      self.output_dir.mkdir(parents=True, exist_ok=True)
      logger.info(f"出力先: {self.output_dir}")
    
    # 各投稿をダウンロード
    for idx, post in enumerate(posts, start=1):
      post_id = post.get('id')
      
      if post_id is None:
        logger.warning(f"投稿 {idx} にIDがありません。スキップします")
        result.failed += 1
        continue
      
      # 既にダウンロード済みかチェック
      if self.database.is_downloaded(post_id):
        logger.debug(f"投稿 {post_id} は既にダウンロード済みです")
        result.skipped += 1
        
        if show_progress:
          self._show_progress(idx, result.total, post_id, "スキップ（既存）")
        
        continue
      
      # ダウンロード実行
      try:
        if dry_run:
          # ドライランモード
          tags = post.get('tags', '')
          tags_preview = tags[:50] + "..." if len(tags) > 50 else tags
          
          if show_progress:
            self._show_progress(idx, result.total, post_id, f"[DRY RUN] {tags_preview}")
          
          result.downloaded += 1
        else:
          # 実際にダウンロード
          success = await self._download_single_post(post)
          
          if success:
            result.downloaded += 1
            self.database.mark_as_downloaded(post_id)
            
            tags = post.get('tags', '')
            tags_preview = tags[:50] + "..." if len(tags) > 50 else tags
            
            if show_progress:
              self._show_progress(idx, result.total, post_id, tags_preview)
          else:
            result.failed += 1
            result.failed_ids.append(post_id)
            
            if show_progress:
              self._show_progress(idx, result.total, post_id, "失敗")
      
      except Exception as e:
        logger.error(f"投稿 {post_id} のダウンロード中にエラーが発生しました: {e}")
        result.failed += 1
        result.failed_ids.append(post_id)
    
    return result
  
  async def _download_single_post(self, post: Dict[str, Any]) -> bool:
    """
    単一の投稿をダウンロードする
    
    Args:
      post: 投稿データ
    
    Returns:
      成功した場合True
    """
    post_id = post.get('id')
    md5 = post.get('md5', '')
    file_url = post.get('file_url')
    tags = post.get('tags', '')
    
    if not file_url:
      logger.warning(f"投稿 {post_id} にfile_urlがありません")
      return False
    
    logger.debug(f"ダウンロードURL: {file_url}")
    
    # ファイル拡張子を取得
    extension = Path(file_url).suffix
    
    # ファイル名を生成
    filename = f"{post_id}_{md5}{extension}"
    image_path = self.output_dir / filename
    caption_path = self.output_dir / f"{post_id}_{md5}.txt"
    
    # 画像をダウンロード
    for attempt in range(1, self.max_retries + 1):
      try:
        success = await self._download_file(file_url, image_path)
        if success:
          break
        
        if attempt < self.max_retries:
          logger.warning(f"投稿 {post_id} のダウンロードに失敗。リトライ {attempt}/{self.max_retries}")
          await asyncio.sleep(self.retry_delay)
      except Exception as e:
        logger.error(f"投稿 {post_id} のダウンロード中にエラー: {e}")
        if attempt < self.max_retries:
          await asyncio.sleep(self.retry_delay)
    else:
      # すべてのリトライが失敗
      logger.error(f"投稿 {post_id} のダウンロードに失敗しました")
      return False
    
    # キャプションファイルを作成
    try:
      caption_text = format_tags_for_caption(tags)
      async with aiofiles.open(caption_path, 'w', encoding='utf-8') as f:
        await f.write(caption_text)
    except Exception as e:
      logger.error(f"キャプションファイルの作成に失敗しました: {e}")
      # 画像は取得できたので、失敗とはしない
    
    return True
  
  async def _download_file(self, url: str, dest_path: Path) -> bool:
    """
    ファイルをダウンロードする
    
    Args:
      url: ダウンロードURL
      dest_path: 保存先パス
    
    Returns:
      成功した場合True
    """
    try:
      # Refererヘッダーを追加（ホットリンク防止対策）
      headers = {
        'Referer': 'https://gelbooru.com/'
      }
      
      async with self.api.session.get(url, headers=headers) as response:
        if response.status != 200:
          logger.warning(f"ファイルダウンロード失敗: HTTP {response.status} - {url}")
          return False
        
        # ファイルに書き込み
        async with aiofiles.open(dest_path, 'wb') as f:
          # チャンクごとに書き込み
          async for chunk in response.content.iter_chunked(8192):
            await f.write(chunk)
        
        # ファイルサイズをログ
        file_size = dest_path.stat().st_size
        logger.debug(f"ダウンロード完了: {dest_path.name} ({format_file_size(file_size)})")
        
        return True
    
    except Exception as e:
      logger.error(f"ファイルダウンロードエラー: {e}")
      return False
  
  def _show_progress(self, current: int, total: int, post_id: int, message: str) -> None:
    """
    進捗を表示する
    
    Args:
      current: 現在の位置
      total: 総件数
      post_id: 投稿ID
      message: メッセージ
    """
    percentage = (current / total * 100) if total > 0 else 0
    print(f"進捗: {current}/{total} ({percentage:.1f}%) - ID: {post_id} - {message}")


async def download_query(
  api: GelbooruAPI,
  database: Database,
  query: str,
  output_dir: Path,
  delay_ms: int = 1000,
  max_retries: int = 3,
  retry_delay: float = 1.0,
  dry_run: bool = False
) -> DownloadResult:
  """
  クエリを使って検索・ダウンロードする（便利関数）
  
  Args:
    api: Gelbooru APIクライアント
    database: データベース
    query: 検索クエリ
    output_dir: 出力ディレクトリ
    delay_ms: リクエスト間隔（ミリ秒）
    max_retries: リトライ回数
    retry_delay: リトライ間隔（秒）
    dry_run: ドライランモード
  
  Returns:
    ダウンロード結果
  """
  # 検索実行
  logger.info(f"検索クエリ: {query}")
  
  try:
    posts = await api.search(query, delay_ms=delay_ms)
  except GelbooruAPIError as e:
    logger.error(f"検索に失敗しました: {e}")
    return DownloadResult()
  
  if not posts:
    logger.info("検索結果が0件でした")
    return DownloadResult()
  
  logger.info(f"検索結果: {len(posts)}件")
  
  # ダウンロード
  downloader = Downloader(api, database, output_dir, max_retries, retry_delay)
  result = await downloader.download_posts(posts, dry_run=dry_run)
  
  # 結果表示
  logger.info(f"ダウンロード完了: {result}")
  
  if result.failed > 0:
    logger.warning(f"失敗した投稿ID: {result.failed_ids}")
  
  return result


# スタンドアロン使用例
async def main():
  """使用例"""
  from .utils import Config, setup_logging
  
  # ログ設定
  setup_logging(log_level="INFO")
  
  # 設定読み込み
  config = Config()
  
  # API初期化
  api = GelbooruAPI(
    api_key=config.get('api_key'),
    user_id=config.get('user_id'),
    display_all_site_content=config.get('display_all_site_content', True)
  )
  
  # データベース初期化
  db_path = Path(config.get('output_dir')) / 'download.db'
  database = Database(db_path)
  
  # 出力ディレクトリ
  output_dir = Path(config.get('output_dir')) / 'test_download'
  
  async with api:
    result = await download_query(
      api=api,
      database=database,
      query="tags=blonde_hair&limit=5",
      output_dir=output_dir,
      delay_ms=config.get('delay_ms', 1000),
      dry_run=False
    )
    
    print(f"\n最終結果: {result}")
  
  database.close()


if __name__ == "__main__":
  asyncio.run(main())
