import json
import shutil
from pathlib import Path
from typing import Optional


class ArticleCache:
    """
    磁盘缓存管理器。
    结构：
        data/articles/{article_id}/
            ├── article.html   纯净 HTML 页面
            ├── meta.json      元数据（title, source, author, date, original_url, created_at）
            └── images/        下载的图片
    """

    def __init__(self, cache_dir: str = "data/articles") -> None:
        self.root = Path(cache_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, dict] = {}
        self._load_index()

    def _load_index(self) -> None:
        """扫描磁盘构建内存索引"""
        self._index.clear()
        for meta_file in self.root.glob("*/meta.json"):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if "id" in meta:
                    self._index[meta["id"]] = meta
            except Exception:
                pass

    def is_cached(self, article_id: str) -> bool:
        return (
            article_id in self._index
            and (self.root / article_id / "article.html").exists()
        )

    def save(
        self,
        article_id: str,
        html: str,
        meta: dict,
        images: Optional[dict[str, bytes]] = None,
    ) -> None:
        """
        保存文章 HTML、元数据和图片到磁盘。

        Args:
            article_id: 文章唯一 ID
            html: 纯净 HTML 内容
            meta: 元数据字典（自动附加 id 字段）
            images: {文件名: bytes} 图片数据，可选
        """
        article_dir = self.root / article_id
        article_dir.mkdir(parents=True, exist_ok=True)

        (article_dir / "article.html").write_text(html, encoding="utf-8")

        meta_with_id = {**meta, "id": article_id}
        (article_dir / "meta.json").write_text(
            json.dumps(meta_with_id, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if images:
            img_dir = article_dir / "images"
            img_dir.mkdir(exist_ok=True)
            for name, data in images.items():
                # 安全检查：文件名不能含路径分隔符
                safe_name = Path(name).name
                if safe_name:
                    (img_dir / safe_name).write_bytes(data)

        self._index[article_id] = meta_with_id

    def load_html(self, article_id: str) -> Optional[str]:
        path = self.root / article_id / "article.html"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def load_meta(self, article_id: str) -> Optional[dict]:
        return self._index.get(article_id)

    def load_image(self, article_id: str, filename: str) -> Optional[bytes]:
        """
        读取缓存图片，含路径遍历防护。
        """
        img_dir = (self.root / article_id / "images").resolve()
        try:
            img_path = (img_dir / Path(filename).name).resolve()
            # 确保最终路径在 img_dir 之内
            if not str(img_path).startswith(str(img_dir)):
                return None
            return img_path.read_bytes() if img_path.exists() else None
        except Exception:
            return None

    def list_all(self) -> list[dict]:
        return sorted(
            self._index.values(),
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )

    def delete(self, article_id: str) -> bool:
        article_dir = self.root / article_id
        if article_dir.exists():
            shutil.rmtree(article_dir)
            self._index.pop(article_id, None)
            return True
        return False
