#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
echo "Preview URL: http://localhost:8002/"
echo "Requires: python3 -m pip install -r requirements.txt"
DATA_DIR="${DATA_DIR:-/tmp/tmrceo-preview-data}" python3 -m flask --app app run --host 127.0.0.1 --port 8002
