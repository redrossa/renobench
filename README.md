# RenoBench

My personal benchmark suite for locally-run LLM agents on the workflows I
actually do: coding, literature review, social media, web browsing, online
shopping, health monitoring, personal finance.

v0 is deliberately small — a task set, a stdlib-only harness, and the results
of the runs already done on `forge`. No framework, no plugin system, no
leaderboard plumbing. Just enough to compare models on my own machine and keep
the numbers honest.

## Where it runs

Everything executes on **forge** (RTX 4090 24 GB · Ryzen 5 5600X · 32 GB RAM ·
Ubuntu), alongside the inference stack in `~/inference`: Compose profiles that
serve one model at a time on `127.0.0.1:8080`. GGUF weights live ghq-style
under `~/models`. This repo holds only the tasks, the harness, and the results
— no weights, no secrets (`~/inference/.env` stays on forge).

## Layout

```text
harness.py                  eval runner (stdlib-only OpenAI-compatible client)
bench.sh                    llama.cpp llama-bench throughput runs
models.toml                 model registry -> compose profile + base_url
tasks/                      task suites, one JSONL file per suite
results/                    recorded runs (see results/README.md)
lefthook.yml                git hooks: commit message + markdown lint
scripts/                    hook scripts
mise.toml                   lefthook, markdownlint-cli2, node, python
.markdownlint-cli2.jsonc    markdown rules
```

## What v0 measures

| suite | what | how it's scored |
|---|---|---|
| `tasks` | 7 tasks: `code`, `reasoning`, `domain`, `instruction` | `python_tests` runs the model's code in a network-isolated `python:3.12-slim` container (`--memory 1g --cpus 1`); the rest are regex/fullmatch checks |
| `needle` | long-context recall at 8K/32K/64K/128K/190K tokens, needle at 10%/50%/90% depth | exact needle string must appear in the reply; TTFT and prefill tok/s recorded |
| llama-bench | raw prefill/generate throughput at context 0/32K/128K/192K | `llama-bench` markdown output |

Every task records TTFT, answer-start, total time, prompt/completion/reasoning
tokens and gen/prefill tok/s into `raw.jsonl`, so timings and correctness stay
separable.

## Models under test

| name | served by | weights |
|---|---|---|
| `qwen27b` | llama.cpp `server-cuda`, 200K ctx, q4_0 KV | `unsloth/Qwen3.8-27B-GGUF` → `Qwen3.8-27B-UD-Q4_K_XL.gguf` |
| `inkling` | llama.cpp `server-cuda`, 200K ctx, q8_0 KV, `--n-cpu-moe 0`, `--load-mode none` | `unsloth/Inkling-2-Mini-GGUF` → `Inkling-2-Mini-UD-Q4_K_XL.gguf` |
| `flash` | `strata` (llamaswap), 262K ctx, IQ3_XXS | `qwen3.8-flash-next` |

## Running it

```bash
ssh forge
cd ~/ghq/github.com/redrossa/renobench     # ghq clone of this repo

./harness.py                               # all models, all suites
./harness.py --models qwen27b,inkling      # subset
./harness.py --suites tasks --no-switch    # keep the server that is already up
./harness.py --suites needle --needle-lengths 8000,64000
./bench.sh                                 # throughput (stops the stack first)
```

The harness switches Compose profiles itself, waits for the server to report
`loaded`, warms it up, then evaluates. `INFERENCE_DIR` overrides where
`~/inference` lives.

`harness.py` is stdlib-only (Python ≥ 3.11, for `tomllib`), so it runs on
forge's system `python3` with no setup. `mise.toml` pins the same tooling for
work done off forge.

## Results so far

[`results/run-20261125-0339`](results/run-20261125-0339/summary.md) — 7 tasks
and 15 needle cells per model:

| model | tasks | median TTFT | median gen tok/s | needle recall | prefill tok/s @ 190K |
|---|---|---|---|---|---|
| qwen27b | 5/7 | 0.3 s | 47.5 | 15/15 | 1707 |
| inkling | 7/7 | 0.2 s | 66.2 | 14/15 (fails 90% depth @ 128K) | 307 |
| flash | 7/7 | 1.8 s | 44.9 | 15/15 | 1714 |

Of the three failures, two are token-budget failures rather than wrong answers:
`qwen27b` on `nuclear-decay` spent all 8192 tokens on long division inside its
reasoning channel and never emitted an answer, and `inkling` at 128K/90% started
reciting filler after 4096 tokens. The one clean capability failure is
`qwen27b`'s LRU cache. Details in [`results/README.md`](results/README.md).

Raw llama.cpp throughput for the same weights:
[`results/llama-bench`](results/llama-bench).

## Adding tasks

One JSON object per line in `tasks/*.jsonl`:

```json
{"id": "code-lru-cache", "category": "code", "prompt": "...",
 "max_tokens": 8192,
 "check": {"type": "python_tests", "tests": "assert LRUCache(1)..."}}
```

`check.type` is one of `python_tests` | `regex` | `contains` | `fullmatch`.
`id` must be unique across the suite, because results key on `model` + `id`.

## Dev tooling

Repo-local and hard-pinned via mise — nothing is installed machine-wide:
lefthook 2.2.3, markdownlint-cli2 0.24.2, node 26.13.1, python 3.12.16.

```bash
mise install                          # lefthook, markdownlint-cli2, node, python
mise x -- lefthook install            # wire up .git/hooks (do this once)
mise x -- markdownlint-cli2           # lint markdown
mise x -- markdownlint-cli2 --fix     # lint + autofix
```

Hooks (`lefthook.yml`):

- **pre-commit** — `markdownlint-cli2 --fix` on staged `.md`, fixes re-staged
  automatically. Rules live in `.markdownlint-cli2.jsonc` and cover the recorded
  results too: the ruleset is one llama-bench and harness.py output already
  passes, so the hook leaves benchmark data alone while still catching a results
  table that lost a row or a cell.
- **commit-msg** — `scripts/check-commit-msg.sh` enforces Conventional Commits
  as used on this machine: `feat|fix|docs|style|refactor|perf|test|build|ci|
  chore|revert[(scope)][!]: description`, lowercase, subject ≤ 72 chars, no
  trailing period, and a `BREAKING CHANGE:` footer when `!` is used.

Escape hatch for a commit you really must make now: `git commit --no-verify`.

## Next (not built yet)

- agentic tasks on real workflows: file/shell chores, git, browser sessions
- literature-review, health and personal-finance tasks with personal fixtures
- multiple runs per model for variance, and per-task token budgets
