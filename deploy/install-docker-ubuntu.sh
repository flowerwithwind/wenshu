#!/usr/bin/env bash
# Ubuntu 一键安装 Docker + Compose（含国内镜像加速）
# 用法: bash install-docker-ubuntu.sh
# 可选环境变量:
#   DOCKER_APT_MIRROR   apt 源，默认阿里云
#   DOCKER_REGISTRY_MIRROR  拉取加速，默认 DaoCloud 公共加速

set -euo pipefail

# ---- 可改镜像 ----
# apt 安装包加速（二选一即可）
DOCKER_APT_MIRROR="${DOCKER_APT_MIRROR:-https://mirrors.aliyun.com/docker-ce}"
# 备用: https://mirrors.tuna.tsinghua.edu.cn/docker-ce
# 备用: https://mirrors.cloud.tencent.com/docker-ce
# 官方: https://download.docker.com

# 容器镜像拉取加速（可追加多个）
DOCKER_REGISTRY_MIRROR="${DOCKER_REGISTRY_MIRROR:-https://docker.m.daocloud.io}"
# 阿里云需登录控制台创建「容器镜像服务 → 镜像加速器」个人地址，例如:
#   https://xxxx.mirror.aliyuncs.com
# 腾讯云内网: https://mirror.ccs.tencentyun.com

echo "==> [1/6] 基础依赖"
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

echo "==> [2/6] Docker GPG + apt 源（${DOCKER_APT_MIRROR}）"
sudo install -m 0755 -d /etc/apt/keyrings

# 优先从镜像拉 GPG，失败再回落官方
if ! curl -fsSL "${DOCKER_APT_MIRROR}/linux/ubuntu/gpg" | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg; then
  echo "镜像 GPG 失败，改用官方 download.docker.com ..."
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
fi
sudo chmod a+r /etc/apt/keyrings/docker.gpg

ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME}")"

echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] ${DOCKER_APT_MIRROR}/linux/ubuntu ${CODENAME} stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "==> [3/6] 安装 Docker Engine / Buildx / Compose 插件"
sudo apt-get update
sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

echo "==> [4/6] 配置 registry-mirrors 加速拉镜像"
sudo mkdir -p /etc/docker
# 若已有 daemon.json 则备份
if [[ -f /etc/docker/daemon.json ]]; then
  sudo cp /etc/docker/daemon.json "/etc/docker/daemon.json.bak.$(date +%s)"
fi

# 使用 Python 合并/写入 JSON，避免手写格式错误
sudo python3 - <<PY
import json, os
path = "/etc/docker/daemon.json"
data = {}
if os.path.isfile(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        data = {}
mirrors = data.get("registry-mirrors") or []
want = "${DOCKER_REGISTRY_MIRROR}".strip()
if want and want not in mirrors:
    mirrors.insert(0, want)
# 常见公共加速（去重）
for m in [
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run",
]:
    if m not in mirrors:
        mirrors.append(m)
data["registry-mirrors"] = mirrors
data.setdefault("log-driver", "json-file")
data.setdefault("log-opts", {"max-size": "10m", "max-file": "3"})
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("wrote", path, "registry-mirrors=", mirrors)
PY

sudo systemctl daemon-reload
sudo systemctl enable docker
sudo systemctl restart docker

echo "==> [5/6] 当前用户加入 docker 组 + 部署目录"
sudo usermod -aG docker "${USER}"
sudo mkdir -p /opt/smartqa
sudo chown -R "${USER}:${USER}" /opt/smartqa

echo "==> [6/6] 防火墙端口（若使用 ufw）"
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 22/tcp || true
  sudo ufw allow 18080/tcp || true
  sudo ufw allow 18000/tcp || true
  sudo ufw allow 18001/tcp || true
  sudo ufw allow 18002/tcp || true
  sudo ufw allow 18082/tcp || true
  echo "已放行 22 与 18xxx 业务端口（未自动 ufw enable，按需自行开启）"
fi

echo ""
echo "======== 验证 ========"
sudo docker version
sudo docker compose version
echo "registry-mirrors:"
sudo docker info 2>/dev/null | grep -A5 -i 'Registry Mirrors' || true

echo ""
echo "拉测试镜像（走加速）..."
sudo docker pull hello-world
sudo docker run --rm hello-world

echo ""
echo "安装完成。"
echo "请执行:  exit  后重新 SSH 登录，使 docker 组生效（之后可不用 sudo docker）。"
echo "部署目录: /opt/smartqa"
echo ""
echo "自定义加速示例:"
echo "  DOCKER_APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/docker-ce \\"
echo "  DOCKER_REGISTRY_MIRROR=https://xxxx.mirror.aliyuncs.com \\"
echo "  bash install-docker-ubuntu.sh"
