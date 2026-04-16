import re
import hashlib
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup


def get_article_id(url: str) -> str:
    """生成文章 ID：URL 的 MD5 前 8 位"""
    return hashlib.md5(url.strip().encode()).hexdigest()[:8]


def _clean_content_html(content_html: str, article_id: str, base_url: str) -> tuple[str, dict[str, str]]:
    """
    用 BeautifulSoup 清理微信正文 HTML：
    - 移除隐藏元素（visibility:hidden / display:none）
    - 移除脚本、noscript、iframe 标签
    - 替换图片 data-src 为代理路径
    - 保留段落、标题、强调等语义标签
    返回 (清理后HTML, img_map)
    """
    soup = BeautifulSoup(content_html, "html.parser")

    # 移除脚本、noscript、iframe
    for tag in soup.find_all(["script", "noscript", "iframe", "style"]):
        tag.decompose()

    # 移除微信代码块的行号列表（pre 前的空 ul，全部 li 为空）
    for ul in soup.find_all("ul"):
        lis = ul.find_all("li", recursive=False)
        if lis and all(li.get_text(strip=True) == "" for li in lis):
            ul.decompose()

    # 仅移除 display:none 的元素（真正不可见的内容）
    # visibility:hidden 不删除——微信用 JS 控制，CSS 已用 visibility:visible!important 覆盖
    for tag in soup.find_all(style=True):
        style = tag.get("style", "")
        if re.search(r"display\s*:\s*none", style, re.I):
            tag.decompose()

    # 处理图片：data-src → 代理 src，清除多余属性
    img_map: dict[str, str] = {}
    img_counter = [0]

    for img in soup.find_all("img"):
        orig_src = img.get("data-src") or img.get("src") or ""
        # 跳过 data URI 和非 http 链接
        if not orig_src or orig_src.startswith("data:") or not orig_src.startswith("http"):
            img.decompose()
            continue

        if orig_src not in img_map:
            img_counter[0] += 1
            ext = _get_img_ext(orig_src)
            img_map[orig_src] = f"img_{img_counter[0]:03d}.{ext}"

        filename = img_map[orig_src]
        proxy_url = f"{base_url}/article/{article_id}/images/{filename}"

        # 清空所有属性，只保留 src 和 alt
        alt = img.get("alt", "")
        img.attrs = {"src": proxy_url}
        if alt:
            img.attrs["alt"] = alt

    # 清理每个标签的危险属性，保留语义
    KEEP_ATTRS = {"href", "src", "alt", "title", "colspan", "rowspan"}
    for tag in soup.find_all(True):
        attrs_to_remove = [k for k in list(tag.attrs.keys()) if k not in KEEP_ATTRS]
        for k in attrs_to_remove:
            del tag.attrs[k]

    return str(soup), img_map


def generate_clean_html(
    article: dict, article_id: str, base_url: str = ""
) -> tuple[str, dict[str, str]]:
    """
    生成语义化纯净 HTML5 页面，适合 AI Agent 直接阅读。

    - UTF-8 编码，无 JS，最小内联 CSS
    - 图片路径替换为代理路径 /article/{id}/images/{name}
    - 移除微信隐藏元素、脚本、无用属性
    - 添加 <meta> 标签便于 AI Agent 理解

    Returns:
        (html_str, img_map)
        img_map: {原始图片 URL: 本地文件名} 映射，供后续下载使用
    """
    title = article.get("title", "Untitled")
    author = article.get("author", "")
    source = article.get("source", "")
    date = article.get("date", "")
    original_url = article.get("url", "")
    content_html = article.get("content_html", "")

    # 清理正文 HTML 并获取图片映射
    content, img_map = _clean_content_html(content_html, article_id, base_url)

    # 纯文本用于 description meta 标签（从清理后的 content 提取，避免包含隐藏文本）
    description = re.sub(r"<[^>]+>", "", content)
    description = re.sub(r"\s+", " ", description).strip()[:200]

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="{_esc(description)}" />
  <meta name="author" content="{_esc(author)}" />
  <meta name="source" content="{_esc(source)}" />
  <meta name="date" content="{_esc(date)}" />
  <meta name="original-url" content="{_esc(original_url)}" />
  <title>{_esc(title)}</title>
  <style>
    body {{
      font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
      max-width: 780px;
      margin: 0 auto;
      padding: 24px 16px 48px;
      color: #1a1a1a;
      line-height: 1.8;
      background: #fff;
    }}
    h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; }}
    .meta {{
      font-size: 13px;
      color: #888;
      margin-bottom: 24px;
      border-bottom: 1px solid #eee;
      padding-bottom: 16px;
    }}
    img {{ max-width: 100%; height: auto; border-radius: 4px; display: block; margin: 12px 0; }}
    p {{ margin: 12px 0; }}
    section {{ padding-top: 8px; }}
    /* 代码块样式 */
    pre {{
      background: #f6f8fa;
      border: 1px solid #e1e4e8;
      border-radius: 6px;
      padding: 16px;
      overflow-x: auto;
      margin: 16px 0;
      line-height: 1.6;
    }}
    pre code {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 13px;
      color: #24292e;
      background: none;
      padding: 0;
      display: block;
      white-space: pre;
    }}
    code {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 13px;
      background: #f0f0f0;
      padding: 2px 5px;
      border-radius: 3px;
    }}
    /* 确保所有元素可见 */
    * {{ visibility: visible !important; }}
  </style>
</head>
<body>
  <h1>{_esc(title)}</h1>
  <div class="meta">{_esc(source)} · {_esc(author)} · {_esc(date)}</div>
  <section>
{content}
  </section>
</body>
</html>"""

    return html, img_map


def _get_img_ext(url: str) -> str:
    """从微信图片 URL 中提取扩展名，默认 jpg"""
    ext_map = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "gif": "gif", "webp": "webp"}
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        fmt = (params.get("wx_fmt") or [""])[0].lower()
        if fmt in ext_map:
            return ext_map[fmt]
        path_ext = parsed.path.rsplit(".", 1)[-1].lower()
        return ext_map.get(path_ext, "jpg")
    except Exception:
        return "jpg"


def _esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
