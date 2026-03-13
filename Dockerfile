FROM python:3.10-slim

# 使用阿里云 Debian 镜像源（国内服务器）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true

# ffmpeg 用于 GPT 视频抽帧
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用 Docker layer 缓存），使用阿里云 PyPI 镜像
COPY requirements.txt ./requirements.txt
COPY server/requirements.txt ./server-requirements.txt
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    -r requirements.txt -r server-requirements.txt

# 复制项目代码
COPY tests/ tests/
COPY server/ server/
COPY frontend/dist/ frontend/dist/
COPY .env .env

ENV PYTHONPATH=/app
EXPOSE 8001

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8001"]
