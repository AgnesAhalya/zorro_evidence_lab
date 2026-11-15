#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_dir="$(cd "$script_dir/.." && pwd)"
cd "$repo_dir"

musr_revision="7c365b439a222150f317764d4f16ae6c96d7d94a3"
narracrime_revision="3f48324fde2bc332d48e3a61608a90fd2a4e7923"

if [ ! -f "data/vendor/musr/murder_mystery.csv" ]; then
    rm -rf data/vendor/musr
    git clone --filter=blob:none --no-checkout \
        https://huggingface.co/datasets/TAUR-Lab/MuSR data/vendor/musr
    git -C data/vendor/musr checkout --detach "$musr_revision"
fi

if [ ! -d "data/vendor/evar/dataset" ]; then
    rm -rf data/vendor/evar
    git clone --filter=blob:none --no-checkout \
        https://github.com/Cosinecos/EVAR.git data/vendor/evar
    git -C data/vendor/evar checkout --detach "$narracrime_revision"
fi

test -f data/vendor/musr/murder_mystery.csv
test -d data/vendor/evar/dataset
echo "Pinned datasets are ready."
