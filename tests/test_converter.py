import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.markdown_converter import convert_to_markdown

ARTICLE = {
    "title": "测试文章",
    "author": "张三",
    "source": "测试公众号",
    "date": "2026-03-29",
    "url": "https://mp.weixin.qq.com/s/test123",
    "content_html": (
        '<div id="js_content">'
        "<p>这是正文第一段。</p>"
        '<img data-src="https://mmbiz.qpic.cn/test.jpg" />'
        "<p>这是正文第二段。</p>"
        "<blockquote>引用内容</blockquote>"
        "</div>"
    ),
    "images": ["https://mmbiz.qpic.cn/test.jpg"],
}

URL_MAP = {"https://mmbiz.qpic.cn/test.jpg": "images/001.jpg"}


def test_frontmatter_present():
    md = convert_to_markdown(ARTICLE, url_to_local=URL_MAP)
    assert md.startswith("---")
    assert "title:" in md
    assert "author:" in md
    assert "source:" in md
    assert "tags:" in md
    assert "- wechat" in md


def test_frontmatter_contains_source_tag():
    md = convert_to_markdown(ARTICLE, url_to_local=URL_MAP)
    assert "测试公众号" in md


def test_title_heading_present():
    md = convert_to_markdown(ARTICLE, url_to_local=URL_MAP)
    assert "# 测试文章" in md


def test_image_url_replaced():
    md = convert_to_markdown(ARTICLE, url_to_local=URL_MAP)
    assert "images/001.jpg" in md
    assert "mmbiz.qpic.cn" not in md


def test_content_present():
    md = convert_to_markdown(ARTICLE, url_to_local=URL_MAP)
    assert "这是正文第一段" in md
    assert "这是正文第二段" in md


def test_no_images_article():
    """无图文章正常转换，不报错。"""
    article = {**ARTICLE, "content_html": "<div><p>纯文字</p></div>", "images": []}
    md = convert_to_markdown(article, url_to_local={})
    assert "纯文字" in md
    assert "---" in md


def test_special_chars_in_title():
    """标题含特殊字符（双引号等）不会破坏 frontmatter。"""
    article = {**ARTICLE, "title": '含"引号"的标题'}
    md = convert_to_markdown(article, url_to_local={})
    assert "---" in md
    assert "含" in md
