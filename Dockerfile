FROM python:3.11-slim

# 安装系统依赖（Playwright Chromium 需要）
RUN apt-get update && apt-get install -y \
    curl \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright Chromium
RUN playwright install chromium --with-deps

# 复制项目文件
COPY . .

# 创建缓存目录
RUN mkdir -p data/articles

# 暴露服务端口
EXPOSE 8686

# 启动命令（生产模式，不使用 reload）
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8686"]
