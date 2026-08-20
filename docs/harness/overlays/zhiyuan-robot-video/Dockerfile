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

# 官方 tensorflow 只有 glibc wheel。在 Debian Python 3.12 里装 TF，再嵌进 Alpine 官方镜像。
FROM python:3.12-slim-bookworm AS rlds-py
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    tensorflow tensorflow-datasets Pillow

FROM heartexlabs/label-studio:latest
USER root
# RLDS zip 常超过默认 250MB；TensorFlow 在国内连 GCE/GCS 会把导入卡住。
# 官方 latest 是 Alpine 3.x + Python 3.13（musl），ffmpeg 用 apk。
ENV DATA_UPLOAD_MAX_MEMORY_SIZE=1073741824 \
    NO_GCE_CHECK=true \
    GCE_METADATA_TIMEOUT=0 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    RLDS_IMPORT_MAX_EPISODES=16 \
    RLDS_PYTHON=/opt/rlds/bin/python
RUN sed -i 's#https\?://dl-cdn.alpinelinux.org#https://mirrors.tuna.tsinghua.edu.cn#g' /etc/apk/repositories \
    && apk add --no-cache ffmpeg
COPY --from=rlds-py /usr/local /opt/rlds-python
COPY --from=rlds-py /lib /opt/rlds-host-lib
COPY --from=rlds-py /usr/lib /opt/rlds-host-usr-lib
COPY docs/harness/overlays/zhiyuan-robot-video/rlds_python.sh /opt/rlds/bin/python
RUN chmod +x /opt/rlds/bin/python \
    && /opt/rlds/bin/python -c "import tensorflow, tensorflow_datasets, PIL; print('rlds-python ok')"
COPY label_studio/rlds_decode /label-studio/label_studio/rlds_decode
COPY label_studio/data_import/uploader.py /label-studio/label_studio/data_import/uploader.py
COPY label_studio/data_import/models.py /label-studio/label_studio/data_import/models.py
COPY --from=frontend-builder /label-studio/web/dist /label-studio/web/dist
COPY --from=frontend-builder /label-studio/label_studio/core/static/js /label-studio/label_studio/core/static/js
COPY docs/harness/overlays/zhiyuan-robot-video/patches/base.html /label-studio/label_studio/templates/base.html
# Django 启动时从 STATIC_ROOT/js/manifest.json 解析 Vite hash 入口。
# 官方镜像 BASE_DIR 是 label_studio/core，STATIC_ROOT=label_studio/core/static_build。
RUN mkdir -p /label-studio/label_studio/core/static_build/js \
    && cp /label-studio/label_studio/core/static/js/manifest.json /label-studio/label_studio/core/static_build/js/manifest.json
