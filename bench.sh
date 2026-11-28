#!/usr/bin/env bash
# Raw llama.cpp throughput (llama-bench) for the llama.cpp-served models.
# Run this on forge; it stops the inference stack first so the GPU is free.
#   ./bench.sh                  # every model below
#   ./bench.sh inkling          # only the named ones
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFER="${INFERENCE_DIR:-$HOME/inference}"
OUT="$HERE/results/llama-bench"
mkdir -p "$OUT"

source "$INFER/.env"   # QWEN27B, INKLING, INKLING_CPU_MOE = model paths / flags

wanted() { [ "$#" -eq 0 ] || [[ " $* " == *" $NAME "* ]]; }

(cd "$INFER" && docker compose --profile '*' down)   # free the GPU

run() {  # name, model, extra flags
  docker run --rm --gpus all -v "$HOME/models:/models:ro" --entrypoint /app/llama-bench \
    ghcr.io/ggml-org/llama.cpp:full-cuda \
    -m "/models/$2" -fa 1 -ngl 999 $3 \
    -p 2048 -n 256 -d 0,32768,131072,196608 -r 2 -o md | tee "$OUT/$1.md"
}

NAME=qwen27b; wanted "$@" && run qwen27b "$QWEN27B" "-ctk q4_0 -ctv q4_0"
NAME=inkling; wanted "$@" && run inkling "$INKLING" "-ctk q8_0 -ctv q8_0 -ub 64 --n-cpu-moe $INKLING_CPU_MOE"
exit 0
