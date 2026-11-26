# Results

Every recorded run is committed here. This folder is the history of the
benchmark, not scratch space.

## Conventions

- `run-<YYYYMMDD>-<HHMM>/` — one harness run, written by `harness.py`
  - `summary.md` — per-category pass counts, medians, the needle grid;
    generated, so it diffs cleanly
  - `raw.jsonl` — one record per (model, suite, task): full reply text,
    reasoning text, timings, token counts, pass/fail and the checker output.
    ~114K per run is fine; it's what makes a failure diagnosable months
    later.
- `llama-bench/<model>.md` — `llama-bench` output, refreshed in place by
  `bench.sh`: throughput of the served weights, not an agent run.

Generated files are linted like everything else, against a ruleset llama-bench
and harness.py output already passes — so the hook never rewrites recorded
numbers, but a row that lost a cell or a table that lost a line fails the
commit. If a results file is wrong, regenerate it with `harness.py` /
`bench.sh` rather than patching it by hand.

A run is complete when `summary.md` exists and every model in `models.toml`
(or the subset given to `--models`) appears in `raw.jsonl`.

## Index

| run | models | suites | result |
|---|---|---|---|
| [`run-20261125-0339`](run-20261125-0339/summary.md) | qwen27b, inkling, flash | tasks (7), needle (8K–190K × 3 depths) | tasks 5/7 · 7/7 · 7/7 — needle 15/15 · 14/15 · 15/15 |
| [`llama-bench/qwen27b.md`](llama-bench/qwen27b.md) | qwen27b | pp2048 / tg256 @ ctx 0, 32K, 128K, 192K | prefill 3498 → 1096 tok/s, generate 48 → 29 tok/s |
| [`llama-bench/inkling.md`](llama-bench/inkling.md) | inkling | same grid | prefill 1248 → 167 tok/s, generate 73 → 45 tok/s |

## What the v0 failures actually were

- `qwen27b` / `code-lru-cache` — a real failure: it defined `Node` as a nested
  class, then referenced it unqualified (`NameError`). The checker output is in
  `raw.jsonl`.
- `qwen27b` / `nuclear-decay` — truncation, not a knowledge error:
  `finish_reason=length` at 8192 completion tokens, computing `0.5^(30/8.02)`
  by long division inside the reasoning channel and never emitting the
  `ANSWER:` line.
- `inkling` / `needle-128000-0.9` — a long-context breakdown, not a recall
  miss: `finish_reason=length` at 4096 tokens, with the reasoning channel
  reciting haystack filler instead of answering. Its 190K cells pass, so it
  reads as a wobble specific to 128K.

Two of the three failures are token-budget failures, so the v0 budgets (8192
for tasks, 4096 for needle) are part of the measurement. Repeats and per-task
budgets are the next thing to fix.

## Environment for the runs above

- Machine: forge — RTX 4090 24 GB, Ryzen 5 5600X (12 threads), 32 GB RAM
- llama.cpp server: `ghcr.io/ggml-org/llama.cpp:server-cuda`, build
  `af5c58347 (12679)`
- llama-bench: `ghcr.io/ggml-org/llama.cpp:full-cuda`, same build
- `flash`: `ghcr.io/niko1221/strata:latest-cuda13`, 262144 ctx, IQ3_XXS
- llama.cpp serving: `-c 200000 -np 1 -fa on -ngl 999 --jinja`
  - qwen27b: `-ctk q4_0 -ctv q4_0`
  - inkling: `-ctk q8_0 -ctv q8_0 -ub 64 --n-cpu-moe 0 --load-mode none`
    plus `--temp 1.0 --top-p 1.0 --top-k 0 --min-p 0.0`
- Harness defaults: `--max-tokens 8192` (needle capped at 4096), needle depths
  0.1/0.5/0.9, one sample per cell — no repeats yet, so "median" means across
  tasks, not across runs.
