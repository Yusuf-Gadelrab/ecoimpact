#!/bin/bash
cd "$(dirname "$0")"
exec uv run uvicorn main:app --host 127.0.0.1 --port 8900 "$@"
