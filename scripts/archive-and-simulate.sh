#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_dir="$(cd "$script_dir/.." && pwd)"
cd "$repo_dir"

simulation_dir="pilot/artifacts/simulation"
archive_root="pilot/artifacts/archive"
timestamp="$(date +%Y%m%d-%H%M%S)"
archive_dir="$archive_root/simulation-$timestamp"

if [ -e "$archive_dir" ]; then
    archive_dir="$archive_root/simulation-$timestamp-$$"
fi

mkdir -p "$archive_root"

if [ -e "$simulation_dir" ]; then
    mv "$simulation_dir" "$archive_dir"
    echo "Archived existing simulation artifacts to: $archive_dir"
fi

mkdir -p "$simulation_dir"

echo "Rebuilding the local simulation image..."
docker compose build plan
docker compose run --rm test
echo "Running a fresh offline simulation..."
docker compose run --rm simulate

echo "Fresh simulation completed."
