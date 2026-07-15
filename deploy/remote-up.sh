#!/usr/bin/env bash
# 在服务器 /opt/smartqa 执行：配置镜像加速 → 登录 → pull → up
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

run_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    sudo "$@"
  else
    "$@"
  fi
}

# ---------- 国内服务器：配置 Docker Hub 镜像加速（避免 registry-1.docker.io 超时）----------
ensure_registry_mirrors() {
  echo "==> Ensure Docker registry-mirrors (China-friendly)"
  local daemon_json="/etc/docker/daemon.json"
  local tmp
  tmp="$(mktemp)"

  # 腾讯云 CVM 优先内网加速；再加公共加速
  cat >"$tmp" <<'EOF'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

  if [[ -f "$daemon_json" ]]; then
    # 已有 mirrors 则尽量不覆盖用户自定义（简单检测）
    if grep -q 'registry-mirrors' "$daemon_json" 2>/dev/null; then
      echo "    daemon.json already has registry-mirrors, keep existing"
      rm -f "$tmp"
      return 0
    fi
    run_root cp "$daemon_json" "${daemon_json}.bak.$(date +%s)" || true
  fi

  if run_root mkdir -p /etc/docker \
    && run_root cp "$tmp" "$daemon_json"; then
    echo "    wrote $daemon_json"
    run_root systemctl daemon-reload 2>/dev/null || true
    run_root systemctl restart docker 2>/dev/null || run_root service docker restart 2>/dev/null || true
    sleep 3
  else
    echo "    WARN: cannot write daemon.json (need passwordless sudo?). Configure mirrors manually if pull times out."
  fi
  rm -f "$tmp"
}

docker_login() {
  echo "==> Docker login as ${DOCKER_USERNAME}"
  local ok=0
  local i
  for i in 1 2 3; do
    if [[ -f .docker_password ]]; then
      if cat .docker_password | docker login -u "$DOCKER_USERNAME" --password-stdin; then
        ok=1
        break
      fi
    elif [[ -n "${DOCKER_PASSWORD:-}" ]]; then
      if echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin; then
        ok=1
        break
      fi
    else
      echo "    no password file/env; skip login (public pull only)"
      return 0
    fi
    echo "    login failed (attempt $i/3), retry in 5s..."
    sleep 5
  done
  rm -f .docker_password 2>/dev/null || true
  if [[ "$ok" -ne 1 ]]; then
    echo "WARN: docker login failed (Docker Hub may be blocked). Will still try pull via mirrors."
  fi
}

compose_pull_with_retry() {
  echo "==> Pull ${DOCKER_USERNAME}/smartqa-*:${IMAGE_TAG}"
  local i
  for i in 1 2 3 4 5; do
    if docker compose pull; then
      echo "    pull ok (attempt $i)"
      return 0
    fi
    echo "    pull failed (attempt $i/5)"
    if [[ "$i" -eq 2 ]]; then
      # 第二次失败后再强制写 mirrors 并重启 docker
      ensure_registry_mirrors
    fi
    sleep $((i * 5))
  done
  echo "ERROR: docker compose pull failed after retries."
  echo "Server cannot reach Docker Hub. On Tencent CVM, ensure daemon.json has mirror.ccs.tencentyun.com"
  echo "Then: sudo systemctl restart docker && cd /opt/smartqa && docker compose pull"
  return 1
}

ensure_registry_mirrors
docker_login
compose_pull_with_retry

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
