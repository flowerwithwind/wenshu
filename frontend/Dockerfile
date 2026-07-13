# Build stage
FROM node:20-alpine AS build

ARG NPM_REGISTRY=https://registry.npmjs.org

WORKDIR /app
COPY package.json package-lock.json ./

# npm 镜像加速
RUN npm config set registry ${NPM_REGISTRY}
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

# nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
