import re
import time
import random
import requests
from pathlib import Path
from urllib.parse import urlparse

IMG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mp.weixin.qq.com/",
}

EXTENSION_MAP = {
    "jpeg": "jpg",
    "jpg": "jpg",
    "png": "png",
    "gif": "gif",
    "webp": "webp",
}


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符，截断过长的文件名。"""
    name = name.split("?")[0]  # 去掉 URL 参数
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip("._").strip()
    return name[:100]


def get_extension(url: str) -> str:
    """
    从微信图片 URL 中提取扩展名。
    优先从 wx_fmt 参数取，其次从路径取，默认 jpg。
    """
    parsed = urlparse(url)
    # 从查询参数 wx_fmt 提取
    params: dict[str, str] = {}
    for part in parsed.query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    fmt = params.get("wx_fmt", "").lower()
    if fmt in EXTENSION_MAP:
        return EXTENSION_MAP[fmt]

    # 从路径后缀提取
    path_ext = parsed.path.rsplit(".", 1)[-1].lower()
    if path_ext in EXTENSION_MAP:
        return EXTENSION_MAP[path_ext]

    return "jpg"


def download_images(image_urls: list[str], save_dir: Path) -> dict[str, str]:
    """
    批量下载图片到 save_dir/，返回 {原始URL: 本地相对路径} 映射。
    下载失败的 URL 保留原始 URL（确保 Markdown 中至少有网络图片链接）。
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    url_to_local: dict[str, str] = {}

    for i, url in enumerate(image_urls, start=1):
        ext = get_extension(url)
        filename = f"{i:03d}.{ext}"
        local_path = save_dir / filename

        try:
            time.sleep(random.uniform(0.5, 1.5))
            resp = requests.get(url, headers=IMG_HEADERS, timeout=15)
            resp.raise_for_status()
            # 验证响应是图片类型
            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type and len(resp.content) < 100:
                # 可能被重定向到错误页
                url_to_local[url] = url
                continue
            local_path.write_bytes(resp.content)
            url_to_local[url] = f"images/{filename}"
        except requests.RequestException:
            # 下载失败保留原始 URL，确保文章仍可读
            url_to_local[url] = url

    return url_to_local
