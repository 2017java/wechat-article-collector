import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_invalid_url_returns_none():
    from core.fetcher import fetch_article
    result = fetch_article("https://not-weixin.com/article")
    assert result is None


def test_non_wechat_returns_none():
    from core.fetcher import fetch_article
    result = fetch_article("https://www.baidu.com")
    assert result is None


def test_is_wechat_url_valid():
    from core.fetcher import is_wechat_url
    assert is_wechat_url("https://mp.weixin.qq.com/s/abc123")
    assert is_wechat_url("https://mp.weixin.qq.com/s?__biz=abc&mid=123")


def test_is_wechat_url_invalid():
    from core.fetcher import is_wechat_url
    assert not is_wechat_url("https://example.com/s/abc")
    assert not is_wechat_url("https://weixin.qq.com/s/abc")
    assert not is_wechat_url("http://mp.weixin.qq.com/s/abc")  # http 不匹配


def test_sanitize_filename():
    from core.image_downloader import sanitize_filename
    result = sanitize_filename("path/to/file.jpg")
    assert "/" not in result
    result2 = sanitize_filename("file.jpg?wx_fmt=jpeg")
    assert "?" not in result2
