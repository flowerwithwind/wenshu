#!/usr/bin/env bash
# 在服务器 /opt/smartqa：配置国内镜像加速 →（可选）登录 → pull → up
# 国内机访问 registry-1.docker.io 常超时：login 失败可忽略，靠 mirror pull
set -euo pipefail

cd /opt/smartqa

if [[ ! -f docker-compose.yml ]]; then
  echo "ERROR: missing docker-compose.yml"
  ls -la || true
  exit 1
fi
if [[ ! -f .env ]]; then
  echo "ERROR: missing .env"
  exit 1
fi

get_env() {
  local line
  line="$(grep -E "^${1}=" .env | tail -n1 || true)"
  echo "${line#*=}"
}

DOCKER_USERNAME="$(get_env DOCKER_USERNAME)"
IMAGE_TAG="$(get_env IMAGE_TAG)"
IMAGE_TAG="${IMAGE_TAG:-latest}"

if [[ -z "$DOCKER_USERNAME" ]]; then
  echo "ERROR: DOCKER_USERNAME empty in .env"
  exit 1
fi

run_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    sudo "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

# 强制写入可用加速（腾讯云 CVM 内网优先）
force_registry_mirrors() {
  echo "==> Configure registry-mirrors (force China-friendly list)"
  run_root mkdir -p /etc/docker
  if [[ -f /etc/docker/daemon.json ]]; then
    run_root cp /etc/docker/daemon.json "/etc/docker/daemon.json.bak.$(date +%s)" || true
  fi
  run_root tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ],
  "max-concurrent-downloads": 3,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
  run_root systemctl daemon-reload 2>/dev/null || true
  run_root systemctl restart docker 2>/dev/null || run_root service docker restart 2>/dev/null || true
  echo "    waiting docker after restart..."
  sleep 5
  for _ in $(seq 1 30); do
    if docker info >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  docker info 2>/dev/null | grep -A8 -i 'Registry Mirrors' || true
}

hub_reachable() {
  # 2 秒探测，不通就别浪费时间 login
  timeout 5 bash -c 'echo >/dev/tcp/registry-1.docker.io/443' 2>/dev/null \
    || curl -fsS -m 5 -o /dev/null https://registry-1.docker.io/v2/ 2>/dev/null
}

docker_login_optional() {
  rm -f .docker_password 2>/dev/null || true
  if ! hub_reachable; then
    echo "==> Skip docker login (registry-1.docker.io unreachable; pull via mirrors)"
    return 0
  fi
  if [[ -z "${DOCKER_PASSWORD:-}" && ! -f .docker_password ]]; then
    echo "==> Skip docker login (no password)"
    return 0
  fi
  echo "==> Docker login as ${DOCKER_USERNAME}"
  if [[ -f .docker_password ]]; then
    cat .docker_password | docker login -u "$DOCKER_USERNAME" --password-stdin && return 0
  fi
  if [[ -n "${DOCKER_PASSWORD:-}" ]]; then
    echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin && return 0
  fi
  echo "WARN: login failed; continue with anonymous/mirror pull"
}

pull_one() {
  local image="$1"
  local i
  echo "    pull $image"
  for i in 1 2 3 4 5 6; do
    if docker pull "$image"; then
      echo "    ok: $image"
      return 0
    fi
    echo "    fail $image attempt $i/6, sleep $((i * 8))s"
    sleep $((i * 8))
    if [[ "$i" -eq 2 ]]; then
      force_registry_mirrors
    fi
  done
  return 1
}

compose_pull() {
  local backend="${DOCKER_USERNAME}/smartqa-backend:${IMAGE_TAG}"
  local frontend="${DOCKER_USERNAME}/smartqa-frontend:${IMAGE_TAG}"
  echo "==> Pull images (may take 10–40 min for backend with torch)"
  # 串行更稳，避免双大镜像并行把弱网打挂
  pull_one "$backend"
  pull_one "$frontend"
}

force_registry_mirrors
docker_login_optional
compose_pull

echo "==> Up"
docker compose up -d --remove-orphans

echo "==> PS"
docker compose ps

echo "==> Wait backend health (max ~8 min)"
ok=0
for i in $(seq 1 48); do
  if curl -fsS "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
    echo "Backend healthy (attempt $i)"
    ok=1
    break
  fi
  echo "  waiting health... ($i/48)"
  sleep 10
done

if [[ "$ok" -ne 1 ]]; then
  echo "WARN: health not ready yet (model download may still run). Logs:"
  docker compose logs --tail=80 backend || true
fi

docker image prune -f >/dev/null 2>&1 || true
echo "Deploy finished at $(date -Is)"
