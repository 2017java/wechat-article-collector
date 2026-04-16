# WeChat Article Collector

**本地化微信公众号文章抓取器，面向 AI 友好笔记和知识管理。**

这一套工具把微信公众号文章自动抓取为结构化 Markdown 和 PDF，并支持 Obsidian/NotebookLM 友好的本地存储流程。

## 项目亮点

- 本地处理：文章、图片和 PDF 均保留在本机，不会上传到第三方服务。
- 隐私保护：`config.yaml`、`data/` 缓存与运行日志已加入 `.gitignore`，不会推送到 GitHub。
- AI 友好：生成 Markdown 时自动添加 YAML frontmatter，方便后续加载到 AI 知识库、语义搜索、Obsidian 或 NotebookLM。
- 漂亮的本地 Web UI：打开浏览器即可操作，支持预览、保存和配置管理。

## 功能列表

- 粘贴微信公众号文章链接，自动提取文章元信息
- 抓取正文内容并下载文章中图片
- 生成 Obsidian 兼容的 Markdown 文件
- 生成 PDF 文件，支持 Playwright 渲染后输出
- 可选同步到 Obsidian Vault 或 Google Drive
- 提供 REST API 和 `http://127.0.0.1:8686/docs` 文档
- 支持批量链接转换和离线文章缓存

## 准备工作

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 Playwright Chromium

```bash
python -m playwright install chromium
```

### 3. 配置项目

复制示例配置文件并修改本地设置：

```bash
copy config.example.yaml config.yaml
```

请将 `config.yaml` 中的路径替换为自己的存储目录/Obsidian Vault，并保持 `server_base_url` 留空用于本地调试。

### 4. 启动服务

```bash
python app.py
```

访问：

- 本地前端： `http://127.0.0.1:8686`
- API 文档： `http://127.0.0.1:8686/docs`

## 配置说明

`config.example.yaml` 中包含以下可配置项：

- `default_save_path`：文章默认保存目录
- `obsidian_vault`：Obsidian Vault 路径
- `google_drive_path`：Google Drive 同步目录
- `default_formats`：默认保存格式（md / pdf）
- `server_port`：本地服务端口
- `server_base_url`：公开部署后用于链接转换的外网地址
- `cache_dir`：文章缓存目录

## 目录结构

```text
wechat-article-collector/
├── app.py
├── config.example.yaml
├── requirements.txt
├── core/
├── static/
├── templates/
└── tests/
```

## 隐私与安全

- 本仓库仅包含源码与示例配置。
- 本地运行生成的 `data/` 缓存、日志、PDF、图片和私有 `config.yaml` 均不会纳入 Git 提交。
- 公开仓库只保存可复现的代码，不包含个人路径、Google Drive 路径或本地文件。

## AI 场景

该项目适用于将微信公众号内容转成 AI 可消费知识：

- 喂给 Obsidian + 语义搜索
- 输入 NotebookLM / AI Agent
- 构建个人知识库与研究资料
- 归档会议资料、灵感笔记和信息流文章

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/extract` | 提取文章元信息（预览） |
| POST | `/api/save` | 完整保存文章 |
| GET  | `/api/config` | 读取当前配置 |
| PUT  | `/api/config` | 更新配置 |
| GET  | `/api/history` | 获取保存历史 |
| DELETE | `/api/history` | 清空历史 |

---

如需运行测试，请执行：

```bash
pytest
```
