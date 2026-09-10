#!/bin/sh
# Debian glibc CPython + TensorFlow, running inside the official Alpine LS image.
# Alpine's own Python 3.13 cannot import official tensorflow wheels.
set -eu
# arm64: ld-linux-aarch64.so.1 ； amd64: ld-linux-x86-64.so.2
LOADER=$(ls /opt/rlds-host-lib/ld-linux-*.so.* /opt/rlds-host-lib/*/ld-linux-*.so.* 2>/dev/null | head -1)
GNU=$(ls -d /opt/rlds-host-lib/*-linux-gnu 2>/dev/null | head -1)
USR_GNU=$(ls -d /opt/rlds-host-usr-lib/*-linux-gnu 2>/dev/null | head -1)
if [ -z "$LOADER" ] || [ ! -x /opt/rlds-python/bin/python3 ]; then
  echo "rlds-python: missing glibc loader or /opt/rlds-python/bin/python3" >&2
  ls -l /opt/rlds-host-lib /opt/rlds-host-lib/*/ld-linux* /opt/rlds-python/bin 2>&1 | head -40 >&2 || true
  exit 127
fi
export PYTHONPATH="/label-studio/label_studio${PYTHONPATH:+:$PYTHONPATH}"
# ffmpeg comes from Alpine apk (musl); this interpreter is only for TensorFlow.
export PATH="/usr/bin:/opt/rlds-python/bin:${PATH}"
exec "$LOADER" --library-path "/opt/rlds-python/lib:${GNU}:${USR_GNU:-}" \
  /opt/rlds-python/bin/python3 "$@"
