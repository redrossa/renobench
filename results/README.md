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
- `compare-<name>/summary.md` — one summary over several runs, written by
  `harness.py --compare <run dirs> --out <dir>` (no requests); it links back
  to the runs it was built from.
- `ssd-probe/<model>-<YYYYMMDD>-<HHMM>.{md,jsonl}` — one
  `scripts/ssd-probe.py` run: fresh long requests with machine-wide disk
  reads and swap traffic split into prefill and decode, plus strata's own
  per-request metrics. Re-render the `.md` with `--from <jsonl>`.

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
| [`ssd-probe/flash-20261126-0422`](ssd-probe/flash-20261126-0422.md) | flash | 2 × fresh 71K prompt + 1500 tokens | prefill 1437 tok/s reading 68 GB, decode 79 tok/s reading 12 GB, expert hit 92% |
| [`run-20261126-0446`](run-20261126-0446/summary.md) | flash (IQ3_XXS) | tasks v0+v1 (21) × 3, aggregate 32K/128K × 3 | tasks 59/63, aggregate 5/6 |
| [`run-20261126-0621`](run-20261126-0621/summary.md) | flash-iq3s (IQ3_S) | same | tasks 58/63, aggregate 6/6 |
| [`ssd-probe/flash-iq3s-20261126-0808`](ssd-probe/flash-iq3s-20261126-0808.md) | flash-iq3s | 2 × fresh 71K prompt + 1500 tokens | prefill 996 tok/s reading 85 GB, decode 57 tok/s reading 21 GB, expert hit 88% |
| [`compare-flash-iq3xxs-vs-iq3s`](compare-flash-iq3xxs-vs-iq3s/summary.md) | flash, flash-iq3s | the two runs above, side by side | see below |

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

## How `flash` runs on 32 GB of RAM

Strata's catalog lists IQ3_XXS at 60 GB of RAM for keeping every expert in
memory. With 32 GB, setup picks its low-RAM mode (`--mmap-experts`): a ~14 GB
expert cache in VRAM, the next-hottest experts in the OS page cache, the rest
read from the NVMe on demand. The probe shows what that costs:

- A fresh 71K-token prefill reads ~68 GB from disk, more than the 42.9 GB
  expert file, because each prefill chunk needs every expert and the page cache
  cannot hold them all. It still runs at ~1,440 tok/s.
- Decode reads ~10–25 GB per 1,500 tokens at ~1 GB/s, far under what the drive
  can do. A 92% VRAM hit rate and speculative decoding (several tokens checked
  per pass) keep the reads off the critical path: ~75–82 tok/s.
- In real use almost nothing is prefilled fresh: 98% of prompt tokens on the
  pre-change server (11.3M of 11.6M) came from its conversation cache.
- RAM, not the SSD, is the tight resource. The kernel keeps hot expert pages
  and swaps out strata's cold anonymous memory: parked conversations, heap, and
  (probably) the host-side KV of prompts over 64K. With strata's default 8 GiB
  conversation cache that filled the 8 GiB swap file, so the cache is now
  capped at 2 GiB (`STRATA_SET=conversation-cache-mib=2048` in
  `~/inference/compose.yaml`). Swap then settled at 4–5 GB after the probe.

## IQ3_XXS vs IQ3_S on forge

Same model, same strata engine and settings (262K ctx, int8 KV,
`--mmap-experts`, 2 GiB conversation cache); only the expert quant differs
(2.84 vs 3.33 bits per weight, 42.9 vs 50.3 GB of experts).

| | IQ3_XXS (`flash`) | IQ3_S (`flash-iq3s`) |
|---|---|---|
| tasks (21 × 3) | 59/63 | 58/63 |
| aggregate (2 lengths × 3) | 5/6 | 6/6 |
| median gen tok/s over the tasks | 60.9 | 44.7 |
| median TTFT over the tasks | 3.3 s | 4.8 s |
| probe prefill, fresh 71K prompt | 1,437 tok/s | 996 tok/s |
| probe decode | 78.6 tok/s | 56.5 tok/s |
| VRAM expert cache | 8,449 experts (34%) | 7,012 experts (29%) |
| probe expert hit rate | 92% | 86–89% |
| disk read per fresh prefill | 68 GB | 85 GB |

Quality comes out even, 64/69 each. With three samples per task a one- or
two-sample swing is noise, and the misses are the same kind in both:

- The mortgage tasks need 360-month compound interest done by hand. Strata
  closes the thinking at 75% of `max_tokens` (its `answer_room` rule: 12,288 of
  16,384) and the model then answers from an unfinished calculation. That cut
  hits both quants the same way.
- IQ3_S's two code misses (an unbound `nonlocal`, an off-by-one index) were
  written right after the same cut; IQ3_XXS hit the cut on code too and got
  lucky. IQ3_XXS's one aggregate miss was 20 cents off at 128K.

Speed is the clear difference: IQ3_S is ~27–31% slower everywhere, because
its bigger experts leave fewer in VRAM and more to read from RAM and the NVMe.
On this 32 GB machine IQ3_XXS is the better trade; the strata catalog's
"matches the full model" for IQ3_S does not show up at this benchmark's
resolution.

## Environment for the runs above

- Machine: forge — RTX 4090 24 GB, Ryzen 5 5600X (12 threads), 32 GB RAM
- llama.cpp server: `ghcr.io/ggml-org/llama.cpp:server-cuda`, build
  `af5c58347 (12679)`
- llama-bench: `ghcr.io/ggml-org/llama.cpp:full-cuda`, same build
- `flash`: `ghcr.io/niko1221/strata:latest-cuda13` (engine 0.1.67), 262144
  ctx, IQ3_XXS, int8 KV, `--mmap-experts`; from the ssd-probe run on,
  conversation cache 2048 MiB (default 8192)
- llama.cpp serving: `-c 200000 -np 1 -fa on -ngl 999 --jinja`
  - qwen27b: `-ctk q4_0 -ctv q4_0`
  - inkling: `-ctk q8_0 -ctv q8_0 -ub 64 --n-cpu-moe 0 --load-mode none`
    plus `--temp 1.0 --top-p 1.0 --top-k 0 --min-p 0.0`
- Harness defaults: `--max-tokens 8192` (needle capped at 4096), needle depths
  0.1/0.5/0.9, one sample per cell — no repeats yet, so "median" means across
  tasks, not across runs.
