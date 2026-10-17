#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

CONTAINER=tmrceo-static
IMAGE=tmrceo-static:latest
PORT=9002
ENV_FILE="${TMRCEO_ENV_FILE:-.env}"

# Validate the image and host-only runtime configuration before replacing it.
docker image inspect "$IMAGE" >/dev/null
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Runtime environment file is missing. Create .env from .env.example."
  exit 1
fi
docker run --rm --env-file "$ENV_FILE" "$IMAGE" python -c 'import app; assert app.app.config["GOOGLE_CLIENT_ID"], "Google client ID is missing"; print("Runtime authentication configuration checked.")'
if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "Stopping old container..."
  docker stop "$CONTAINER"
  echo "Removing old container..."
  docker rm "$CONTAINER"
fi

echo "Starting new container..."
docker run -d \
  --name "$CONTAINER" \
  --env-file "$ENV_FILE" \
  -p "127.0.0.1:${PORT}:8080" \
  -v tmrceo-data:/data \
  --restart unless-stopped \
  "$IMAGE"

echo "Deployment complete: http://localhost:${PORT}/"
