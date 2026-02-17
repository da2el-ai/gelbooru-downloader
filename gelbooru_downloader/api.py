"""Gelbooru API ラッパー

このモジュールは他のスクリプトから独立して利用可能です。
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode, parse_qs
import aiohttp

logger = logging.getLogger(__name__)


class GelbooruAPIError(Exception):
  """Gelbooru API関連のエラー"""
  pass


class GelbooruAPI:
  """Gelbooru API クライアント"""
  
  BASE_URL = "https://gelbooru.com/index.php"
  DEFAULT_PARAMS = {
    "page": "dapi",
    "s": "post",
    "q": "index",
    "json": "1"
  }
  MAX_LIMIT_PER_REQUEST = 100
  
  def __init__(
    self,
    api_key: Optional[str] = None,
    user_id: Optional[str] = None,
    display_all_site_content: bool = True
  ):
    """
    Gelbooru APIクライアントを初期化する
    
    Args:
      api_key: API Key（オプション、レート制限緩和）
      user_id: User ID（オプション、レート制限緩和）
      display_all_site_content: 全コンテンツ表示を有効化（fringeBenefits cookie）
    """
    self.api_key = api_key
    self.user_id = user_id
    self.display_all_site_content = display_all_site_content
    self.session: Optional[aiohttp.ClientSession] = None
  
  async def __aenter__(self):
    """コンテキストマネージャー: セッション開始"""
    await self.start_session()
    return self
  
  async def __aexit__(self, exc_type, exc_val, exc_tb):
    """コンテキストマネージャー: セッション終了"""
    await self.close_session()
  
  async def start_session(self) -> None:
    """HTTPセッションを開始する"""
    if self.session is None or self.session.closed:
      # Cookie設定
      cookies = {}
      if self.display_all_site_content:
        cookies['fringeBenefits'] = 'yup'
      
      # User-Agentヘッダーを設定
      headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; gelbooru-downloader/0.1.0)'
      }
      
      self.session = aiohttp.ClientSession(cookies=cookies, headers=headers)
      logger.debug("HTTPセッションを開始しました")
  
  async def close_session(self) -> None:
    """HTTPセッションを閉じる"""
    if self.session and not self.session.closed:
      await self.session.close()
      logger.debug("HTTPセッションを閉じました")
  
  def _build_params(self, query_string: str) -> Dict[str, str]:
    """
    クエリ文字列からAPIパラメータを構築する
    
    Args:
      query_string: URLクエリパラメータ形式の検索条件
    
    Returns:
      APIリクエスト用のパラメータ辞書
    """
    # デフォルトパラメータをコピー
    params = self.DEFAULT_PARAMS.copy()
    
    # API Key/User IDを追加
    if self.api_key:
      params['api_key'] = self.api_key
    if self.user_id:
      params['user_id'] = self.user_id
    
    # クエリ文字列をパース
    if query_string.startswith('?'):
      query_string = query_string[1:]
    
    user_params = parse_qs(query_string, keep_blank_values=True)
    
    # パラメータをマージ（値がリストの場合は最初の要素を取得）
    for key, value in user_params.items():
      params[key] = value[0] if isinstance(value, list) else value
    
    return params
  
  async def search(
    self,
    query_string: str,
    delay_ms: int = 1000
  ) -> List[Dict[str, Any]]:
    """
    検索を実行する（ページネーション自動処理）
    
    Args:
      query_string: URLクエリパラメータ形式の検索条件
      delay_ms: リクエスト間隔（ミリ秒）
    
    Returns:
      投稿データのリスト
    
    Raises:
      GelbooruAPIError: API呼び出しに失敗した場合
    """
    if not self.session or self.session.closed:
      raise GelbooruAPIError("セッションが開始されていません。start_session()を呼び出してください")
    
    params = self._build_params(query_string)
    
    # limitを取得（指定がない場合は100）
    limit = int(params.get('limit', self.MAX_LIMIT_PER_REQUEST))
    
    # ページネーションが必要かチェック
    if limit <= self.MAX_LIMIT_PER_REQUEST:
      # 単一リクエストで取得可能
      params['limit'] = str(limit)
      return await self._fetch_page(params)
    
    # 複数ページに分割して取得
    all_posts = []
    total_pages = (limit + self.MAX_LIMIT_PER_REQUEST - 1) // self.MAX_LIMIT_PER_REQUEST
    
    logger.info(f"ページネーション: {limit}件を{total_pages}ページに分割して取得します")
    
    for page in range(total_pages):
      page_params = params.copy()
      page_params['limit'] = str(self.MAX_LIMIT_PER_REQUEST)
      page_params['pid'] = str(page)
      
      logger.debug(f"ページ {page + 1}/{total_pages} を取得中...")
      
      try:
        posts = await self._fetch_page(page_params)
        all_posts.extend(posts)
        
        # 取得件数が0の場合は終了（これ以上データがない）
        if not posts:
          logger.info(f"ページ {page + 1} でデータが空になりました。取得を終了します")
          break
        
        # 次のページの前に待機
        if page < total_pages - 1:
          await asyncio.sleep(delay_ms / 1000.0)
      
      except GelbooruAPIError as e:
        logger.error(f"ページ {page + 1} の取得に失敗しました: {e}")
        # エラーが発生しても、既に取得したデータは返す
        break
    
    logger.info(f"合計 {len(all_posts)} 件の投稿を取得しました")
    return all_posts[:limit]  # 指定された件数まで切り詰め
  
  async def _fetch_page(self, params: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    単一ページを取得する
    
    Args:
      params: APIリクエストパラメータ
    
    Returns:
      投稿データのリスト
    
    Raises:
      GelbooruAPIError: API呼び出しに失敗した場合
    """
    url = f"{self.BASE_URL}?{urlencode(params)}"
    logger.debug(f"APIリクエストURL: {url}")
    
    try:
      async with self.session.get(url) as response:
        # ステータスコードチェック
        if response.status != 200:
          error_text = await response.text()
          logger.error(f"APIエラーレスポンス: {error_text[:500]}")
          raise GelbooruAPIError(
            f"APIリクエストが失敗しました: HTTP {response.status}\n{error_text}"
          )
        
        # JSONレスポンスをパース
        data = await response.json()
        
        # JSONレスポンスをパース
        data = await response.json()
        
        # レスポンス形式チェック
        if isinstance(data, dict):
          # {"post": [...]} 形式
          posts = data.get('post', [])
        elif isinstance(data, list):
          # [...] 形式
          posts = data
        else:
          raise GelbooruAPIError(f"予期しないレスポンス形式: {type(data)}")
        
        # デバッグ: 最初の投稿のキーを確認
        if posts and logger.isEnabledFor(logging.DEBUG):
          first_post = posts[0]
          logger.debug(f"投稿のキー: {list(first_post.keys())[:20]}")
          for key in ['file_url', 'sample_url', 'preview_url', 'image', 'directory']:
            if key in first_post:
              logger.debug(f"{key}: {first_post.get(key)}")
        
        logger.debug(f"{len(posts)} 件の投稿を取得しました")
        return posts
    
    except aiohttp.ClientError as e:
      raise GelbooruAPIError(f"ネットワークエラー: {e}")
    except Exception as e:
      raise GelbooruAPIError(f"予期しないエラー: {e}")
  
  async def get_post_info(self, post_id: int) -> Optional[Dict[str, Any]]:
    """
    特定の投稿情報を取得する
    
    Args:
      post_id: 投稿ID
    
    Returns:
      投稿データ（存在しない場合はNone）
    """
    if not self.session or self.session.closed:
      raise GelbooruAPIError("セッションが開始されていません")
    
    params = self.DEFAULT_PARAMS.copy()
    params['id'] = str(post_id)
    
    if self.api_key:
      params['api_key'] = self.api_key
    if self.user_id:
      params['user_id'] = self.user_id
    
    try:
      posts = await self._fetch_page(params)
      return posts[0] if posts else None
    except GelbooruAPIError:
      return None


# スタンドアロン使用例
async def main():
  """使用例"""
  # APIクライアントを初期化
  api = GelbooruAPI(
    api_key="your_api_key_here",  # オプション
    user_id="your_user_id_here",  # オプション
    display_all_site_content=True
  )
  
  async with api:
    # 検索実行
    posts = await api.search("tags=blonde_hair&limit=10")
    
    # 結果を表示
    for post in posts:
      print(f"ID: {post.get('id')}")
      print(f"Tags: {post.get('tags')}")
      print(f"File URL: {post.get('file_url')}")
      print("-" * 50)


if __name__ == "__main__":
  # ログ設定
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )
  
  # 実行
  asyncio.run(main())
