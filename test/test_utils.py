"""Test utilities"""

import pytest
from pathlib import Path
from gelbooru_downloader.utils import (
  Config,
  parse_query_string,
  apply_default_exclude_tags,
  format_tags_for_caption,
  generate_output_dir_name
)


def test_parse_query_string():
  """クエリ文字列のパース"""
  query = "tags=blonde_hair&limit=100"
  parsed = parse_query_string(query)
  
  assert 'tags' in parsed
  assert 'limit' in parsed
  assert parsed['tags'][0] == 'blonde_hair'
  assert parsed['limit'][0] == '100'


def test_apply_default_exclude_tags():
  """デフォルト除外タグの適用"""
  query = "tags=blonde_hair&limit=100"
  exclude_tags = ["comic", "3d"]
  
  result = apply_default_exclude_tags(query, exclude_tags)
  
  assert "-comic" in result
  assert "-3d" in result


def test_format_tags_for_caption():
  """タグのキャプション形式変換"""
  tags = "1girl solo blonde_hair blue_eyes"
  caption = format_tags_for_caption(tags)
  
  assert caption == "1girl, solo, blonde_hair, blue_eyes"


def test_generate_output_dir_name():
  """出力ディレクトリ名の生成"""
  query = "tags=blonde_hair&limit=100"
  dir_name = generate_output_dir_name(query)
  
  # タイムスタンプが含まれている
  assert "_tags=blonde_hair" in dir_name
  # 日付形式が含まれている（YYYYMMDD）
  assert len(dir_name.split("_")[0]) == 15  # YYYYMMDD-HHMMSS


def test_config_default():
  """デフォルト設定"""
  config = Config()
  
  assert config.get('delay_ms') == 1000
  assert config.get('max_retries') == 3
  assert 'default_exclude_tags' in config.config


def test_config_create_sample(tmp_path):
  """サンプル設定ファイルの作成"""
  config_path = tmp_path / "config.json"
  Config.create_sample_config(config_path)
  
  assert config_path.exists()
  
  # 読み込めることを確認
  config = Config(config_path)
  assert config.get('delay_ms') == 1000
