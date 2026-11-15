#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_dir="$(cd "$script_dir/.." && pwd)"
cd "$repo_dir"

if [ -z "${ADAPTION_API_KEY:-}" ]; then
    if [ ! -f ".env" ] || ! grep -Eq '^ADAPTION_API_KEY=[^[:space:]]+' .env; then
        echo "ADAPTION_API_KEY is not set in the environment or .env" >&2
        exit 1
    fi
fi

adaption_dir="pilot/artifacts/adaption"
archive_root="pilot/artifacts/archive"
timestamp="$(date +%Y%m%d-%H%M%S)"
archive_dir="$archive_root/adaption-$timestamp"

if [ -e "$archive_dir" ]; then
    archive_dir="$archive_root/adaption-$timestamp-$$"
fi

mkdir -p "$archive_root"

if [ -e "$adaption_dir" ]; then
    mv "$adaption_dir" "$archive_dir"
    echo "Archived existing Adaption results to: $archive_dir"
fi

mkdir -p "$adaption_dir"

echo "Rebuilding the local pilot image..."
docker compose build plan

echo "Starting the paid Adaption pilot..."
echo "Results will be written to: $adaption_dir"
docker compose --profile live run --rm adaption-pilot

echo "Adaption pilot completed."
