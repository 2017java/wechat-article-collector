import re
from datetime import datetime
from markdownify import markdownify


def _build_frontmatter(article: dict) -> str:
    """生成 Obsidian 兼容的 YAML frontmatter。"""
    # 将公众号名转为 kebab-case 标签（如"测试公众号" → "测试公众号"）
    source = article.get("source", "unknown")
    source_tag = re.sub(r"\s+", "-", source) if source else "unknown"

    return (
        "---\n"
        f'title: "{_escape_yaml(article.get("title", ""))}"\n'
        f'author: "{_escape_yaml(article.get("author", ""))}"\n'
        f'source: "{_escape_yaml(source)}"\n'
        f'date: {article.get("date", "")}\n'
        f'url: "{article.get("url", "")}"\n'
        f"tags:\n"
        f"  - wechat\n"
        f"  - {source_tag}\n"
        f'created: {datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}\n'
        "---\n\n"
    )


def _escape_yaml(value: str) -> str:
    """转义 YAML 字符串中的双引号。"""
    return value.replace('"', '\\"')


def _replace_image_urls(content_html: str, url_to_local: dict[str, str]) -> str:
    """
    将 HTML 中的图片 URL 替换为本地相对路径。
    处理 data-src（懒加载）和 src 两种属性。
    """
    for original_url, local_path in url_to_local.items():
        # BeautifulSoup 序列化时会将 URL 中的 & 编码为 &amp;，需同时处理两种形式
        encoded_url = original_url.replace("&", "&amp;")
        for url_variant in (original_url, encoded_url):
            content_html = content_html.replace(
                f'data-src="{url_variant}"', f'src="{local_path}"'
            )
            content_html = content_html.replace(
                f'src="{url_variant}"', f'src="{local_path}"'
            )
    return content_html


def convert_to_markdown(article: dict, url_to_local: dict[str, str]) -> str:
    """
    将文章数据转换为 Obsidian 兼容的 Markdown 字符串。
    包含：YAML frontmatter、标题、正文（图片替换为本地路径）。
    """
    content_html = _replace_image_urls(article["content_html"], url_to_local)

    body = markdownify(
        content_html,
        heading_style="ATX",
        strip=["script", "style"],
        newline_style="backslash",
    )

    # 清理多余空行（markdownify 有时产生过多空行）
    body = re.sub(r"\n{3,}", "\n\n", body)

    frontmatter = _build_frontmatter(article)
    title_heading = f"# {article.get('title', 'Untitled')}\n\n"
    return frontmatter + title_heading + body.strip() + "\n"
