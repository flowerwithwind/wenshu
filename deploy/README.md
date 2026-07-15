# SmartQA：GitHub 自动部署

推送到 `master` / `main` 后，工作流 **Deploy SmartQA** 会自动：

1. 跑测试 + 前端 build  
2. 构建并推送镜像到 Docker Hub  
3. **上传** `docker-compose.yml` / `.env` / `remote-up.sh` 到服务器 `/opt/smartqa`  
4. SSH 执行 `docker compose pull && up -d`

也可在 GitHub → **Actions** → **Deploy SmartQA** → **Run workflow** 手动触发。

---

## 一、GitHub Secrets（必须）

路径：仓库 **Settings → Secrets and variables → Actions → New repository secret**

| 名称 | 必填 | 说明 |
|------|------|------|
| `DOCKER_USERNAME` | ✅ | Docker Hub 用户名 |
| `DOCKER_PASSWORD` | ✅ | Docker Hub 密码或 Access Token |
| `SERVER_HOST` | ✅ 自动上机 | 服务器公网 IP 或域名 |
| `SERVER_USER` | ✅ 自动上机 | SSH 用户，如 `ubuntu` |
| `SERVER_PASSWORD` | ✅ 自动上机 | SSH 密码 |
| `SERVER_PORT` | 可选 | 默认 `22` |
| `DEEPSEEK_API_KEY` | 建议 | 写入服务器 `.env`，否则无法真正问数 |
| `JWT_SECRET_KEY` | 建议 | 生产 JWT 密钥 |
| `DEEPSEEK_BASE_URL` | 可选 | 默认官方地址 |
| `CORS_ORIGINS` | 可选 | 默认 `*` |

> 若没配 `SERVER_HOST`，流水线**只会推镜像**，不会出现你服务器上的 `docker-compose.yml`。

---

## 二、服务器一次性准备

```bash
# 1) 安装 Docker（可用 deploy/install-docker-ubuntu.sh）
# 2) 当前用户可执行 docker
sudo usermod -aG docker ubuntu   # 用户名按实际改
# 重新登录 SSH

# 3) 目录
sudo mkdir -p /opt/smartqa
sudo chown -R ubuntu:ubuntu /opt/smartqa

# 4) 防火墙
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 8000/tcp
```

确认：

```bash
docker version
docker compose version
ls -la /opt/smartqa   # 首次可为空，成功部署后会有文件
```

---

## 三、触发自动部署

```bash
# 本地有改动时
git push origin master

# 或 GitHub 网页: Actions → Deploy SmartQA → Run workflow
```

看日志步骤：

- `Build and push backend/frontend image` — 镜像是否成功  
- `Upload bundle to server` — 是否上传到 `/opt/smartqa`  
- `Extract pull and start on server` — 是否 pull/up 成功  

部署成功后服务器应有：

```text
/opt/smartqa/
  docker-compose.yml
  .env
  remote-up.sh
```

访问：

- `http://SERVER_HOST/` — 前端  
- `http://SERVER_HOST:8000/api/health` — 健康检查  

---

## 四、常见失败

| 现象 | 原因 | 处理 |
|------|------|------|
| 只有 Hub 推送、服务器仍空 | 未配 `SERVER_HOST` 或值为空 | 检查 Secrets 名称拼写 |
| SSH 失败 | 密码/IP/安全组 | 本机 `ssh ubuntu@IP` 先测通 |
| `permission denied` docker | 用户不在 docker 组 | `usermod -aG docker` 后重登 |
| `sudo` 要密码 | 脚本里 chown 失败 | 先手动 `chown` `/opt/smartqa` |
| pull 失败 / `registry-1.docker.io` 超时 | 国内机访问 Docker Hub 不稳定 | 配置镜像加速（见下）后重试 |
| pull 失败 | Hub 登录/镜像名 | 核对 `DOCKER_USERNAME` 与镜像仓库 |

### 国内服务器 Docker Hub 超时（腾讯云等）

报错示例：

```text
Get "https://registry-1.docker.io/v2/": ... Timeout exceeded while awaiting headers
```

在服务器执行（腾讯云推荐内网加速）：

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run"
  ]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker

cd /opt/smartqa
./remote-up.sh
# 或: docker compose pull && docker compose up -d
```

新版本 `remote-up.sh` 会在部署时尽量自动写入上述加速配置。
| health 超时 | 首次下 embedding 慢 | 看 `docker logs smartqa-backend`，多等几分钟 |

---

## 五、与「手动 compose」的关系

- **推荐**：只靠 GitHub 自动上传 + 部署，不要手写冲突配置。  
- 手动 `docker compose` 仅在 `/opt/smartqa` 已有 `docker-compose.yml` 时可用；没有配置文件就会报 `no configuration file provided`。
