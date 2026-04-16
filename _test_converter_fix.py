"""
测试修复后的 converter 和前端逻辑
"""
from core.converter import get_article_id, generate_clean_html

# ── 测试1：隐藏元素被移除 ──────────────────────────────────────────
article = {
    "title": "测试文章",
    "author": "作者",
    "source": "公众号",
    "date": "2026-04-02",
    "url": "https://mp.weixin.qq.com/s/test123",
    "content_html": """
<div id="js_content">
  <p style="display:none">这段不应显示</p>
  <p style="visibility:hidden">这段也不应显示</p>
  <section>
    <p>这是正常正文内容，应该显示</p>
    <p><strong>加粗文字</strong>也应该显示</p>
  </section>
  <img data-src="https://mmbiz.qpic.cn/img1.jpg?wx_fmt=jpeg" />
  <script>alert('xss')</script>
</div>
""",
    "images": [],
}

aid = get_article_id(article["url"])
html, img_map = generate_clean_html(article, aid, "http://118.145.228.33:8686")

print("=== 测试1：隐藏元素移除 ===")
assert "display:none" not in html, "FAIL: display:none 未被移除"
assert "visibility:hidden" not in html, "FAIL: visibility:hidden 未被移除"
assert "这段不应显示" not in html, "FAIL: 隐藏文本仍在 HTML 中"
print("✓ 隐藏元素已移除")

print("\n=== 测试2：正文内容保留 ===")
assert "这是正常正文内容" in html, "FAIL: 正常文本丢失"
assert "加粗文字" in html, "FAIL: strong 标签内容丢失"
print("✓ 正文内容正常保留")

print("\n=== 测试3：XSS 防护 ===")
assert "<script>" not in html, "FAIL: script 标签未被移除"
assert "alert(" not in html, "FAIL: XSS 内容未被移除"
print("✓ script 标签已移除")

print("\n=== 测试4：图片代理路径 ===")
assert len(img_map) == 1, f"FAIL: img_map 应有1项，实际 {len(img_map)}"
assert "img_001.jpg" in img_map.values(), "FAIL: 图片文件名生成错误"
assert f"http://118.145.228.33:8686/article/{aid}/images/img_001.jpg" in html, "FAIL: 代理 URL 未注入"
assert "data-src" not in html, "FAIL: data-src 未被替换"
print(f"✓ 图片代理路径正确: http://118.145.228.33:8686/article/{aid}/images/img_001.jpg")

print("\n=== 测试5：base_url 为空时使用相对路径 ===")
html2, img_map2 = generate_clean_html(article, aid, "")
assert f"/article/{aid}/images/img_001.jpg" in html2, "FAIL: 空 base_url 时相对路径错误"
print(f"✓ 空 base_url 时使用相对路径: /article/{aid}/images/img_001.jpg")

print("\n=== 测试6：完整 HTML 结构 ===")
assert "<!DOCTYPE html>" in html, "FAIL: 缺少 DOCTYPE"
assert '<meta charset="UTF-8"' in html, "FAIL: 缺少 charset"
assert "<title>测试文章</title>" in html, "FAIL: title 错误"
assert "visibility: visible !important" in html, "FAIL: 覆盖样式缺失"
print("✓ HTML 结构完整")

print("\n✅ 所有测试通过!")
