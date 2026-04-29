#!/usr/bin/env bash
# 从「仓库根」上传，保证压缩包内存在 backend/，与 Railway 里 Root Directory=backend 一致。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec railway up -s terrific-recreation -c -m "CLI: backend deploy from monorepo root" "$@"
