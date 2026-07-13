# ===== Build Args for Mirror Acceleration =====
# Usage: docker build --build-arg PIP_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple --build-arg APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian .
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org
ARG APT_MIRROR=deb.debian.org

FROM python:3.11-slim

WORKDIR /app

ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST
ARG APT_MIRROR

# apt 镜像加速
RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# pip 镜像加速
RUN pip config set global.index-url ${PIP_INDEX_URL} && \
    pip config set global.trusted-host ${PIP_TRUSTED_HOST}

# 升级 pip 避免旧版兼容问题
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 分步安装 torch（大包单独装，减少并行压力，已安装的会被 -r 跳过）
RUN pip install --no-cache-dir torch==2.5.1
RUN pip install --no-cache-dir sentence-transformers==3.3.1

# 安装其余依赖
RUN pip install --no-cache-dir -r requirements.txt

# HuggingFace 镜像
ARG HF_ENDPOINT=https://hf-mirror.com
ENV HF_ENDPOINT=${HF_ENDPOINT}

# 复制代码
COPY . .

# 创建数据目录
RUN mkdir -p data/datasets data/chroma_db data/vector_db data/conversations

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
