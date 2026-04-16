from typing import Optional
from bs4 import BeautifulSoup


def parse_article(html: str, url: str) -> Optional[dict]:
    """
    解析微信文章 HTML，返回结构化数据字典。
    正文内容缺失（无 #js_content）时返回 None。
    """
    soup = BeautifulSoup(html, "html.parser")

    # 提取标题：优先 h1.rich_media_title，备选 #activity-name
    title_el = (
        soup.find("h1", class_="rich_media_title")
        or soup.find(id="activity-name")
    )
    title = title_el.get_text(strip=True) if title_el else ""

    # 提取公众号名
    source_el = soup.find(id="js_name")
    source = source_el.get_text(strip=True) if source_el else ""

    # 提取作者（部分文章有单独作者字段，无则用公众号名代替）
    author_el = soup.find(id="js_author_name")
    author = author_el.get_text(strip=True) if author_el else source

    # 提取发布时间
    date_el = soup.find(id="publish_time")
    date_str = date_el.get_text(strip=True) if date_el else ""

    # 提取正文（必须字段，无则返回 None）
    content_el = soup.find(id="js_content")
    if not content_el:
        return None

    # 提取图片 URL（data-src 优先，防止懒加载）
    images: list[str] = []
    seen: set[str] = set()
    for img in content_el.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        if src and "mmbiz.qpic.cn" in src and src not in seen:
            images.append(src)
            seen.add(src)

    return {
        "title": title or "Untitled",
        "author": author,
        "source": source,
        "date": date_str,
        "url": url,
        "content_html": str(content_el),
        "images": images,
    }
