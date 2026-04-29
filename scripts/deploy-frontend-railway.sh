#!/usr/bin/env bash
# 从「仓库根」上传，保证压缩包内存在 frontend/，与 Railway 里 Root Directory=frontend 一致。
# 切勿在 frontend/ 子目录执行 railway up，否则会报 Could not find root directory: /frontend
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec railway up -s quant-trading -c -m "CLI: frontend from monorepo root (${USER:-local})" "$@"
