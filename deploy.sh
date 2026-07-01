#!/usr/bin/env bash
# Deploy AgentParley plugin to the agent-zero docker container.
# Usage: ./deploy.sh [--restart]

set -euo pipefail

CONTAINER="agent-zero"
DEST="/a0/usr/plugins/parley"

echo "→ Copying plugin files to $CONTAINER:$DEST ..."
docker -H ssh://docker.lan exec "$CONTAINER" mkdir -p "$DEST"
docker -H ssh://docker.lan cp . "$CONTAINER:$DEST"

echo "→ Clearing stale .pyc cache ..."
docker -H ssh://docker.lan exec "$CONTAINER" find "$DEST" -name "*.pyc" -delete

echo "→ Running execute.py inside container ..."
docker -H ssh://docker.lan exec "$CONTAINER" /opt/venv-a0/bin/python "$DEST/execute.py"

if [[ "${1:-}" == "--restart" ]]; then
  echo "→ Restarting agent-zero ..."
  docker -H ssh://docker.lan restart "$CONTAINER"
fi

echo "✓ Done. Plugin installed at $DEST"
