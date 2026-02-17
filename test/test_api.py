"""Test API"""

import pytest
from gelbooru_downloader.api import GelbooruAPI


@pytest.fixture
async def api():
  """テスト用APIクライアント"""
  api = GelbooruAPI()
  await api.start_session()
  yield api
  await api.close_session()


def test_api_init():
  """API初期化"""
  api = GelbooruAPI(
    api_key="test_key",
    user_id="test_user",
    display_all_site_content=True
  )
  
  assert api.api_key == "test_key"
  assert api.user_id == "test_user"
  assert api.display_all_site_content is True


def test_build_params():
  """パラメータ構築"""
  api = GelbooruAPI()
  
  query = "tags=blonde_hair&limit=10"
  params = api._build_params(query)
  
  assert params['page'] == 'dapi'
  assert params['s'] == 'post'
  assert params['q'] == 'index'
  assert params['json'] == '1'
  assert params['tags'] == 'blonde_hair'
  assert params['limit'] == '10'


@pytest.mark.asyncio
async def test_session_context_manager():
  """セッションのコンテキストマネージャー"""
  async with GelbooruAPI() as api:
    assert api.session is not None
    assert not api.session.closed
  
  # コンテキストを抜けた後
  assert api.session.closed


# 注意: 以下のテストは実際のAPIを呼び出すため、
# 通常のテストでは実行しない（統合テストとして別途実行）

@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_real_api():
  """実際のAPI検索（統合テスト）"""
  async with GelbooruAPI() as api:
    posts = await api.search("tags=blonde_hair&limit=5")
    
    assert isinstance(posts, list)
    # 結果があれば検証
    if posts:
      assert 'id' in posts[0]
      assert 'tags' in posts[0]
