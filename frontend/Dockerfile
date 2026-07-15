# Build stage
FROM node:24-alpine AS build

ARG NPM_REGISTRY=https://registry.npmjs.org
# 变更此参数可强制失效 COPY 层缓存（CI 传入 commit SHA）
ARG CACHEBUST=1

WORKDIR /app
COPY package.json package-lock.json ./

# npm 镜像加速
RUN npm config set registry ${NPM_REGISTRY}
RUN npm ci

# 显式依赖 CACHEBUST，避免 GHA buildx 误用旧源码层
RUN echo "cachebust=${CACHEBUST}"
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

# nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
