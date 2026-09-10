#!/bin/bash
set -euo pipefail
ROOT="${HOME}/zhiyuan-label-studio"
mkdir -p "${ROOT}/data"
docker rm -f zhiyuan-ls >/dev/null 2>&1 || true
docker run -d \
  --name zhiyuan-ls \
  --restart unless-stopped \
  -p 8080:8080 \
  -v "${ROOT}/data:/label-studio/data" \
  -e DATA_UPLOAD_MAX_MEMORY_SIZE=1073741824 \
  -e NO_GCE_CHECK=true \
  -e GCE_METADATA_TIMEOUT=0 \
  -e TF_CPP_MIN_LOG_LEVEL=2 \
  -e RLDS_IMPORT_MAX_EPISODES=16 \
  -e LABEL_STUDIO_HOST=http://192.168.110.23:8080 \
  zhiyuan-label-studio:ux
echo "已启动 http://192.168.110.23:8080/"
