#!/usr/bin/env bash
set -euo pipefail

expected_sha="${1:?expected commit SHA is required}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

actual_sha="$(git rev-parse HEAD)"
if [ "$actual_sha" != "$expected_sha" ]; then
  echo "Refusing deployment: source SHA mismatch expected=$expected_sha actual=$actual_sha"
  exit 1
fi

docker compose up -d --build --remove-orphans

healthy=0
for _ in $(seq 1 30); do
  if curl -fsS http://localhost:8000/health >/dev/null; then
    healthy=1
    break
  fi
  sleep 2
done

if [ "$healthy" -ne 1 ]; then
  echo "Deployment health check failed"
  docker compose ps || true
  docker compose logs --tail=100 mcp-server || true
  exit 1
fi

echo "Deployment verified at $expected_sha"
