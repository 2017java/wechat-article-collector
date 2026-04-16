# 微信公众号文章采集器 (WeChat Article Collector) — Implementation Plan

**Goal:** 构建一个 Python 本地 Web 应用，用户粘贴微信公众号文章链接，自动抓取文章内容和图片，保存为 Markdown（兼容 Obsidian）和 PDF 格式，并支持 NotebookLM 辅助导入。

**Architecture:** FastAPI 后端 + requests/BeautifulSoup 抓取（Playwright 降级）+ markdownify 转 Markdown + WeasyPrint 生成 PDF + 原生 HTML 前端单页应用。保存结构为 `{base_path}/{公众号名}/{YYYY-MM-DD}-{文章标题}/article.md + article.pdf + images/`。

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, requests, BeautifulSoup4, lxml, markdownify, WeasyPrint, Playwright, PyYAML

---

## File Structure

```
wechat-article-collector/
├── app.py                      # FastAPI 主入口，路由注册
├── requirements.txt            # Python 依赖
├── config.yaml                 # 用户配置（保存路径、Obsidian vault、Google Drive 路径）
├── PRD.md                      # 项目文档
├── static/
│   ├── index.html              # 前端单页应用
│   ├── style.css               # 样式
│   └── app.js                  # 前端逻辑（链接输入、预览、保存、历史）
├── core/
│   ├── __init__.py
│   ├── fetcher.py              # HTTP 抓取，请求头管理，重定向处理
│   ├── parser.py               # BeautifulSoup 解析，提取标题/作者/正文/图片URL
│   ├── image_downloader.py     # 图片批量下载，Referer 头，本地路径映射
│   ├── markdown_converter.py   # HTML→Markdown，YAML frontmatter，Obsidian 标签
│   ├── pdf_converter.py        # WeasyPrint 渲染，中文排版 CSS，图片内嵌
│   └── storage.py              # 文件保存，目录创建，文件名 sanitize
├── templates/
│   └── article.html            # PDF 渲染 HTML 模板（中文排版优化 CSS）
└── tests/
    ├── fixtures/
    │   └── sample_article.html # 本地保存的微信文章 HTML，供单元测试用
    ├── test_fetcher.py
    ├── test_parser.py
    └── test_converter.py
```

---

## Phase 1: 核心抓取引擎

### Task 1: 初始化项目

**Files:**
- Create: `wechat-article-collector/requirements.txt`
- Create: `wechat-article-collector/config.yaml`
- Create: `wechat-article-collector/core/__init__.py`

- [ ] **Step 1: 创建 requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
requests==2.32.3
beautifulsoup4==4.12.3
lxml==5.3.0
markdownify==0.13.1
weasyprint==62.3
playwright==1.47.0
pyyaml==6.0.2
python-multipart==0.0.9
aiofiles==24.1.0
```

- [ ] **Step 2: 创建 config.yaml**

```yaml
default_save_path: "D:/Articles/WeChat"
obsidian_vault: ""
obsidian_attachments_dir: "attachments"
google_drive_path: ""
default_formats:
  - md
  - pdf
server_port: 8686
```

- [ ] **Step 3: 创建 core/__init__.py（空文件）**

- [ ] **Step 4: 安装依赖**

Run: `pip install -r requirements.txt`
Expected: 所有包安装成功，无错误

---

### Task 2: 实现 `core/fetcher.py`

**Files:**
- Create: `wechat-article-collector/core/fetcher.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_fetcher.py
def test_invalid_url_raises():
    from core.fetcher import fetch_article
    result = fetch_article("https://not-weixin.com/article")
    assert result is None

def test_valid_url_format():
    from core.fetcher import is_wechat_url
    assert is_wechat_url("https://mp.weixin.qq.com/s/abc123")
    assert not is_wechat_url("https://example.com/s/abc")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd wechat-article-collector && python -m pytest tests/test_fetcher.py -v`
Expected: FAIL (ImportError or AttributeError)

- [ ] **Step 3: 实现 fetcher.py**

```python
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

WECHAT_URL_PATTERN = re.compile(
    r"https://mp\.weixin\.qq\.com/s[/?].*"
)


def is_wechat_url(url: str) -> bool:
    return bool(WECHAT_URL_PATTERN.match(url))


def fetch_article(url: str, timeout: int = 15) -> Optional[str]:
    """抓取微信文章 HTML，返回 HTML 字符串，失败返回 None。"""
    if not is_wechat_url(url):
        return None
    try:
        # 随机延迟，避免触发速率限制
        time.sleep(random.uniform(1, 3))
        session = requests.Session()
        resp = session.get(url, headers=WECHAT_HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    except requests.RequestException:
        return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_fetcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/fetcher.py tests/test_fetcher.py
git commit -m "feat: add article fetcher with WeChat URL validation"
```

---

### Task 3: 实现 `core/parser.py`

**Files:**
- Create: `wechat-article-collector/core/parser.py`
- Create: `wechat-article-collector/tests/fixtures/sample_article.html`（需手动保存一篇真实微信文章的 HTML）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_parser.py
import os
from core.parser import parse_article

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_article.html")

def test_parse_returns_required_fields():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        html = f.read()
    result = parse_article(html, url="https://mp.weixin.qq.com/s/test")
    assert result["title"]
    assert result["source"]  # 公众号名
    assert result["content_html"]
    assert isinstance(result["images"], list)

def test_parse_missing_content_returns_none():
    result = parse_article("<html><body></body></html>", url="")
    assert result is None
```

- [ ] **Step 2: 获取测试 fixture**（手动：在浏览器中打开一篇微信文章 → 保存网页 → 复制 HTML 到 `tests/fixtures/sample_article.html`）

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/test_parser.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 4: 实现 parser.py**

```python
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup


def parse_article(html: str, url: str) -> Optional[dict]:
    """解析微信文章 HTML，返回结构化数据字典，内容缺失返回 None。"""
    soup = BeautifulSoup(html, "lxml")

    # 提取标题
    title_el = soup.find("h1", class_="rich_media_title") or soup.find(id="activity-name")
    title = title_el.get_text(strip=True) if title_el else ""

    # 提取公众号名
    source_el = soup.find(id="js_name")
    source = source_el.get_text(strip=True) if source_el else ""

    # 提取作者（可能无）
    author_el = soup.find(id="js_author_name")
    author = author_el.get_text(strip=True) if author_el else source

    # 提取发布时间
    date_el = soup.find(id="publish_time")
    date_str = date_el.get_text(strip=True) if date_el else ""

    # 提取正文
    content_el = soup.find(id="js_content")
    if not content_el:
        return None

    # 提取图片 URL（data-src 优先，回退 src）
    images = []
    for img in content_el.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        if src and "mmbiz.qpic.cn" in src:
            images.append(src)

    return {
        "title": title or "Untitled",
        "author": author,
        "source": source,
        "date": date_str,
        "url": url,
        "content_html": str(content_el),
        "images": images,
    }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_parser.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add core/parser.py tests/test_parser.py
git commit -m "feat: add HTML parser for WeChat article structure"
```

---

### Task 4: 实现 `core/image_downloader.py`

**Files:**
- Create: `wechat-article-collector/core/image_downloader.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_fetcher.py（追加）
def test_sanitize_filename():
    from core.image_downloader import sanitize_filename
    assert "/" not in sanitize_filename("path/to/file.jpg")
    assert "?" not in sanitize_filename("file.jpg?wx_fmt=jpeg")
```

- [ ] **Step 2: 实现 image_downloader.py**

```python
import re
import time
import random
import requests
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

IMG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mp.weixin.qq.com/",
}

EXTENSION_MAP = {"jpeg": "jpg", "png": "png", "gif": "gif", "webp": "webp"}


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符。"""
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = name.split("?")[0]  # 去掉 URL 参数
    return name[:100]  # 限制长度


def get_extension(url: str) -> str:
    """从 URL 中提取图片扩展名。"""
    parsed = urlparse(url)
    params = dict(p.split("=") for p in parsed.query.split("&") if "=" in p)
    fmt = params.get("wx_fmt", "").lower()
    return EXTENSION_MAP.get(fmt, "jpg")


def download_images(image_urls: list[str], save_dir: Path) -> dict[str, str]:
    """
    下载图片列表到 save_dir，返回 {原始URL: 本地相对路径} 映射。
    下载失败的 URL 保留原始 URL。
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
            local_path.write_bytes(resp.content)
            url_to_local[url] = f"images/{filename}"
        except requests.RequestException:
            url_to_local[url] = url  # 失败保留原始 URL

    return url_to_local
```

- [ ] **Step 3: 运行测试确认通过**

Run: `python -m pytest tests/test_fetcher.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add core/image_downloader.py
git commit -m "feat: add image downloader with WeChat referer header"
```

---

## Phase 2: 格式转换

### Task 5: 实现 `core/markdown_converter.py`

**Files:**
- Create: `wechat-article-collector/core/markdown_converter.py`
- Create: `wechat-article-collector/tests/test_converter.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_converter.py
from core.markdown_converter import convert_to_markdown

ARTICLE = {
    "title": "测试文章",
    "author": "作者",
    "source": "测试公众号",
    "date": "2026-03-29",
    "url": "https://mp.weixin.qq.com/s/test",
    "content_html": "<div><p>这是正文</p><img src='https://mmbiz.qpic.cn/test.jpg'/></div>",
    "images": [],
}
URL_MAP = {"https://mmbiz.qpic.cn/test.jpg": "images/001.jpg"}

def test_frontmatter_present():
    md = convert_to_markdown(ARTICLE, url_to_local=URL_MAP)
    assert "---" in md
    assert "title:" in md
    assert "tags:" in md
    assert "测试公众号" in md

def test_image_replaced():
    md = convert_to_markdown(ARTICLE, url_to_local=URL_MAP)
    assert "images/001.jpg" in md
    assert "mmbiz.qpic.cn" not in md
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_converter.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 markdown_converter.py**

```python
import re
from datetime import datetime
from markdownify import markdownify


def _build_frontmatter(article: dict) -> str:
    source_tag = re.sub(r"\s+", "-", article.get("source", "unknown"))
    return (
        "---\n"
        f'title: "{article["title"]}"\n'
        f'author: "{article.get("author", "")}"\n'
        f'source: "{article.get("source", "")}"\n'
        f'date: {article.get("date", "")}\n'
        f'url: "{article.get("url", "")}"\n'
        f"tags:\n"
        f"  - wechat\n"
        f"  - {source_tag}\n"
        f'created: {datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}\n'
        "---\n\n"
    )


def convert_to_markdown(article: dict, url_to_local: dict[str, str]) -> str:
    """将文章数据转换为 Obsidian 兼容的 Markdown 字符串。"""
    content_html = article["content_html"]

    # 替换图片 URL 为本地路径（操作 HTML，markdownify 后路径才对）
    for original_url, local_path in url_to_local.items():
        # 替换 src 和 data-src
        content_html = content_html.replace(f'data-src="{original_url}"', f'src="{local_path}"')
        content_html = content_html.replace(f'src="{original_url}"', f'src="{local_path}"')

    body = markdownify(
        content_html,
        heading_style="ATX",
        strip=["script", "style"],
    )

    frontmatter = _build_frontmatter(article)
    title_heading = f"# {article['title']}\n\n"
    return frontmatter + title_heading + body.strip() + "\n"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_converter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/markdown_converter.py tests/test_converter.py
git commit -m "feat: add markdown converter with Obsidian frontmatter and tags"
```

---

### Task 6: 实现 `core/pdf_converter.py` 和 PDF 模板

**Files:**
- Create: `wechat-article-collector/core/pdf_converter.py`
- Create: `wechat-article-collector/templates/article.html`

- [ ] **Step 1: 创建 PDF HTML 模板 `templates/article.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&display=swap');
    body {
      font-family: "Noto Serif SC", "Source Han Serif CN", "SimSun", serif;
      font-size: 15px;
      line-height: 1.8;
      color: #333;
      max-width: 720px;
      margin: 0 auto;
      padding: 40px 30px;
    }
    h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
    .meta { color: #888; font-size: 13px; margin-bottom: 32px; border-bottom: 1px solid #eee; padding-bottom: 16px; }
    img { max-width: 100%; height: auto; display: block; margin: 16px auto; }
    blockquote { border-left: 3px solid #ccc; padding-left: 16px; color: #666; }
    code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
    pre { background: #f5f5f5; padding: 16px; border-radius: 6px; overflow-x: auto; }
    p { margin: 12px 0; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <div class="meta">
    <span>{{ source }}</span>
    {% if author and author != source %} · <span>{{ author }}</span>{% endif %}
    {% if date %} · <span>{{ date }}</span>{% endif %}
  </div>
  {{ content_html }}
</body>
</html>
```

- [ ] **Step 2: 实现 pdf_converter.py**

```python
import re
from pathlib import Path
from string import Template
from weasyprint import HTML


def _render_template(article: dict, url_to_local: dict[str, str], images_dir: Path) -> str:
    """将文章数据渲染为 HTML 字符串，图片引用替换为绝对本地路径（WeasyPrint 需要）。"""
    template_path = Path(__file__).parent.parent / "templates" / "article.html"
    template_str = template_path.read_text(encoding="utf-8")

    content_html = article["content_html"]
    # 替换图片 URL 为绝对路径（WeasyPrint 渲染 PDF 需要 file:/// 路径）
    for original_url, local_rel in url_to_local.items():
        local_abs = (images_dir.parent / local_rel).resolve().as_uri()
        content_html = content_html.replace(f'data-src="{original_url}"', f'src="{local_abs}"')
        content_html = content_html.replace(f'src="{original_url}"', f'src="{local_abs}"')

    # 简单模板替换（避免引入 Jinja2 依赖，保持轻量）
    html = (template_str
        .replace("{{ title }}", article.get("title", ""))
        .replace("{{ source }}", article.get("source", ""))
        .replace("{{ author }}", article.get("author", ""))
        .replace("{{ date }}", article.get("date", ""))
        .replace("{{ content_html }}", content_html)
    )
    # 处理 Jinja2-style 的条件语句（简单移除）
    html = re.sub(r"\{%.*?%\}", "", html, flags=re.DOTALL)
    return html


def convert_to_pdf(article: dict, url_to_local: dict[str, str], images_dir: Path, output_path: Path) -> None:
    """将文章渲染为 PDF，保存到 output_path。"""
    html_str = _render_template(article, url_to_local, images_dir)
    HTML(string=html_str).write_pdf(str(output_path))
```

- [ ] **Step 3: 手动验证**（在 Python shell 中调用，确认生成 PDF 中文正常）

```python
from pathlib import Path
from core.pdf_converter import convert_to_pdf
article = {"title": "测试", "source": "测试号", "author": "", "date": "2026-03-29",
           "content_html": "<p>这是中文测试内容。</p>", "images": []}
convert_to_pdf(article, {}, Path("test_images"), Path("test.pdf"))
# 打开 test.pdf 确认中文正常显示
```

- [ ] **Step 4: Commit**

```bash
git add core/pdf_converter.py templates/article.html
git commit -m "feat: add WeasyPrint PDF converter with Chinese typography"
```

---

### Task 7: 实现 `core/storage.py`

**Files:**
- Create: `wechat-article-collector/core/storage.py`

- [ ] **Step 1: 实现 storage.py**

```python
import re
import yaml
import shutil
from pathlib import Path
from datetime import datetime

from core.fetcher import fetch_article
from core.parser import parse_article
from core.image_downloader import download_images
from core.markdown_converter import convert_to_markdown
from core.pdf_converter import convert_to_pdf


def _sanitize_dirname(name: str) -> str:
    """将文章标题转为安全的目录名。"""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip("._").strip()
    return name[:60] or "article"


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_article(url: str, formats: list[str], save_path: str | None = None) -> dict:
    """
    完整流程：抓取 → 解析 → 下载图片 → 转换 → 保存。
    返回保存结果信息字典。
    """
    config = _load_config()

    # 1. 抓取
    html = fetch_article(url)
    if not html:
        raise ValueError(f"无法抓取文章: {url}")

    # 2. 解析
    article = parse_article(html, url=url)
    if not article:
        raise ValueError("文章内容解析失败，可能页面结构已变化")

    # 3. 确定保存目录
    base = Path(save_path or config["default_save_path"])
    source_safe = _sanitize_dirname(article["source"]) or "unknown"
    date_prefix = article["date"].replace("-", "")[:8] or datetime.now().strftime("%Y%m%d")
    title_safe = _sanitize_dirname(article["title"])
    article_dir = base / source_safe / f"{date_prefix}-{title_safe}"
    images_dir = article_dir / "images"
    article_dir.mkdir(parents=True, exist_ok=True)

    # 4. 下载图片
    url_to_local: dict[str, str] = {}
    if article["images"]:
        url_to_local = download_images(article["images"], images_dir)

    # 5. 保存 Markdown
    saved_files = []
    if "md" in formats:
        md_content = convert_to_markdown(article, url_to_local)
        md_path = article_dir / "article.md"
        md_path.write_text(md_content, encoding="utf-8")
        saved_files.append(str(md_path))

    # 6. 保存 PDF
    if "pdf" in formats:
        pdf_path = article_dir / "article.pdf"
        convert_to_pdf(article, url_to_local, images_dir, pdf_path)
        saved_files.append(str(pdf_path))

    # 7. 如果配置了 Obsidian vault，复制 Markdown
    obsidian_vault = config.get("obsidian_vault", "")
    if obsidian_vault and "md" in formats:
        vault = Path(obsidian_vault)
        obsidian_dir = vault / "WeChat" / source_safe
        obsidian_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(article_dir / "article.md", obsidian_dir / f"{date_prefix}-{title_safe}.md")
        # Obsidian 图片放 attachments/
        if article["images"]:
            att_dir = vault / config.get("obsidian_attachments_dir", "attachments") / "wechat" / title_safe
            shutil.copytree(images_dir, att_dir, dirs_exist_ok=True)

    # 8. 如果配置了 Google Drive，复制 PDF
    google_drive = config.get("google_drive_path", "")
    if google_drive and "pdf" in formats:
        gd_dir = Path(google_drive) / "WeChat"
        gd_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(article_dir / "article.pdf", gd_dir / f"{date_prefix}-{title_safe}.pdf")

    return {
        "title": article["title"],
        "source": article["source"],
        "save_dir": str(article_dir),
        "saved_files": saved_files,
        "image_count": len(article["images"]),
    }
```

- [ ] **Step 2: Commit**

```bash
git add core/storage.py
git commit -m "feat: add storage orchestrator with Obsidian and Google Drive support"
```

---

## Phase 3: Web 界面 + API

### Task 8: 实现 FastAPI 后端 `app.py`

**Files:**
- Create: `wechat-article-collector/app.py`

- [ ] **Step 1: 实现 app.py**

```python
import yaml
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl

from core.fetcher import fetch_article, is_wechat_url
from core.parser import parse_article
from core.storage import save_article

CONFIG_PATH = Path(__file__).parent / "config.yaml"
HISTORY: list[dict] = []  # 内存中的保存历史（简单实现）


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # 可在此添加启动/关闭钩子


app = FastAPI(title="微信文章采集器", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


class ExtractRequest(BaseModel):
    url: str


class SaveRequest(BaseModel):
    url: str
    formats: list[str] = ["md", "pdf"]
    save_path: str | None = None


class ConfigUpdate(BaseModel):
    default_save_path: str | None = None
    obsidian_vault: str | None = None
    google_drive_path: str | None = None


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/api/extract")
async def extract_article(req: ExtractRequest):
    """提取文章信息（预览用，不保存）。"""
    if not is_wechat_url(req.url):
        raise HTTPException(status_code=400, detail="不是有效的微信公众号文章链接")

    html = fetch_article(req.url)
    if not html:
        raise HTTPException(status_code=502, detail="无法访问文章，请检查链接或稍后重试")

    article = parse_article(html, url=req.url)
    if not article:
        raise HTTPException(status_code=422, detail="文章内容解析失败")

    return {
        "title": article["title"],
        "author": article["author"],
        "source": article["source"],
        "date": article["date"],
        "url": article["url"],
        "image_count": len(article["images"]),
        "content_preview": article["content_html"][:500],  # 预览前500字符
    }


@app.post("/api/save")
async def save(req: SaveRequest):
    """完整保存文章（含图片下载 + 格式转换）。"""
    if not req.formats:
        raise HTTPException(status_code=400, detail="至少选择一种保存格式")

    try:
        result = save_article(req.url, req.formats, req.save_path)
        HISTORY.insert(0, result)
        if len(HISTORY) > 100:
            HISTORY.pop()
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


@app.get("/api/config")
async def get_config():
    return load_config()


@app.put("/api/config")
async def update_config(update: ConfigUpdate):
    config = load_config()
    if update.default_save_path is not None:
        config["default_save_path"] = update.default_save_path
    if update.obsidian_vault is not None:
        config["obsidian_vault"] = update.obsidian_vault
    if update.google_drive_path is not None:
        config["google_drive_path"] = update.google_drive_path
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    return config


@app.get("/api/history")
async def get_history():
    return HISTORY


if __name__ == "__main__":
    import uvicorn
    config = load_config()
    port = config.get("server_port", 8686)
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=True)
```

- [ ] **Step 2: 启动服务验证**

Run: `python app.py`
Expected: Uvicorn 启动，访问 `http://127.0.0.1:8686/docs` 可见 Swagger UI

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add FastAPI backend with extract/save/config/history endpoints"
```

---

### Task 9: 实现前端 `static/`

**Files:**
- Create: `wechat-article-collector/static/index.html`
- Create: `wechat-article-collector/static/style.css`
- Create: `wechat-article-collector/static/app.js`

- [ ] **Step 1: 创建 `static/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>微信文章采集器</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div class="container">
    <header>
      <h1>📚 微信文章采集器</h1>
      <button id="settings-btn" class="icon-btn" title="设置">⚙️</button>
    </header>

    <!-- 链接输入区 -->
    <section class="input-section">
      <div class="url-input-row">
        <input type="text" id="url-input" placeholder="粘贴微信公众号文章链接 (mp.weixin.qq.com/s/...)" />
        <button id="extract-btn" class="btn-primary">提取预览</button>
      </div>
    </section>

    <!-- 预览区 -->
    <section id="preview-section" class="hidden">
      <div class="preview-card">
        <div class="preview-header">
          <h2 id="preview-title"></h2>
          <div class="preview-meta">
            <span id="preview-source"></span>
            <span id="preview-author"></span>
            <span id="preview-date"></span>
            <span id="preview-images"></span>
          </div>
        </div>
        <div class="format-select">
          <label><input type="checkbox" value="md" checked> Markdown (.md)</label>
          <label><input type="checkbox" value="pdf" checked> PDF (.pdf)</label>
        </div>
        <div class="save-options">
          <input type="text" id="save-path" placeholder="保存路径（留空使用默认路径）" />
        </div>
        <div class="action-row">
          <button id="save-btn" class="btn-success">💾 保存文章</button>
          <button id="cancel-btn" class="btn-ghost">取消</button>
        </div>
      </div>
    </section>

    <!-- 保存结果 -->
    <div id="toast" class="toast hidden"></div>

    <!-- 保存历史 -->
    <section class="history-section">
      <h3>保存历史</h3>
      <ul id="history-list"></ul>
    </section>

    <!-- 设置面板 -->
    <div id="settings-overlay" class="overlay hidden">
      <div class="settings-panel">
        <h2>⚙️ 设置</h2>
        <label>默认保存路径<input type="text" id="cfg-default-path" /></label>
        <label>Obsidian Vault 路径（留空不启用）<input type="text" id="cfg-obsidian" /></label>
        <label>Google Drive 路径（用于 NotebookLM，留空不启用）<input type="text" id="cfg-gdrive" /></label>
        <div class="action-row">
          <button id="save-config-btn" class="btn-primary">保存配置</button>
          <button id="close-settings-btn" class="btn-ghost">关闭</button>
        </div>
      </div>
    </div>
  </div>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 创建 `static/style.css`**（简洁现代风格，中文友好）

- [ ] **Step 3: 创建 `static/app.js`**（实现：提取预览、格式选择、保存、历史列表、配置面板的所有交互逻辑）

- [ ] **Step 4: 端到端测试**

  1. 访问 `http://127.0.0.1:8686`
  2. 粘贴一篇真实微信文章链接
  3. 点击"提取预览"，确认标题/作者/公众号名/图片数量显示正确
  4. 选择 Markdown + PDF，点击"保存文章"
  5. 确认文件保存到正确路径，Markdown 在 Obsidian 中显示正常，PDF 可打开

- [ ] **Step 5: Commit**

```bash
git add static/
git commit -m "feat: add frontend UI with extract preview, format selection, and settings"
```

---

## Phase 4: 进阶功能

### Task 10: NotebookLM 辅助导入 + Playwright 降级

**Files:**
- Modify: `wechat-article-collector/core/fetcher.py`（添加 `fetch_with_playwright` 函数）
- Modify: `wechat-article-collector/core/storage.py`（fetcher 失败时调用 Playwright）

- [ ] **Step 1: 在 fetcher.py 中添加 Playwright 降级**

```python
# 追加到 fetcher.py

async def fetch_with_playwright(url: str) -> Optional[str]:
    """使用 Playwright 无头浏览器抓取（降级方案）。"""
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
    """先用 requests，失败后降级到 Playwright。"""
    import asyncio
    html = fetch_article(url)
    if html:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        # 检查正文是否为空（被反爬拦截的常见特征）
        if soup.find(id="js_content"):
            return html
    # 降级到 Playwright
    return asyncio.run(fetch_with_playwright(url))
```

- [ ] **Step 2: 更新 storage.py 使用 fetch_article_with_fallback**

- [ ] **Step 3: Playwright 初始化（首次使用）**

Run: `playwright install chromium`
Expected: Chromium 浏览器下载完成

- [ ] **Step 4: 手动测试降级**（将 requests 请求头临时改错，验证 Playwright 降级生效）

- [ ] **Step 5: Commit**

```bash
git add core/fetcher.py core/storage.py
git commit -m "feat: add Playwright fallback for JS-rendered articles"
```

---

## Verification Checklist

- [ ] `python -m pytest tests/ -v` 全部通过
- [ ] 真实微信链接提取：标题/正文/公众号名/图片数正确
- [ ] 生成 Markdown 在 Obsidian 中打开：图片显示、frontmatter 标签正确
- [ ] 生成 PDF：中文显示正常、图片完整、排版合理
- [ ] Web UI 完整流程：粘贴链接 → 预览 → 选格式 → 保存 → 历史显示
- [ ] 边界测试：无图文章 / 长文章（>1w字）/ 含代码块 / 含表格
- [ ] Obsidian vault 路径配置后，文件正确复制到 vault 目录

---

## Known Risks & Mitigations

| 风险 | 缓解方案 |
|------|---------|
| 微信反爬（IP 封禁） | 请求间随机延迟 1-3s；Playwright 降级；不速率滥用 |
| 图片 token 过期 | 提取后立即下载图片，不缓存 URL |
| WeasyPrint 中文字体 | 安装 Noto Serif SC / 依赖系统中文字体 |
| 微信 HTML 结构变化 | 选择器多重备选（`h1.rich_media_title` 或 `#activity-name`） |
| NotebookLM 无 API | 通过 Google Drive 目录复制 PDF；等待官方 API |
