import re
import yaml
import shutil
from pathlib import Path
from datetime import datetime

from core.fetcher import fetch_article_with_fallback
from core.parser import parse_article
from core.image_downloader import download_images
from core.markdown_converter import convert_to_markdown
from core.pdf_converter import convert_to_pdf

# 配置文件路径（相对于本模块的根目录）
_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def _sanitize_dirname(name: str) -> str:
    """将文本转为安全的目录名（清理非法字符，截断长度）。"""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip("._").strip()
    return name[:50] or "unknown"


def load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def save_article(
    url: str,
    formats: list[str],
    save_path: str | None = None,
) -> dict:
    """
    完整保存流程：抓取 → 解析 → 下载图片 → 格式转换 → 写入磁盘。

    Args:
        url: 微信公众号文章链接
        formats: 保存格式列表，可包含 'md' 和/或 'pdf'
        save_path: 覆盖配置文件中的默认保存路径（可选）

    Returns:
        保存结果字典，包含 title, source, save_dir, saved_files, image_count
    """
    config = load_config()

    # 1. 抓取（含 Playwright 降级）
    html = fetch_article_with_fallback(url)
    if not html:
        raise ValueError(f"无法抓取文章，请检查链接是否有效：{url}")

    # 2. 解析
    article = parse_article(html, url=url)
    if not article:
        raise ValueError("文章内容解析失败，可能微信页面结构已变化")

    # 3. 确定保存目录：{base}/{公众号名}/{日期}-{标题}/
    base = Path(save_path or config["default_save_path"])
    source_safe = _sanitize_dirname(article["source"]) or "unknown"
    # 提取日期的纯数字部分（2026-03-29 → 20260329）
    date_raw = article["date"].replace("-", "").replace("/", "")
    date_prefix = date_raw[:8] if len(date_raw) >= 8 else datetime.now().strftime("%Y%m%d")
    title_safe = _sanitize_dirname(article["title"])
    article_dir = base / source_safe / f"{date_prefix}-{title_safe}"
    images_dir = article_dir / "images"
    article_dir.mkdir(parents=True, exist_ok=True)

    # 4. 下载图片
    url_to_local: dict[str, str] = {}
    if article["images"]:
        url_to_local = download_images(article["images"], images_dir)

    # 5. 保存 Markdown
    saved_files: list[str] = []
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

    # 7. Obsidian vault 集成（若配置了 vault 路径）
    obsidian_vault = config.get("obsidian_vault", "")
    if obsidian_vault and "md" in formats:
        vault = Path(obsidian_vault)
        obsidian_dir = vault / "WeChat" / source_safe
        obsidian_dir.mkdir(parents=True, exist_ok=True)
        dest_md = obsidian_dir / f"{date_prefix}-{title_safe}.md"
        shutil.copy2(article_dir / "article.md", dest_md)

        # 图片复制到 vault/attachments/wechat/{title}/
        if article["images"] and images_dir.exists():
            att_dir = (
                vault
                / config.get("obsidian_attachments_dir", "attachments")
                / "wechat"
                / title_safe
            )
            shutil.copytree(images_dir, att_dir, dirs_exist_ok=True)

    # 8. Google Drive 集成（用于 NotebookLM，若配置了路径）
    google_drive = config.get("google_drive_path", "")
    if google_drive and "pdf" in formats:
        gd_dir = Path(google_drive) / "WeChat"
        gd_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            article_dir / "article.pdf",
            gd_dir / f"{date_prefix}-{title_safe}.pdf",
        )

    return {
        "title": article["title"],
        "source": article["source"],
        "author": article["author"],
        "date": article["date"],
        "save_dir": str(article_dir),
        "saved_files": saved_files,
        "image_count": len(article["images"]),
    }
