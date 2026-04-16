# PROJECT MEMORY
> 本文件由 project-memory skill 自动生成，记录项目关键信息供后续参考。
> 请勿手动大幅修改，可在各条目下方追加备注。

---

## [PROJECT SUMMARY] wechat-article-collector — 2026-04-03 14:00

### 项目背景
> 微信公众号文章采集与转换工具：用户粘贴微信文章链接，系统抓取并缓存为纯净 HTML，返回可被 NotebookLM/ChatGPT/Claude 等 AI Agent 直接浏览的公网 URL。同时保留原有 Markdown/PDF 导出功能。

### 核心需求
- 批量粘贴微信链接 → 生成公网可访问的纯净 HTML URL
- 纯净 HTML：无 JS、UTF-8、图片本地代理、代码块保留格式
- 图片下载到本地，避免微信 CDN 过期失效
- 已缓存链接自动跳过，不重复抓取
- 部署到火山引擎 ECS（2C4G），通过 `http://118.145.228.33:8686` 访问

### 技术架构
- **技术栈**：Python 3.14、FastAPI、uvicorn、BeautifulSoup4、Playwright（PDF用）、requests
- **架构说明**：请求 → FastAPI 路由 → fetcher 抓取 → parser 解析 → converter 生成纯净 HTML → cache 持久化磁盘 → 返回 URL
- **关键文件路径**：
  - `app.py` — FastAPI 主应用，所有路由
  - `core/converter.py` — 纯净 HTML 生成器（清理微信 HTML、图片代理、代码块处理）
  - `core/cache.py` — 磁盘缓存 CRUD（`data/articles/{id}/article.html + meta.json + images/`）
  - `core/fetcher.py` — 微信文章抓取（requests + Playwright 降级）
  - `core/parser.py` — HTML 解析，提取标题/作者/正文/图片
  - `static/app.js` — 前端逻辑（转换/复制/缓存管理）
  - `static/index.html` — 前端页面（引用 `?v=2` 版本号防缓存）
  - `config.yaml` — 配置文件（`server_base_url`、`cache_dir`、`max_batch_size`）

### 当前进度
- [x] 批量链接转换 POST /api/convert
- [x] 文章 HTML 页面 GET /article/{id}
- [x] 图片代理 GET /article/{id}/images/{filename}
- [x] 缓存管理 GET/DELETE /api/cached
- [x] 前端转换 UI + 复制功能
- [x] 部署到 ECS，公网可访问
- [x] 代码块正确显示（等宽字体 + 灰色背景）
- [ ] HTTPS 支持（NotebookLM 可能要求）
- [ ] 自动缓存清理（30 天 LRU）

### 关键决策记录
| 决策点 | 选择 | 原因 | 放弃的方案 |
|--------|------|------|------------|
| 图片存储 | 本地代理 `/article/{id}/images/` | 微信 CDN 有效期短 | 直接引用微信 URL |
| 文章 ID | URL 的 MD5 前 8 位 | 简短唯一，同 URL 不重复抓取 | UUID |
| 批量处理 | 顺序处理，间隔 1-3s | 防微信反爬 | 并发抓取 |
| visibility:hidden | 不删除 | 微信用 JS 控制，正文整体带此属性，CSS 已覆盖 | 删除（会导致正文消失）|
| 代码块行号 | 删除空 ul/li | 微信行号列表全是空 li，无内容价值 | 保留 |
| 部署方式 | 直接 nohup uvicorn（非 Docker）| 用户习惯 | Docker Compose |

### ECS 部署信息
- **服务器**：118.145.228.33（火山引擎 ECS，2C4G）
- **部署路径**：`/opt/wechat-collector/`
- **启动命令**：`cd /opt/wechat-collector && nohup uvicorn app:app --host 0.0.0.0 --port 8686 > /tmp/wechat.log 2>&1 &`
- **日志**：`/tmp/wechat.log`
- **配置文件**：`/opt/wechat-collector/config.yaml`，`server_base_url: "http://118.145.228.33:8686"`
- **缓存目录**：`/opt/wechat-collector/data/articles/`
- **更新流程**：本地修改 → `scp 文件 root@118.145.228.33:/opt/wechat-collector/对应路径` → SSH 重启 uvicorn → 删旧缓存重新转换

### 下一步行动
1. 测试更多微信文章链接，确认各种代码块格式均正确
2. 考虑购买域名 + Caddy 配置 HTTPS（NotebookLM 需要）

### Agent 接手须知
> 1. **缓存是旧的**：修改 converter.py 后必须删除 `/opt/wechat-collector/data/articles/*` 并重启 uvicorn，否则继续读旧文件
> 2. **uvicorn 必须重启**：Python 模块启动时缓存，改代码不重启不生效
> 3. **scp 上传后不自动生效**：Python 文件需重启服务，静态文件（JS/HTML）不需要重启但需要浏览器强刷
> 4. **server_base_url 必须含端口**：`http://118.145.228.33:8686`，不能写 `http://118.145.228.33`（80端口不通）
> 5. **SSH 命令用 PowerShell 时**避免 `$()` 子命令和复杂引号嵌套，改用 `pkill -f uvicorn` 而非 `kill $(pgrep)`
> 6. **静态文件防缓存**：index.html 引用 `/static/app.js?v=2`，下次改 JS 需改版本号

---

## [BUG RECORD] 复制按钮报错 TypeError: Cannot read properties of undefined — 2026-04-03 14:00

### 问题现象
> `app.js:269 Uncaught TypeError: Cannot read properties of undefined (reading 'writeText')`，点击复制按钮崩溃

### 根本原因
> `navigator.clipboard` 在 HTTP 页面（非 HTTPS）中是 `undefined`，直接调用 `.writeText()` 不走 `.catch()` 而是直接抛出 TypeError

### 解决方案
先检查 `navigator.clipboard && navigator.clipboard.writeText` 是否存在，不存在直接走 `execCommand('copy')` 降级

### 踩过的坑
- ❌ 以为降级逻辑会自动触发 → 实际上 undefined 不会触发 `.catch()`，直接崩溃

---

## [BUG RECORD] 转换后文章只有标题作者无正文 — 2026-04-03 14:00

### 问题现象
> 转换后打开链接，只显示标题和作者，正文内容完全空白

### 根本原因
> 微信 `#js_content` 元素带有 `visibility: hidden` 内联样式（JS 执行后才变可见），`converter.py` 的清理逻辑把带 `visibility:hidden` 的元素全部删除，导致整个正文消失

### 解决方案
只删除 `display: none` 的元素，不删 `visibility: hidden`。生成的 HTML 已有 `* { visibility: visible !important; }` CSS 规则覆盖

---

## [BUG RECORD] 图片 502 Bad Gateway — 2026-04-03 14:00

### 问题现象
> 文章图片全部 502，浏览器控制台：`GET http://118.145.228.33/article/.../images/img_001.webp 502`

### 根本原因
> ECS 上 `config.yaml` 的 `server_base_url` 写成了 `thhp://118.145.228.33`（拼写错误），后来 sed 修复了拼写但漏掉端口，变成 `http://118.145.228.33`（80端口），图片 URL 生成错误

### 解决方案
1. 修改本地 `config.yaml`：`server_base_url: "http://118.145.228.33:8686"`
2. `scp config.yaml root@118.145.228.33:/opt/wechat-collector/config.yaml`
3. 删除旧缓存：`rm -rf /opt/wechat-collector/data/articles/*`
4. 重启 uvicorn，重新转换链接

### 踩过的坑
- ❌ 以为是浏览器缓存 → 实际是生成的 HTML 里图片 URL 本身就是错的
- ❌ SSH 里用 sed 修配置文件引号嵌套报错 → 改为本地修改后 scp 上传

---

## [BUG RECORD] 代码块显示为一行 — 2026-04-03 14:00

### 问题现象
> 微信原文中的多行代码块在转换后挤成一行，行号变成空白 bullet points

### 根本原因
> 1. CSS 缺少 `pre`/`code` 的等宽字体和 `white-space: pre` 样式
> 2. 微信代码块前有一个 `<ul>` 行号容器，全是空 `<li>`，清理后变成空 bullet points
> 3. 微信每行代码用单独的 `<code>` 标签，没有换行符，依赖 `display:block` 换行

### 解决方案
1. CSS 添加 `pre { background:#f6f8fa; } pre code { font-family:monospace; white-space:pre; display:block; }`
2. 清理时检测全空 `<ul>`（所有 `<li>` 无文字内容）并删除

### 踩过的坑
- ❌ 修改代码后忘记重启 uvicorn → 进程还在用内存中的旧模块
- ❌ 删了缓存但没重启服务 → 重新转换时用的还是旧 converter.py
