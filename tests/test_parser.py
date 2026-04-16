import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.parser import parse_article

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_article.html")


def _load_fixture() -> str:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return f.read()


def test_parse_returns_required_fields():
    html = _load_fixture()
    result = parse_article(html, url="https://mp.weixin.qq.com/s/test")
    assert result is not None
    assert result["title"] == "测试文章标题：微信抓取验证"
    assert result["source"] == "测试公众号"
    assert result["author"] == "张三"
    assert result["date"] == "2026-03-29"
    assert result["url"] == "https://mp.weixin.qq.com/s/test"
    assert isinstance(result["images"], list)
    assert result["content_html"]


def test_parse_extracts_images():
    html = _load_fixture()
    result = parse_article(html, url="https://mp.weixin.qq.com/s/test")
    assert result is not None
    # 应该发现 2 张 mmbiz.qpic.cn 图片
    assert len(result["images"]) == 2
    assert all("mmbiz.qpic.cn" in img for img in result["images"])


def test_parse_deduplicates_images():
    """相同图片 URL 不应重复。"""
    html = """<html><body>
    <div id="js_content">
      <img data-src="https://mmbiz.qpic.cn/test/001"/>
      <img data-src="https://mmbiz.qpic.cn/test/001"/>
    </div></body></html>"""
    result = parse_article(html, url="")
    assert result is not None
    assert len(result["images"]) == 1


def test_parse_missing_content_returns_none():
    """缺少 #js_content 时返回 None。"""
    result = parse_article("<html><body><p>无正文</p></body></html>", url="")
    assert result is None


def test_parse_no_images():
    """无图文章应返回空 images 列表。"""
    html = """<html><body>
    <h1 class="rich_media_title">无图文章</h1>
    <div id="js_name">测试号</div>
    <div id="js_content"><p>纯文字内容</p></div>
    </body></html>"""
    result = parse_article(html, url="")
    assert result is not None
    assert result["images"] == []
    assert result["title"] == "无图文章"
