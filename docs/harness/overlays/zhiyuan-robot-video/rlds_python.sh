#!/bin/sh
# Debian glibc CPython + TensorFlow, running inside the official Alpine LS image.
# Alpine's own Python 3.13 cannot import official tensorflow wheels.
set -eu
LOADER=$(ls /opt/rlds-host-lib/ld-linux-*.so.1 /opt/rlds-host-lib/*/ld-linux-*.so.1 2>/dev/null | head -1)
GNU=$(ls -d /opt/rlds-host-lib/*-linux-gnu 2>/dev/null | head -1)
USR_GNU=$(ls -d /opt/rlds-host-usr-lib/*-linux-gnu 2>/dev/null | head -1)
export PYTHONPATH="/label-studio/label_studio${PYTHONPATH:+:$PYTHONPATH}"
# ffmpeg comes from Alpine apk (musl); this interpreter is only for TensorFlow.
export PATH="/usr/bin:/opt/rlds-python/bin:${PATH}"
exec "$LOADER" --library-path "/opt/rlds-python/lib:${GNU}:${USR_GNU:-}" \
  /opt/rlds-python/bin/python3 "$@"
