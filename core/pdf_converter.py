import re
import tempfile
from pathlib import Path


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符，防止 XSS 注入到模板。"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _strip_hidden_style(content_html: str) -> str:
    """
    移除微信 JS 注入的隐藏样式（visibility:hidden / opacity:0），
    使 PDF 渲染时内容可见。
    """
    import re
    # 移除 visibility: hidden
    content_html = re.sub(r'visibility\s*:\s*hidden\s*;?', '', content_html, flags=re.IGNORECASE)
    # 移除 opacity: 0
    content_html = re.sub(r'opacity\s*:\s*0\s*;?', '', content_html, flags=re.IGNORECASE)
    return content_html


def _replace_image_urls_for_pdf(
    content_html: str, url_to_local: dict[str, str], images_dir: Path
) -> str:
    """
    将 HTML 中的图片 URL 替换为 base64 data URI，直接嵌入图片数据。
    避免 Playwright headless shell 因安全沙箱无法加载 file:// 本地图片的问题。
    下载失败的图片保留原始网络 URL。
    """
    import base64, mimetypes

    for original_url, local_rel in url_to_local.items():
        if local_rel.startswith("images/"):
            local_abs = (images_dir.parent / local_rel).resolve()
            if local_abs.exists():
                mime_type, _ = mimetypes.guess_type(str(local_abs))
                mime_type = mime_type or "image/jpeg"
                b64 = base64.b64encode(local_abs.read_bytes()).decode()
                replacement = f"data:{mime_type};base64,{b64}"
            else:
                replacement = original_url
        else:
            # 图片下载失败，保留原始网络 URL
            replacement = local_rel

        # BeautifulSoup 序列化时会将 URL 中的 & 编码为 &amp;，需同时处理两种形式
        encoded_url = original_url.replace("&", "&amp;")
        for url_variant in (original_url, encoded_url):
            content_html = content_html.replace(
                f'data-src="{url_variant}"', f'src="{replacement}"'
            )
            content_html = content_html.replace(
                f'src="{url_variant}"', f'src="{replacement}"'
            )
    return content_html


def _render_html(
    article: dict, url_to_local: dict[str, str], images_dir: Path
) -> str:
    """将文章数据渲染为 HTML 字符串。"""
    template_path = Path(__file__).parent.parent / "templates" / "article.html"
    template_str = template_path.read_text(encoding="utf-8")

    content_html = _strip_hidden_style(article["content_html"])
    content_html = _replace_image_urls_for_pdf(
        content_html, url_to_local, images_dir
    )

    # 元信息处理：author 与 source 相同时只显示 source
    author = article.get("author", "")
    source = article.get("source", "")
    author_display = author if author and author != source else ""

    html = (
        template_str
        .replace("ARTICLE_TITLE", _escape_html(article.get("title", "")))
        .replace("ARTICLE_SOURCE", _escape_html(source))
        .replace("ARTICLE_AUTHOR", _escape_html(author_display))
        .replace("ARTICLE_DATE", _escape_html(article.get("date", "")))
        .replace("ARTICLE_URL", article.get("url", ""))
        .replace("ARTICLE_CONTENT", content_html)
    )
    return html


def convert_to_pdf(
    article: dict,
    url_to_local: dict[str, str],
    images_dir: Path,
    output_path: Path,
) -> None:
    """
    将文章渲染为 PDF，保存到 output_path。
    使用 Playwright Chromium 渲染，支持完整 CSS 和中文字体。
    """
    from playwright.sync_api import sync_playwright

    html_str = _render_html(article, url_to_local, images_dir)

    # 将 HTML 写入临时文件，Playwright 通过 file:// URL 加载（本地图片需要此方式）
    with tempfile.NamedTemporaryFile(
        suffix=".html", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(html_str)
        tmp_path = Path(tmp.name)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(tmp_path.as_uri(), wait_until="networkidle")
            page.pdf(
                path=str(output_path),
                format="A4",
                margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
                print_background=True,
            )
            browser.close()
    finally:
        tmp_path.unlink(missing_ok=True)

