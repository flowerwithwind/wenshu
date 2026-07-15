#!/bin/bash
# SmartQA 部署辅助脚本（本地执行）
# 用法: ./deploy/deploy.sh --remote

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

DOCKER_USERNAME="${DOCKER_USERNAME:-}"
SERVER_HOST="${SERVER_HOST:-}"
SERVER_USER="${SERVER_USER:-root}"
SERVER_PORT="${SERVER_PORT:-22}"

print_usage() {
    echo "用法: $0 [OPTIONS]"
    echo "  --push-only   仅本地构建并推送到 Docker Hub"
    echo "  --remote      同步文件到服务器并 docker compose up"
    echo "  --all         推送 + 远程部署"
}

require_docker_user() {
    if [[ -z "$DOCKER_USERNAME" ]]; then
        echo "错误: 请设置 DOCKER_USERNAME"
        exit 1
    fi
}

push_images() {
    require_docker_user
    echo "[1] 构建并推送..."
    docker build -t "${DOCKER_USERNAME}/smartqa-backend:latest" ./backend
    docker build -t "${DOCKER_USERNAME}/smartqa-frontend:latest" ./frontend
    docker push "${DOCKER_USERNAME}/smartqa-backend:latest"
    docker push "${DOCKER_USERNAME}/smartqa-frontend:latest"
    echo "推送完成"
}

deploy_remote() {
    require_docker_user
    if [[ -z "$SERVER_HOST" ]]; then
        echo "错误: 请设置 SERVER_HOST"
        exit 1
    fi

    echo "[2] 同步到 ${SERVER_USER}@${SERVER_HOST}:${SERVER_PORT} ..."
    ssh -p "$SERVER_PORT" "${SERVER_USER}@${SERVER_HOST}" "mkdir -p /opt/smartqa"

    scp -P "$SERVER_PORT" deploy/docker-compose.prod.yml \
        "${SERVER_USER}@${SERVER_HOST}:/opt/smartqa/docker-compose.yml"
    scp -P "$SERVER_PORT" deploy/remote-up.sh \
        "${SERVER_USER}@${SERVER_HOST}:/opt/smartqa/remote-up.sh"

    if [[ -f deploy/.env ]]; then
        scp -P "$SERVER_PORT" deploy/.env \
            "${SERVER_USER}@${SERVER_HOST}:/opt/smartqa/.env"
    elif [[ -f .env.prod ]]; then
        scp -P "$SERVER_PORT" .env.prod \
            "${SERVER_USER}@${SERVER_HOST}:/opt/smartqa/.env"
    else
        echo "提示: 本地无 deploy/.env，将在服务器生成最小 .env"
        ssh -p "$SERVER_PORT" "${SERVER_USER}@${SERVER_HOST}" \
            "grep -q DOCKER_USERNAME /opt/smartqa/.env 2>/dev/null || echo DOCKER_USERNAME=${DOCKER_USERNAME} > /opt/smartqa/.env"
    fi

    ssh -p "$SERVER_PORT" "${SERVER_USER}@${SERVER_HOST}" "
        cd /opt/smartqa
        chmod +x remote-up.sh
        export DOCKER_USERNAME='${DOCKER_USERNAME}'
        export DOCKER_PASSWORD='${DOCKER_PASSWORD:-}'
        ./remote-up.sh
    "
    echo "远程部署完成 → http://${SERVER_HOST}/"
}

case "${1:-}" in
    --push-only) push_images ;;
    --remote) deploy_remote ;;
    --all) push_images; deploy_remote ;;
    *) print_usage; exit 1 ;;
esac
