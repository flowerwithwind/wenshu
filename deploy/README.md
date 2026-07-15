# SmartQA 生产部署

推送 `master` / `main` 后，GitHub Actions 会：

1. 跑测试  
2. 构建并推送镜像到 **Docker Hub**  
3. 若配置了服务器 Secrets，则 **SSH 上传 compose + 拉镜像启动**

服务器目录固定为：`/opt/smartqa`

```
/opt/smartqa/
  docker-compose.yml   # 来自 deploy/docker-compose.prod.yml
  .env                 # 运行时配置（CI 自动生成）
  remote-up.sh         # 拉镜像并启动
```

## 1. GitHub Secrets（仓库 Settings → Secrets and variables → Actions）

### 必填

| Secret | 说明 |
|--------|------|
| `DOCKER_USERNAME` | Docker Hub 用户名 |
| `DOCKER_PASSWORD` | Docker Hub 密码或 Access Token |

### 远程部署（你已配置）

| Secret | 说明 |
|--------|------|
| `SERVER_HOST` | 服务器 IP 或域名 |
| `SERVER_USER` | SSH 用户（需能执行 docker，或在 docker 组） |
| `SERVER_PASSWORD` | SSH 密码 |
| `SERVER_PORT` | 可选，默认 `22` |

### 强烈建议（业务可用）

| Secret | 说明 |
|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key，写入服务器 `.env` |
| `DEEPSEEK_BASE_URL` | 可选，默认 `https://api.deepseek.com` |
| `JWT_SECRET_KEY` | 生产 JWT 密钥，勿用默认值 |
| `CORS_ORIGINS` | 可选；同源反代一般 `*` 即可 |

## 2. 服务器一次性准备

```bash
# 安装 Docker + Compose 插件
# 将部署用户加入 docker 组，避免每次 sudo：
sudo usermod -aG docker $USER

# 目录
sudo mkdir -p /opt/smartqa
sudo chown -R $USER:$USER /opt/smartqa

# 开放端口：80（前端）、可选 8000（直连 API）
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
```

首次也可手动验通：

```bash
export DOCKER_USERNAME=你的DockerHub用户名
docker login
cd /opt/smartqa
# 放好 docker-compose.yml 与 .env 后：
docker compose pull
docker compose up -d
curl -s http://127.0.0.1:8000/api/health
# 浏览器打开 http://服务器IP/
```

## 3. 访问

| 地址 | 说明 |
|------|------|
| `http://SERVER_HOST/` | 前端（nginx，反代 `/api`） |
| `http://SERVER_HOST:8000/api/health` | 后端健康检查 |
| `http://SERVER_HOST:8000/docs` | OpenAPI 文档 |

首次启动若需下载 BGE 模型，后端 health 可能要等数分钟，属正常。

## 4. 本地脚本（可选）

```bash
# 见 deploy/deploy.sh —— 已对齐 Docker Hub 命名
export DOCKER_USERNAME=...
export DOCKER_PASSWORD=...
export SERVER_HOST=...
export SERVER_USER=...
./deploy/deploy.sh --remote
```
