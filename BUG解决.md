# BUG 解决记录

> 记录日期：2026-04-02  
> 项目：wechat-article-collector

---

## BUG 1：Playwright Chromium 未安装，保存失败

### 现象
点击保存时报错：
```
BrowserType.launch: Executable doesn't exist at
C:\Users\...\ms-playwright\chromium_headless_shell-1208\chrome-headless-shell-win64\chrome-headless-shell.exe
```

### 根本原因
Playwright v1208 需要两个独立的浏览器二进制：
- `chromium-1208/chrome-win64/chrome.exe`（headful 模式 + 网页抓取）
- `chromium_headless_shell-1208/chrome-headless-shell-win64/chrome-headless-shell.exe`（`headless=True` 生成 PDF 专用）

运行 `playwright install chromium` 时因 `cdn.playwright.dev` 国内网络不稳定中途断连，导致安装失败。

### 解决方案
直接从 Google Chrome for Testing 官方地址手动下载两个 zip 包，解压到 Playwright 期望路径：

```
# 完整 Chrome（用于网页抓取）
https://storage.googleapis.com/chrome-for-testing-public/145.0.7632.6/win64/chrome-win64.zip
→ 解压到：C:\Users\{用户名}\AppData\Local\ms-playwright\chromium-1208\

# Headless Shell（用于 PDF 生成）
https://storage.googleapis.com/chrome-for-testing-public/145.0.7632.6/win64/chrome-headless-shell-win64.zip
→ 解压到：C:\Users\{用户名}\AppData\Local\ms-playwright\chromium_headless_shell-1208\
```

---

## BUG 2：保存后文字内容缺失（只有图片目录，无 Markdown 文本）

### 现象
保存成功提示正常，但生成的 `article.md` 中文章正文为空，图片文件夹有内容。

### 根本原因
微信公众号页面通过 JavaScript 动态显示正文，`requests` 直接抓取的 HTML 中 `#js_content` 节点携带内联样式：
```html
<div id="js_content" style="visibility: hidden; opacity: 0;">
```
由于 `requests` 拿到的是服务端静态 HTML，JS 尚未执行，正文节点处于隐藏状态。后续 `parse_article` 虽能找到 `#js_content`，但文字实际上被渲染引擎隐藏，导致 PDF 生成的内容区域完全空白（文字也受影响）。

### 解决方案
在 `core/pdf_converter.py` 中新增 `_strip_hidden_style()` 函数，在渲染 PDF 前移除这两个隐藏属性：

```python
# core/pdf_converter.py
def _strip_hidden_style(content_html: str) -> str:
    import re
    content_html = re.sub(r'visibility\s*:\s*hidden\s*;?', '', content_html, flags=re.IGNORECASE)
    content_html = re.sub(r'opacity\s*:\s*0\s*;?', '', content_html, flags=re.IGNORECASE)
    return content_html
```

在 `_render_html()` 中调用：
```python
content_html = _strip_hidden_style(article["content_html"])
```

---

## BUG 3：预览界面字数统计不准（显示约 300 字）

### 现象
文章实际有 4000+ 字，但界面上"字数"一直显示约 300。

### 根本原因
`app.py` 中字数统计代码先截断再计长度：

```python
# 错误写法
text_preview = re.sub(...).strip()[:300]   # 先截断
word_count: len(text_preview)              # 再计字数 → 最多 300
```

### 解决方案
先计全文字数，再截断预览文本：

```python
# core/app.py
full_text = re.sub(r"<[^>]+>", "", article["content_html"])
full_text = re.sub(r"\s+", " ", full_text).strip()
text_preview = full_text[:300]      # 仅用于界面预览
word_count = len(full_text)         # 用全文长度
```

---

## BUG 4：PDF 中图片大量缺失（32 张只显示 2 张）

### 现象
独立保存图片文件夹时 32 张全部正常；生成 PDF 时图片几乎全部缺失，只有少数几张。

### 根本原因（两层）

#### 原因 A：Playwright headless shell 沙箱拒绝加载本地 `file://` 图片

PDF 生成时将图片路径替换为 `file:///绝对路径` 后传给 Playwright，但 headless shell 的安全沙箱默认阻止跨目录 `file://` 资源访问，图片无法加载。

**修复**：将本地图片读取后转为 **base64 data URI** 直接嵌入 HTML，完全绕过文件路径访问：

```python
import base64, mimetypes
b64 = base64.b64encode(local_abs.read_bytes()).decode()
mime_type, _ = mimetypes.guess_type(str(local_abs))
replacement = f"data:{mime_type};base64,{b64}"
```

#### 原因 B：URL 中 `&` 被 BeautifulSoup 编码为 `&amp;` 导致替换失败

`url_to_local` 字典的 key 是从 `img.get("data-src")` 取出的**已解码 URL**（如 `...wx_fmt=jpeg&tp=webp`），但 `str(content_el)` 序列化回 HTML 时 BeautifulSoup 会将 `&` 转为 HTML 实体 `&amp;`（如 `...wx_fmt=jpeg&amp;tp=webp`）。

32 张图片中有 30 张 URL 含有 `&` 参数，这 30 张全部替换失败，只有 2 张 URL 无 `&` 的图片被正确处理。

**修复**：替换时同时处理原始 URL 和 `&amp;` 编码两种形式：

```python
# core/pdf_converter.py 和 core/markdown_converter.py
encoded_url = original_url.replace("&", "&amp;")
for url_variant in (original_url, encoded_url):
    content_html = content_html.replace(
        f'data-src="{url_variant}"', f'src="{replacement}"'
    )
    content_html = content_html.replace(
        f'src="{url_variant}"', f'src="{replacement}"'
    )
```

**同样的修复也应用于** `markdown_converter.py` 中的 `_replace_image_urls()`，确保 Markdown 图片链接也全部正确替换。

---

## 涉及文件变更汇总

| 文件 | 修改内容 |
|------|----------|
| `core/pdf_converter.py` | 新增 `_strip_hidden_style()`；图片替换改用 base64 嵌入；同时处理 `&` 和 `&amp;` |
| `core/markdown_converter.py` | 图片 URL 替换同时处理 `&` 和 `&amp;` |
| `app.py` | 字数统计改为全文长度，预览文本与字数分离计算 |
