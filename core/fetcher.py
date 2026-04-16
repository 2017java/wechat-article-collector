import re
import time
import random
import requests
from typing import Optional

WECHAT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mp.weixin.qq.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

# 匹配微信公众号文章链接（含短链和长参数链）
WECHAT_URL_PATTERN = re.compile(
    r"https://mp\.weixin\.qq\.com/s[/?].*"
)


def is_wechat_url(url: str) -> bool:
    """检查 URL 是否为微信公众号文章链接。"""
    return bool(WECHAT_URL_PATTERN.match(url.strip()))


def fetch_article(url: str, timeout: int = 15) -> Optional[str]:
    """
    抓取微信文章 HTML，返回 HTML 字符串，失败返回 None。
    非微信 URL 直接返回 None。
    """
    if not is_wechat_url(url):
        return None
    try:
        # 随机延迟 1-3 秒，降低被速率限制的风险
        time.sleep(random.uniform(1, 3))
        session = requests.Session()
        resp = session.get(
            url.strip(),
            headers=WECHAT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    except requests.RequestException:
        return None


async def fetch_with_playwright(url: str) -> Optional[str]:
    """
    使用 Playwright 无头浏览器抓取（降级方案）。
    当 requests 抓取内容为空或被拦截时使用。
    """
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                extra_http_headers={"Referer": "https://mp.weixin.qq.com/"}
            )
            await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.content()
            await browser.close()
            return content
    except Exception:
        return None


def fetch_article_with_fallback(url: str) -> Optional[str]:
    """
    先用 requests 快速抓取，若正文为空则降级到 Playwright 无头浏览器。
    """
    import asyncio
    from bs4 import BeautifulSoup

    html = fetch_article(url)
    if html:
        soup = BeautifulSoup(html, "html.parser")
        if soup.find(id="js_content"):
            return html

    # 降级到 Playwright
    return asyncio.run(fetch_with_playwright(url))
