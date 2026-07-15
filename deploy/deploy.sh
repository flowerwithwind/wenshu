#!/bin/bash
# SmartQA 自动部署脚本
# 用法: ./deploy/deploy.sh [--build] [--push] [--deploy]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

REGISTRY="${DOCKER_REGISTRY:-ghcr.io}/${GITHUB_REPOSITORY_OWNER:-user}"
SERVER_HOST="${SERVER_HOST:-}"
SERVER_USER="${SERVER_USER:-root}"
COMPOSE_FILE="docker-compose.yml"
PROD_COMPOSE="deploy/docker-compose.prod.yml"

print_usage() {
    echo "用法: $0 [OPTIONS]"
    echo "选项:"
    echo "  --build       只构建 Docker 镜像"
    echo "  --push        构建并推送镜像到仓库"
    echo "  --deploy      在本地启动服务"
    echo "  --remote      部署到远程服务器（需设置 SERVER_HOST）"
    echo "  --all         执行完整流程：构建→推送→部署"
}

build() {
    echo "[1/3] 构建 Docker 镜像..."
    docker compose -f "$COMPOSE_FILE" build
    docker tag smartqa-backend:latest "${REGISTRY}/smartqa-backend:latest"
    docker tag smartqa-frontend:latest "${REGISTRY}/smartqa-frontend:latest"
    echo "构建完成: ${REGISTRY}/smartqa-backend:latest"
}

push() {
    echo "[2/3] 推送镜像到仓库..."
    docker push "${REGISTRY}/smartqa-backend:latest"
    docker push "${REGISTRY}/smartqa-frontend:latest"
    echo "推送完成"
}

deploy_local() {
    echo "[3/3] 本地部署..."
    mkdir -p data logs
    docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
    echo "本地部署完成"

    # 健康检查
    echo "等待服务就绪..."
    for i in $(seq 1 12); do
        if curl -sf http://localhost:8000/ > /dev/null 2>&1; then
            echo "服务已就绪! http://localhost:8000"
            break
        fi
        sleep 5
    done
}

deploy_remote() {
    if [ -z "$SERVER_HOST" ]; then
        echo "错误: 未设置 SERVER_HOST"
        exit 1
    fi

    echo "[3/3] 远程部署到 ${SERVER_HOST}..."

    # 传输部署文件
    ssh "${SERVER_USER}@${SERVER_HOST}" "mkdir -p /opt/smartqa/deploy"

    scp "$PROD_COMPOSE" "${SERVER_USER}@${SERVER_HOST}:/opt/smartqa/docker-compose.prod.yml"
    scp deploy/nginx.conf "${SERVER_USER}@${SERVER_HOST}:/opt/smartqa/deploy/nginx.conf" 2>/dev/null || true

    # 远程拉取并启动
    ssh "${SERVER_USER}@${SERVER_HOST}" "
        cd /opt/smartqa
        echo \"${DOCKER_PASSWORD}\" | docker login ${REGISTRY} -u \"${DOCKER_USERNAME}\" --password-stdin 2>/dev/null || true
        docker compose -f docker-compose.prod.yml pull
        docker compose -f docker-compose.prod.yml up -d --remove-orphans
        docker system prune -af --filter 'until=24h' 2>/dev/null || true
        echo '远程部署完成'
    "
}

# 主逻辑
case "${1:-}" in
    --build) build ;;
    --push) build; push ;;
    --deploy) deploy_local ;;
    --remote) deploy_remote ;;
    --all)
        build
        push
        deploy_local
        if [ -n "$SERVER_HOST" ]; then
            deploy_remote
        fi
        ;;
    *)
        print_usage
        exit 1
        ;;
esac
