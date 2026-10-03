#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v fly >/dev/null 2>&1; then
  fly deploy --config fly.toml || echo "fly deploy skipped or failed (auth/remote)"
else
  echo "fly CLI not installed; backend image is defined in bubble_compass/Dockerfile"
fi

if command -v vercel >/dev/null 2>&1; then
  (cd bubble_compass/body && vercel --yes --prod) || echo "vercel deploy skipped or failed (auth/remote)"
else
  echo "vercel CLI not installed; frontend build lives in bubble_compass/body"
fi

echo "Redis: set REDIS_URL to an Upstash or local redis:// instance"
