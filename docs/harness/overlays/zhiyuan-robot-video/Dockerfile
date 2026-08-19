# 智源单视角前端：官方镜像 + 本仓库改过的 Label Studio Frontend。
# 在仓库根目录构建：
#   docker build -f docs/harness/overlays/zhiyuan-robot-video/Dockerfile -t zhiyuan-label-studio:ux .
#
# 这不是新栈。前端 builder 与上游 Dockerfile 同类；运行时仍是官方发行镜像。
# HTML 改为 type=module 加载 Vite dist（manifest hash 名）。禁止把 Vite 文件改名为 Webpack main.js。

# syntax=docker/dockerfile:1
FROM oven/bun:1.3-alpine AS frontend-builder
ENV BUILD_NO_SERVER=true \
    BUILD_NO_HASH=true \
    BUILD_NO_CHUNKS=true \
    BUILD_MODULE=true \
    NODE_ENV=production \
    NODE_OPTIONS="--max-old-space-size=4096"
WORKDIR /label-studio/web
RUN sed -i 's#https\?://dl-cdn.alpinelinux.org#https://mirrors.tuna.tsinghua.edu.cn#g' /etc/apk/repositories \
    && apk add --no-cache git
COPY web/package.json web/bun.lock ./
ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com \
    CYPRESS_INSTALL_BINARY=0 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN bun install --frozen-lockfile --registry https://registry.npmmirror.com
COPY web ./
RUN mkdir -p /label-studio/label_studio/core/static/js
COPY pyproject.toml ../pyproject.toml
RUN bun run build

FROM heartexlabs/label-studio:latest
COPY --from=frontend-builder /label-studio/web/dist /label-studio/web/dist
COPY --from=frontend-builder /label-studio/label_studio/core/static/js /label-studio/label_studio/core/static/js
COPY docs/harness/overlays/zhiyuan-robot-video/patches/base.html /label-studio/label_studio/templates/base.html
# Django 启动时从 STATIC_ROOT/js/manifest.json 解析 Vite hash 入口。
# 官方镜像 BASE_DIR 是 label_studio/core，STATIC_ROOT=label_studio/core/static_build。
RUN mkdir -p /label-studio/label_studio/core/static_build/js \
    && cp /label-studio/label_studio/core/static/js/manifest.json /label-studio/label_studio/core/static_build/js/manifest.json
