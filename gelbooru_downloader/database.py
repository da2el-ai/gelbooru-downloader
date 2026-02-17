"""データベース管理（SQLite）"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class Database:
  """ダウンロード履歴管理用データベース"""
  
  def __init__(self, db_path: Path):
    """
    データベースを初期化する
    
    Args:
      db_path: データベースファイルのパス
    """
    self.db_path = db_path
    self.conn: Optional[sqlite3.Connection] = None
    self._init_database()
  
  def _init_database(self) -> None:
    """データベースを初期化し、必要なテーブルを作成する"""
    # 親ディレクトリが存在しない場合は作成
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    self.conn = sqlite3.connect(str(self.db_path))
    self.conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能にする
    
    cursor = self.conn.cursor()
    
    # downloaded_posts テーブル作成
    cursor.execute("""
      CREATE TABLE IF NOT EXISTS downloaded_posts (
        post_id INTEGER PRIMARY KEY,
        downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    """)
    
    # インデックス作成
    cursor.execute("""
      CREATE INDEX IF NOT EXISTS idx_downloaded_at 
      ON downloaded_posts(downloaded_at)
    """)
    
    self.conn.commit()
    logger.debug(f"データベースを初期化しました: {self.db_path}")
  
  def is_downloaded(self, post_id: int) -> bool:
    """
    投稿がダウンロード済みかチェックする
    
    Args:
      post_id: 投稿ID
    
    Returns:
      ダウンロード済みの場合True
    """
    cursor = self.conn.cursor()
    cursor.execute(
      "SELECT 1 FROM downloaded_posts WHERE post_id = ?",
      (post_id,)
    )
    return cursor.fetchone() is not None
  
  def mark_as_downloaded(self, post_id: int) -> None:
    """
    投稿をダウンロード済みとしてマークする
    
    Args:
      post_id: 投稿ID
    """
    cursor = self.conn.cursor()
    cursor.execute(
      "INSERT OR IGNORE INTO downloaded_posts (post_id) VALUES (?)",
      (post_id,)
    )
    self.conn.commit()
    logger.debug(f"投稿 {post_id} をダウンロード済みとしてマークしました")
  
  def mark_multiple_as_downloaded(self, post_ids: List[int]) -> None:
    """
    複数の投稿を一括でダウンロード済みとしてマークする
    
    Args:
      post_ids: 投稿IDのリスト
    """
    cursor = self.conn.cursor()
    cursor.executemany(
      "INSERT OR IGNORE INTO downloaded_posts (post_id) VALUES (?)",
      [(post_id,) for post_id in post_ids]
    )
    self.conn.commit()
    logger.debug(f"{len(post_ids)} 件の投稿をダウンロード済みとしてマークしました")
  
  def get_total_count(self) -> int:
    """
    ダウンロード済み投稿の総数を取得する
    
    Returns:
      総ダウンロード数
    """
    cursor = self.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM downloaded_posts")
    return cursor.fetchone()[0]
  
  def get_first_download_time(self) -> Optional[datetime]:
    """
    最初のダウンロード日時を取得する
    
    Returns:
      最初のダウンロード日時（データがない場合はNone）
    """
    cursor = self.conn.cursor()
    cursor.execute(
      "SELECT downloaded_at FROM downloaded_posts ORDER BY downloaded_at ASC LIMIT 1"
    )
    row = cursor.fetchone()
    if row:
      return datetime.fromisoformat(row[0])
    return None
  
  def get_last_download_time(self) -> Optional[datetime]:
    """
    最後のダウンロード日時を取得する
    
    Returns:
      最後のダウンロード日時（データがない場合はNone）
    """
    cursor = self.conn.cursor()
    cursor.execute(
      "SELECT downloaded_at FROM downloaded_posts ORDER BY downloaded_at DESC LIMIT 1"
    )
    row = cursor.fetchone()
    if row:
      return datetime.fromisoformat(row[0])
    return None
  
  def get_recent_downloads(self, limit: int = 10) -> List[Tuple[int, datetime]]:
    """
    最近のダウンロード履歴を取得する
    
    Args:
      limit: 取得件数
    
    Returns:
      (post_id, downloaded_at) のタプルのリスト
    """
    cursor = self.conn.cursor()
    cursor.execute(
      "SELECT post_id, downloaded_at FROM downloaded_posts ORDER BY downloaded_at DESC LIMIT ?",
      (limit,)
    )
    
    results = []
    for row in cursor.fetchall():
      post_id = row[0]
      downloaded_at = datetime.fromisoformat(row[1])
      results.append((post_id, downloaded_at))
    
    return results
  
  def get_statistics(self) -> dict:
    """
    データベースの統計情報を取得する
    
    Returns:
      統計情報の辞書
    """
    return {
      'total_count': self.get_total_count(),
      'first_download': self.get_first_download_time(),
      'last_download': self.get_last_download_time(),
      'recent_downloads': self.get_recent_downloads(10)
    }
  
  def close(self) -> None:
    """データベース接続を閉じる"""
    if self.conn:
      self.conn.close()
      logger.debug("データベース接続を閉じました")
  
  def __enter__(self):
    """コンテキストマネージャー: 開始"""
    return self
  
  def __exit__(self, exc_type, exc_val, exc_tb):
    """コンテキストマネージャー: 終了"""
    self.close()


def print_statistics(db_path: Path) -> None:
  """
  データベースの統計情報を表示する
  
  Args:
    db_path: データベースファイルのパス
  """
  with Database(db_path) as db:
    stats = db.get_statistics()
    
    print("=" * 50)
    print("ダウンロード統計")
    print("=" * 50)
    
    print(f"総ダウンロード数: {stats['total_count']:,}件")
    
    if stats['first_download']:
      print(f"初回ダウンロード: {stats['first_download'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    if stats['last_download']:
      print(f"最終ダウンロード: {stats['last_download'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    if stats['recent_downloads']:
      print(f"\n最近のダウンロード（最大10件）:")
      for post_id, downloaded_at in stats['recent_downloads']:
        print(f"  [{downloaded_at.strftime('%Y-%m-%d %H:%M:%S')}] ID: {post_id}")
    
    print("=" * 50)


# スタンドアロン使用例
if __name__ == "__main__":
  # ログ設定
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )
  
  # テスト用データベース
  test_db_path = Path("test_download.db")
  
  with Database(test_db_path) as db:
    # ダウンロード済みとしてマーク
    db.mark_as_downloaded(12345)
    db.mark_as_downloaded(67890)
    
    # チェック
    print(f"12345 is downloaded: {db.is_downloaded(12345)}")
    print(f"99999 is downloaded: {db.is_downloaded(99999)}")
    
    # 統計表示
    print_statistics(test_db_path)
