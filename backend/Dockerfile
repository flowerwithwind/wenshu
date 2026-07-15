# ===== Build Args for Mirror Acceleration =====
# Usage: docker build --build-arg PIP_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple .
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org
ARG APT_MIRROR=deb.debian.org
# 是否安装本地 Embedding 运行时（torch 等，约 +1~2GB）。0=仅 NL2SQL 核心
ARG INSTALL_ML=1

FROM python:3.11-slim

WORKDIR /app

ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST
ARG APT_MIRROR
ARG INSTALL_ML

# apt 镜像加速
RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip config set global.index-url ${PIP_INDEX_URL} && \
    pip config set global.trusted-host ${PIP_TRUSTED_HOST}

COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir --upgrade setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# 可选：CPU 版 torch + sentence-transformers（RAG 向量 / 精排）
# 使用 PyTorch CPU 轮子，避免默认源误装 CUDA 大包
RUN if [ "$INSTALL_ML" = "1" ]; then \
      pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && \
      pip install --no-cache-dir transformers==4.47.1 sentence-transformers==3.3.1 ; \
    else \
      echo "INSTALL_ML=0: skip torch / sentence-transformers" ; \
    fi

ARG HF_ENDPOINT=https://hf-mirror.com
ENV HF_ENDPOINT=${HF_ENDPOINT}

COPY . .

RUN mkdir -p data/datasets data/chroma_db data/vector_db data/conversations

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
