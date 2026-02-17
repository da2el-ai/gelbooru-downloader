"""Test database"""

import pytest
from pathlib import Path
from gelbooru_downloader.database import Database


@pytest.fixture
def test_db(tmp_path):
  """テスト用データベース"""
  db_path = tmp_path / "test.db"
  db = Database(db_path)
  yield db
  db.close()


def test_database_init(tmp_path):
  """データベース初期化"""
  db_path = tmp_path / "test.db"
  db = Database(db_path)
  
  assert db_path.exists()
  db.close()


def test_mark_as_downloaded(test_db):
  """ダウンロード済みマーク"""
  post_id = 12345
  
  # マーク前
  assert not test_db.is_downloaded(post_id)
  
  # マーク
  test_db.mark_as_downloaded(post_id)
  
  # マーク後
  assert test_db.is_downloaded(post_id)


def test_mark_multiple_as_downloaded(test_db):
  """複数の投稿を一括マーク"""
  post_ids = [1, 2, 3, 4, 5]
  
  test_db.mark_multiple_as_downloaded(post_ids)
  
  for post_id in post_ids:
    assert test_db.is_downloaded(post_id)


def test_get_total_count(test_db):
  """総ダウンロード数の取得"""
  assert test_db.get_total_count() == 0
  
  test_db.mark_as_downloaded(1)
  test_db.mark_as_downloaded(2)
  
  assert test_db.get_total_count() == 2


def test_get_statistics(test_db):
  """統計情報の取得"""
  # 空の状態
  stats = test_db.get_statistics()
  assert stats['total_count'] == 0
  assert stats['first_download'] is None
  assert stats['last_download'] is None
  
  # データを追加
  test_db.mark_as_downloaded(1)
  test_db.mark_as_downloaded(2)
  
  stats = test_db.get_statistics()
  assert stats['total_count'] == 2
  assert stats['first_download'] is not None
  assert stats['last_download'] is not None
