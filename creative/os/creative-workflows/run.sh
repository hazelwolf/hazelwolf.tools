#!/usr/bin/env bash
# Start ComfyUI with data directories next to this script, not inside the submodule.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --directory "$root/upstream" python main.py \
  --listen 127.0.0.1 \
  --port 8188 \
  --base-directory "$root" \
  "$@"
