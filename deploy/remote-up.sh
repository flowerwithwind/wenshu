#!/usr/bin/env bash
# 在服务器 /opt/smartqa 执行：登录 Docker Hub → pull → up
set -euo pipefail

cd /opt/smartqa

if [[ ! -f docker-compose.yml ]]; then
  echo "ERROR: missing docker-compose.yml in /opt/smartqa"
  ls -la || true
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "ERROR: missing .env in /opt/smartqa"
  exit 1
fi

# 从 .env 读取关键变量（不 source 整文件，避免特殊字符问题）
get_env() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" .env | tail -n1 || true)"
  echo "${line#*=}"
}

DOCKER_USERNAME="$(get_env DOCKER_USERNAME)"
IMAGE_TAG="$(get_env IMAGE_TAG)"
IMAGE_TAG="${IMAGE_TAG:-latest}"

if [[ -z "$DOCKER_USERNAME" ]]; then
  echo "ERROR: DOCKER_USERNAME empty in .env"
  exit 1
fi

if [[ -f .docker_password ]]; then
  cat .docker_password | docker login -u "$DOCKER_USERNAME" --password-stdin
  rm -f .docker_password
elif [[ -n "${DOCKER_PASSWORD:-}" ]]; then
  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
fi

echo "==> Pull ${DOCKER_USERNAME}/smartqa-*:${IMAGE_TAG}"
docker compose pull

echo "==> Up"
docker compose up -d --remove-orphans

echo "==> PS"
docker compose ps

echo "==> Wait backend health (max ~5 min)"
ok=0
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
    echo "Backend healthy (attempt $i)"
    ok=1
    break
  fi
  echo "  waiting... ($i/30)"
  sleep 10
done

if [[ "$ok" -ne 1 ]]; then
  echo "WARN: health not ready; recent logs:"
  docker compose logs --tail=100 backend || true
fi

docker image prune -f >/dev/null 2>&1 || true
echo "Deploy finished at $(date -Is)"
