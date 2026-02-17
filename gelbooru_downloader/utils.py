"""ユーティリティ関数"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import parse_qs, urlencode

logger = logging.getLogger(__name__)


class Config:
  """設定管理クラス"""
  
  DEFAULT_CONFIG = {
    "api_key": "",
    "user_id": "",
    "display_all_site_content": True,
    "output_dir": "./download",
    "delay_ms": 1000,
    "max_retries": 3,
    "retry_delay": 1.0,
    "default_exclude_tags": ["comic", "3d", "photo", "cosplay"],
    "default_limit": 100
  }
  
  def __init__(self, config_path: Optional[Path] = None):
    """
    設定ファイルを読み込む
    
    Args:
      config_path: 設定ファイルのパス（Noneの場合はデフォルト設定を使用）
    """
    self.config = self.DEFAULT_CONFIG.copy()
    
    if config_path and config_path.exists():
      try:
        with open(config_path, 'r', encoding='utf-8') as f:
          user_config = json.load(f)
          self.config.update(user_config)
          logger.info(f"設定ファイルを読み込みました: {config_path}")
      except Exception as e:
        logger.warning(f"設定ファイルの読み込みに失敗しました: {e}")
        logger.info("デフォルト設定を使用します")
    else:
      logger.info("設定ファイルが見つかりません。デフォルト設定を使用します")
  
  def get(self, key: str, default: Any = None) -> Any:
    """設定値を取得"""
    return self.config.get(key, default)
  
  def __getitem__(self, key: str) -> Any:
    """設定値を取得（辞書アクセス）"""
    return self.config[key]
  
  @classmethod
  def create_sample_config(cls, path: Path) -> None:
    """サンプル設定ファイルを作成"""
    with open(path, 'w', encoding='utf-8') as f:
      json.dump(cls.DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    logger.info(f"サンプル設定ファイルを作成しました: {path}")


def parse_query_string(query: str) -> Dict[str, List[str]]:
  """
  URLクエリパラメータをパースする
  
  Args:
    query: クエリ文字列（例: "tags=blonde_hair&limit=100"）
  
  Returns:
    パース済みクエリ辞書
  """
  # クエリ文字列の先頭に?がある場合は削除
  if query.startswith('?'):
    query = query[1:]
  
  parsed = parse_qs(query, keep_blank_values=True)
  return parsed


def apply_default_exclude_tags(query: str, exclude_tags: List[str]) -> str:
  """
  デフォルト除外タグをクエリに追加する
  
  Args:
    query: 元のクエリ文字列
    exclude_tags: 除外するタグのリスト
  
  Returns:
    除外タグが追加されたクエリ文字列
  """
  if not exclude_tags:
    return query
  
  parsed = parse_query_string(query)
  
  # tagsパラメータを取得
  tags = parsed.get('tags', [''])[0]
  
  # 除外タグを追加（既に含まれている場合はスキップ）
  for tag in exclude_tags:
    exclude_tag = f"-{tag}"
    if exclude_tag not in tags:
      if tags:
        tags += f"+{exclude_tag}"
      else:
        tags = exclude_tag
  
  # tagsを更新
  parsed['tags'] = [tags]
  
  # クエリ文字列を再構築（+記号を保持するため手動で構築）
  result_parts = []
  for key, values in parsed.items():
    for value in values:
      result_parts.append(f"{key}={value}")
  
  return "&".join(result_parts)


def generate_output_dir_name(query: str, max_length: int = 50) -> str:
  """
  出力ディレクトリ名を生成する
  
  Args:
    query: クエリ文字列
    max_length: クエリ部分の最大長
  
  Returns:
    タイムスタンプ付きディレクトリ名
  """
  timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
  
  # クエリ文字列を整形
  query_part = query.replace("&", "&").replace("=", "=")
  
  # 長すぎる場合は切り詰め
  if len(query_part) > max_length:
    query_part = query_part[:max_length] + "..."
  
  return f"{timestamp}_{query_part}"


def load_query_list(file_path: Path) -> List[str]:
  """
  検索クエリリストファイルを読み込む
  
  Args:
    file_path: クエリリストファイルのパス
  
  Returns:
    クエリ文字列のリスト
  """
  queries = []
  
  if not file_path.exists():
    logger.error(f"クエリファイルが見つかりません: {file_path}")
    return queries
  
  with open(file_path, 'r', encoding='utf-8') as f:
    for line_num, line in enumerate(f, start=1):
      line = line.strip()
      
      # 空行やコメント行はスキップ
      if not line or line.startswith('#'):
        continue
      
      queries.append(line)
      logger.debug(f"クエリ {line_num}: {line}")
  
  logger.info(f"{len(queries)}個のクエリを読み込みました")
  return queries


def format_tags_for_caption(tags: str) -> str:
  """
  タグをWD14形式のキャプションに変換する
  
  Args:
    tags: スペース区切りのタグ文字列
  
  Returns:
    カンマ+スペース区切りのキャプション文字列
  """
  # スペース区切りを ", " 区切りに変換
  return tags.replace(' ', ', ')


def format_file_size(size_bytes: int) -> str:
  """
  ファイルサイズを人間が読みやすい形式に変換する
  
  Args:
    size_bytes: バイト数
  
  Returns:
    フォーマットされたサイズ文字列
  """
  for unit in ['B', 'KB', 'MB', 'GB']:
    if size_bytes < 1024.0:
      return f"{size_bytes:.2f} {unit}"
    size_bytes /= 1024.0
  return f"{size_bytes:.2f} TB"


def setup_logging(log_level: str = "INFO", log_file: Optional[Path] = None) -> None:
  """
  ロギングをセットアップする
  
  Args:
    log_level: ログレベル（DEBUG/INFO/WARNING/ERROR）
    log_file: ログファイルのパス（Noneの場合はコンソールのみ）
  """
  level = getattr(logging, log_level.upper(), logging.INFO)
  
  # ログフォーマット
  formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
  )
  
  # ルートロガーの設定
  root_logger = logging.getLogger()
  root_logger.setLevel(level)
  
  # コンソールハンドラ
  console_handler = logging.StreamHandler()
  console_handler.setLevel(level)
  console_handler.setFormatter(formatter)
  root_logger.addHandler(console_handler)
  
  # ファイルハンドラ（指定された場合）
  if log_file:
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    logger.info(f"ログファイル: {log_file}")
