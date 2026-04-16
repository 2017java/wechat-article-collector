import asyncio
import time
import random
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from core.fetcher import is_wechat_url, fetch_article
from core.parser import parse_article
from core.storage import save_article, load_config, save_config
from core.converter import get_article_id, generate_clean_html
from core.cache import ArticleCache

# 保存历史（内存，服务重启后清空；100 条上限）
HISTORY: list[dict] = []

# 全局缓存实例（lifespan 初始化）
article_cache: ArticleCache | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global article_cache
    config = load_config()
    cache_dir = config.get("cache_dir", "data/articles")
    article_cache = ArticleCache(cache_dir)
    yield


app = FastAPI(
    title="微信文章采集器",
    description="粘贴微信公众号文章链接，自动提取并保存为 Markdown / PDF",
    version="1.0.0",
    lifespan=lifespan,
)

# 挂载静态文件目录
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ── 请求模型 ─────────────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    url: str


class SaveRequest(BaseModel):
    url: str
    formats: list[str] = ["md", "pdf"]
    save_path: Optional[str] = None


class ConfigUpdate(BaseModel):
    default_save_path: Optional[str] = None
    obsidian_vault: Optional[str] = None
    google_drive_path: Optional[str] = None


class ConvertRequest(BaseModel):
    urls: list[str]


# ── 路由 ──────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(str(static_dir / "index.html"))


@app.post("/api/extract", summary="提取文章信息（预览，不保存）")
async def extract_article(req: ExtractRequest):
    """
    传入微信文章链接，返回文章元信息预览（标题、公众号、日期、图片数量等）。
    不下载图片，不写入磁盘。
    """
    url = req.url.strip()

    if not is_wechat_url(url):
        raise HTTPException(
            status_code=400,
            detail="不是有效的微信公众号文章链接，请确认链接以 https://mp.weixin.qq.com/s 开头",
        )

    # 使用快速 requests 抓取（预览不走 Playwright 降级，避免等待过长）
    html = await asyncio.to_thread(fetch_article, url)
    if not html:
        raise HTTPException(
            status_code=502,
            detail="无法访问文章页面，请检查链接是否正确，或稍后重试",
        )

    article = parse_article(html, url=url)
    if not article:
        raise HTTPException(
            status_code=422,
            detail="文章内容解析失败，页面可能需要登录或结构已更新",
        )

    # 正文文字预览（去除 HTML 标签）
    import re
    full_text = re.sub(r"<[^>]+>", "", article["content_html"])
    full_text = re.sub(r"\s+", " ", full_text).strip()
    text_preview = full_text[:300]

    return {
        "title": article["title"],
        "author": article["author"],
        "source": article["source"],
        "date": article["date"],
        "url": article["url"],
        "image_count": len(article["images"]),
        "word_count": len(full_text),
        "text_preview": text_preview,
    }


@app.post("/api/save", summary="保存文章到本地")
async def save(req: SaveRequest):
    """
    完整保存流程：抓取 → 解析 → 下载图片 → Markdown/PDF 转换 → 写入磁盘。
    同步执行（图片下载可能需要数秒），前端需等待响应。
    """
    url = req.url.strip()

    if not req.formats:
        raise HTTPException(status_code=400, detail="至少选择一种保存格式（md 或 pdf）")

    valid_formats = {"md", "pdf"}
    invalid = set(req.formats) - valid_formats
    if invalid:
        raise HTTPException(status_code=400, detail=f"不支持的格式：{invalid}")

    try:
        result = await asyncio.to_thread(
            save_article, url, req.formats, req.save_path
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败：{e}")

    # 写入历史记录
    HISTORY.insert(0, result)
    if len(HISTORY) > 100:
        HISTORY.pop()

    return result


@app.get("/api/config", summary="获取当前配置")
async def get_config():
    return load_config()


@app.put("/api/config", summary="更新配置")
async def update_config(update: ConfigUpdate):
    config = load_config()
    if update.default_save_path is not None:
        config["default_save_path"] = update.default_save_path
    if update.obsidian_vault is not None:
        config["obsidian_vault"] = update.obsidian_vault
    if update.google_drive_path is not None:
        config["google_drive_path"] = update.google_drive_path
    save_config(config)
    return config


@app.get("/api/history", summary="获取保存历史")
async def get_history():
    return HISTORY


@app.delete("/api/history", summary="清空保存历史")
async def clear_history():
    HISTORY.clear()
    return {"message": "历史已清空"}


# ── 链接转换 API ──────────────────────────────────────────────────────────────


@app.post("/api/convert", summary="批量转换微信链接为可访问 URL")
async def convert_articles(req: ConvertRequest):
    """
    接收多条微信文章链接，逐条抓取并缓存为纯净 HTML，
    返回每条链接对应的公网可访问 URL。
    已缓存的链接直接返回，不重复抓取。
    """
    if article_cache is None:
        raise HTTPException(status_code=503, detail="缓存服务未就绪")

    config = load_config()
    base_url = config.get("server_base_url", "").rstrip("/")
    max_batch = config.get("max_batch_size", 20)

    urls = [u.strip() for u in req.urls if u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="urls 不能为空")
    if len(urls) > max_batch:
        raise HTTPException(
            status_code=400, detail=f"单次最多转换 {max_batch} 条链接"
        )

    results = []
    for url in urls:
        if not is_wechat_url(url):
            results.append({"url": url, "error": "不是有效的微信公众号文章链接"})
            continue

        article_id = get_article_id(url)

        # 命中缓存，直接返回
        if article_cache.is_cached(article_id):
            meta = article_cache.load_meta(article_id)
            results.append({
                "url": url,
                "article_id": article_id,
                "accessible_url": f"{base_url}/article/{article_id}",
                "title": meta.get("title", "") if meta else "",
                "already_cached": True,
            })
            continue

        # 抓取
        try:
            html_raw = await asyncio.to_thread(fetch_article, url)
        except Exception:
            html_raw = None

        if not html_raw:
            results.append({"url": url, "error": "抓取失败，请检查链接或稍后重试"})
            # 批量处理间隔
            await asyncio.sleep(random.uniform(1, 3))
            continue

        article = parse_article(html_raw, url=url)
        if not article:
            results.append({"url": url, "error": "文章内容解析失败"})
            await asyncio.sleep(random.uniform(1, 3))
            continue

        # 生成纯净 HTML 并得到图片映射
        clean_html, img_map = generate_clean_html(article, article_id, base_url)

        # 下载图片
        images: dict[str, bytes] = {}
        for orig_url, filename in img_map.items():
            try:
                img_resp = await asyncio.to_thread(
                    _download_image, orig_url
                )
                if img_resp:
                    images[filename] = img_resp
            except Exception:
                pass

        # 持久化
        meta = {
            "title": article["title"],
            "source": article["source"],
            "author": article["author"],
            "date": article["date"],
            "original_url": url,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        article_cache.save(article_id, clean_html, meta, images)

        results.append({
            "url": url,
            "article_id": article_id,
            "accessible_url": f"{base_url}/article/{article_id}",
            "title": article["title"],
            "already_cached": False,
        })

        # 批量处理间隔，防反爬
        await asyncio.sleep(random.uniform(1, 3))

    return {"results": results}


def _download_image(url: str) -> Optional[bytes]:
    """同步下载单张图片，失败返回 None（在线程池中运行）。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://mp.weixin.qq.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "image" in content_type and len(resp.content) > 100:
            return resp.content
        return None
    except Exception:
        return None


@app.get("/article/{article_id}", summary="获取缓存文章 HTML", response_class=HTMLResponse)
async def get_article(article_id: str):
    """返回指定 ID 的纯净 HTML 文章页面（供 AI Agent 直接浏览）。"""
    if article_cache is None:
        raise HTTPException(status_code=503, detail="缓存服务未就绪")
    # 只允许 8 位十六进制 ID，防止路径遍历
    if not article_id.isalnum() or len(article_id) != 8:
        raise HTTPException(status_code=400, detail="无效的文章 ID")
    html = article_cache.load_html(article_id)
    if not html:
        raise HTTPException(status_code=404, detail="文章不存在或已被删除")
    return HTMLResponse(content=html)


@app.get("/article/{article_id}/images/{filename}", summary="获取文章缓存图片")
async def get_article_image(article_id: str, filename: str):
    """返回文章的本地缓存图片。"""
    if article_cache is None:
        raise HTTPException(status_code=503, detail="缓存服务未就绪")
    if not article_id.isalnum() or len(article_id) != 8:
        raise HTTPException(status_code=400, detail="无效的文章 ID")
    data = article_cache.load_image(article_id, filename)
    if not data:
        raise HTTPException(status_code=404, detail="图片不存在")
    ext = filename.rsplit(".", 1)[-1].lower()
    media_type_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                      "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
    media_type = media_type_map.get(ext, "image/jpeg")
    return Response(content=data, media_type=media_type)


@app.get("/api/cached", summary="列出所有已缓存文章")
async def list_cached():
    if article_cache is None:
        raise HTTPException(status_code=503, detail="缓存服务未就绪")
    return {"articles": article_cache.list_all()}


@app.delete("/api/cached/{article_id}", summary="删除指定缓存文章")
async def delete_cached(article_id: str):
    if article_cache is None:
        raise HTTPException(status_code=503, detail="缓存服务未就绪")
    if not article_id.isalnum() or len(article_id) != 8:
        raise HTTPException(status_code=400, detail="无效的文章 ID")
    deleted = article_cache.delete(article_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文章不存在或已被删除")
    return {"message": "已删除", "article_id": article_id}


# ── 启动入口 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    config = load_config()
    port = config.get("server_port", 8686)
    print(f"\n[WeChat Collector] 启动中...")
    print(f"   访问地址: http://127.0.0.1:{port}")
    print(f"   API 文档: http://127.0.0.1:{port}/docs\n")
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=True)
