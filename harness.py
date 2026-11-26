#!/usr/bin/env python3
"""
Local LLM eval harness (stdlib only).

Switches between the compose profiles in ~/inference, waits for each server,
then runs:
  - task suites from tasks/*.jsonl (code tests, answer checks)
  - a long-context "needle in a haystack" grid
and writes raw results + a markdown summary to results/run-<timestamp>/.

Usage:
  ./harness.py                                  # all models, all suites
  ./harness.py --models qwen27b,inkling         # subset
  ./harness.py --suites needle --needle-lengths 8000,64000
  ./harness.py --no-switch --models inkling     # test the server already running
"""
import argparse
import json
import os
import random
import re
import statistics
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
INFERENCE = Path(os.environ.get("INFERENCE_DIR", Path.home() / "inference"))
HTTP_TIMEOUT = 3600  # long prompts can take minutes before the first byte


# ---------------------------------------------------------------- config / env

def load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def load_models(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)["models"]


def api_key_for(cfg: dict, env: dict):
    name = cfg.get("api_key_env")
    if not name:
        return None
    return os.environ.get(name) or env.get(name)


# ---------------------------------------------------------------- HTTP

def http_json(url, payload=None, key=None, timeout=60):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def chat_stream(base, key, model, messages, max_tokens, params):
    """Streaming chat completion. Returns timings measured client-side."""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        **params,
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(base + "/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers=headers, method="POST")
    content, reasoning = [], []
    usage = timings = finish = None
    t_first = t_answer = None
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if body == "[DONE]":
                break
            try:
                ev = json.loads(body)
            except json.JSONDecodeError:
                continue
            if ev.get("usage"):
                usage = ev["usage"]
            if ev.get("timings"):
                timings = ev["timings"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                now = time.perf_counter()
                rc = d.get("reasoning_content") or d.get("reasoning")
                c = d.get("content")
                if rc:
                    reasoning.append(rc)
                    t_first = t_first or now
                if c:
                    content.append(c)
                    t_first = t_first or now
                    t_answer = t_answer or now
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
    t_end = time.perf_counter()

    usage = usage or {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    reasoning_tokens = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")

    ttft = (t_first - t0) if t_first else None
    gen_tps = None
    if timings and timings.get("predicted_per_second"):
        gen_tps = timings["predicted_per_second"]
    elif completion_tokens and t_first and t_end > t_first:
        gen_tps = completion_tokens / (t_end - t_first)
    prefill_tps = None
    if timings and timings.get("prompt_per_second"):
        prefill_tps = timings["prompt_per_second"]
    elif prompt_tokens and ttft:
        prefill_tps = prompt_tokens / ttft

    return {
        "content": "".join(content),
        "reasoning": "".join(reasoning),
        "finish_reason": finish,
        "ttft_s": ttft,
        "answer_start_s": (t_answer - t0) if t_answer else None,
        "total_s": t_end - t0,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "gen_tps": gen_tps,
        "prefill_tps": prefill_tps,
    }


# ---------------------------------------------------------------- server control

def switch_to(profile):
    print(f"\n=== switching to profile '{profile}' ===", flush=True)
    subprocess.run(["docker", "compose", "--profile", "*", "down"],
                   cwd=INFERENCE, check=True)
    subprocess.run(["docker", "compose", "--profile", profile, "up", "-d"],
                   cwd=INFERENCE, check=True)


def wait_ready(base, key, timeout=3600):
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout:
        try:
            data = http_json(base + "/models", key=key, timeout=10)
            models = data.get("data") or []
            if models:
                status = (models[0].get("status") or {}).get("value", "loaded")
                if status == "loaded":
                    return models[0]["id"]
                last = status
        except Exception as e:  # server still starting
            last = type(e).__name__
        print(f"  waiting for server... ({int(time.time() - t0)}s, {last})", flush=True)
        time.sleep(10)
    raise TimeoutError(f"server at {base} not ready after {timeout}s")


# ---------------------------------------------------------------- checks

def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    return blocks[-1] if blocks else text


def run_python(code, tests, timeout=90):
    """Run model code + asserts in a throwaway container with no network."""
    with tempfile.TemporaryDirectory() as d:
        Path(d, "solution.py").write_text(code)
        Path(d, "test_solution.py").write_text("from solution import *\n\n" + tests)
        os.chmod(d, 0o755)
        cmd = ["docker", "run", "--rm", "--network", "none", "--memory", "1g",
               "--cpus", "1", "-v", f"{d}:/work:ro", "-w", "/work",
               "python:3.12-slim", "python", "-B", "test_solution.py"]
        if os.environ.get("HARNESS_LOCAL_PYTHON"):  # self-test only: no docker
            cmd = [sys.executable, "-B", "test_solution.py"]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=d)
            return p.returncode == 0, (p.stdout + p.stderr)[-1500:]
        except subprocess.TimeoutExpired:
            return False, "timeout"


def check(task, answer):
    c = task["check"]
    kind = c["type"]
    if kind == "contains":
        vals = c["value"] if isinstance(c["value"], list) else [c["value"]]
        ok = all(v.lower() in answer.lower() for v in vals)
        return ok, ""
    if kind == "regex":
        return re.search(c["value"], answer, re.S | re.I | re.M) is not None, ""
    if kind == "fullmatch":
        return re.fullmatch(c["value"], answer.strip(), re.S | re.I) is not None, ""
    if kind == "python_tests":
        return run_python(extract_code(answer), c["tests"])
    raise ValueError(f"unknown check type {kind}")


# ---------------------------------------------------------------- needle-in-a-haystack

FILLER = """river stone window garden morning quiet table paper letter music field
cloud harbor station market bridge lantern valley forest meadow village candle
mirror pocket ladder basket orchard island engine signal compass blanket kettle
season silver copper timber marble canvas thread needle button pillow carpet
shadow summer winter autumn spring evening midnight sunrise horizon distance
journey traveler painter farmer sailor teacher student neighbor stranger friend
carried opened watched folded painted gathered wandered remembered whispered
noticed counted followed rested listened answered waited returned crossed
slowly gently quietly brightly softly early later often rarely always never
old new small large warm cold bright dark green blue golden narrow wide long
short heavy light simple careful patient curious distant familiar ordinary
the a an of to in on at by with from under over near beside through across
and but while because although after before when where then still also""".split()

VAULTS = ["north", "harbor", "orchard", "granite", "cedar", "lantern", "meridian", "willow"]


def filler_words(n, rng):
    out = []
    while len(out) < n:
        k = rng.randint(8, 16)
        s = [rng.choice(FILLER) for _ in range(k)]
        s[0] = s[0].capitalize()
        s[-1] += "."
        out.extend(s)
    return out[:n]


def calibrate(base, key, model, params):
    """Measure tokens-per-word for this model's tokenizer."""
    rng = random.Random(0)
    n = 3000
    text = " ".join(filler_words(n, rng))
    r = chat_stream(base, key, model,
                    [{"role": "user", "content": text + "\n\nReply with OK."}],
                    8, params)
    if r["prompt_tokens"]:
        return r["prompt_tokens"] / n
    return 1.3


def needle_prompt(ctx_tokens, depth, tok_per_word, seed):
    rng = random.Random(seed)
    vault = rng.choice(VAULTS)
    code = f"{rng.randint(1000, 9999)}-{rng.choice(['amber', 'cobalt', 'violet', 'saffron'])}-{rng.randint(100, 999)}"
    needle = f"The access code for the {vault} vault is {code}."
    n_words = int(ctx_tokens / tok_per_word)
    before = int(n_words * depth)
    words = filler_words(n_words, rng)
    doc = " ".join(words[:before]) + " " + needle + " " + " ".join(words[before:])
    prompt = (
        "Below is a long document. Read it and answer the question after it.\n\n"
        f"<document>\n{doc}\n</document>\n\n"
        f"Question: What is the access code for the {vault} vault? "
        "Reply with just the code."
    )
    return prompt, code


# ---------------------------------------------------------------- runners

def run_tasks(name, base, key, model, tasks, max_tokens, params, out):
    records = []
    for t in tasks:
        print(f"  [{name}] task {t['id']} ...", end=" ", flush=True)
        rec = {"model": name, "suite": "tasks", "id": t["id"],
               "category": t.get("category", "general")}
        try:
            r = chat_stream(base, key, model,
                            [{"role": "user", "content": t["prompt"]}],
                            t.get("max_tokens", max_tokens), params)
            ok, detail = check(t, r["content"])
            rec.update(r, passed=ok, check_detail=detail)
            print(f"{'PASS' if ok else 'FAIL'}  ttft={fmt(r['ttft_s'])}s  gen={fmt(r['gen_tps'])} tok/s", flush=True)
        except Exception as e:
            rec.update(passed=False, error=repr(e))
            print(f"ERROR {e!r}", flush=True)
        records.append(rec)
        out.write(json.dumps(rec) + "\n")
        out.flush()
    return records


def run_needle(name, base, key, model, lengths, depths, params, out):
    tpw = calibrate(base, key, model, params)
    print(f"  [{name}] tokenizer: {tpw:.3f} tokens/word", flush=True)
    records = []
    for L in lengths:
        for d in depths:
            seed = hash((L, d)) & 0xFFFF
            prompt, code = needle_prompt(L, d, tpw, seed)
            print(f"  [{name}] needle {L // 1000}K @ {int(d * 100)}% ...", end=" ", flush=True)
            rec = {"model": name, "suite": "needle", "id": f"needle-{L}-{d}",
                   "length": L, "depth": d, "expected": code}
            try:
                r = chat_stream(base, key, model,
                                [{"role": "user", "content": prompt}], 4096, params)
                ok = code in r["content"]
                rec.update(r, passed=ok)
                print(f"{'PASS' if ok else 'FAIL'}  prompt={r['prompt_tokens']}  "
                      f"ttft={fmt(r['ttft_s'])}s  prefill={fmt(r['prefill_tps'])} tok/s", flush=True)
            except urllib.error.HTTPError as e:
                rec.update(passed=False, error=f"HTTP {e.code}: {e.read()[:300]!r}")
                print(f"ERROR HTTP {e.code}", flush=True)
            except Exception as e:
                rec.update(passed=False, error=repr(e))
                print(f"ERROR {e!r}", flush=True)
            records.append(rec)
            out.write(json.dumps(rec) + "\n")
            out.flush()
    return records


# ---------------------------------------------------------------- summary

def fmt(x, nd=1):
    return "-" if x is None else f"{x:.{nd}f}"


def med(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def summarize(records, model_names, depths, run_dir):
    L = [f"# Eval run {run_dir.name}", ""]

    tasks = [r for r in records if r["suite"] == "tasks"]
    if tasks:
        L += ["## Tasks", "",
              "| model | category | pass | median TTFT (s) | median gen tok/s | median reasoning tok |",
              "|---|---|---|---|---|---|"]
        for m in model_names:
            rs = [r for r in tasks if r["model"] == m]
            cats = sorted({r["category"] for r in rs}) + ["**all**"]
            for c in cats:
                sub = rs if c == "**all**" else [r for r in rs if r["category"] == c]
                if not sub:
                    continue
                p = sum(r.get("passed", False) for r in sub)
                L.append(f"| {m} | {c} | {p}/{len(sub)} | {fmt(med(r.get('ttft_s') for r in sub))} | "
                         f"{fmt(med(r.get('gen_tps') for r in sub))} | "
                         f"{fmt(med(r.get('reasoning_tokens') for r in sub), 0)} |")
        L.append("")

    needle = [r for r in records if r["suite"] == "needle"]
    if needle:
        L += ["## Long-context recall (needle in a haystack)", "",
              "Cell = pass/fail and time to first token.", ""]
        for m in model_names:
            rs = [r for r in needle if r["model"] == m]
            if not rs:
                continue
            L += [f"### {m}", "",
                  "| length | " + " | ".join(f"{int(d * 100)}%" for d in depths) + " | prefill tok/s |",
                  "|---|" + "---|" * (len(depths) + 1)]
            for length in sorted({r["length"] for r in rs}):
                row = [r for r in rs if r["length"] == length]
                cells = []
                for d in depths:
                    hit = next((r for r in row if r["depth"] == d), None)
                    if hit is None:
                        cells.append("")
                    elif hit.get("error"):
                        cells.append("err")
                    else:
                        cells.append(f"{'✅' if hit['passed'] else '❌'} {fmt(hit.get('ttft_s'))}s")
                L.append(f"| {length // 1000}K | " + " | ".join(cells) +
                         f" | {fmt(med(r.get('prefill_tps') for r in row), 0)} |")
            L.append("")

    (run_dir / "summary.md").write_text("\n".join(L))
    return "\n".join(L)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Local LLM eval harness")
    ap.add_argument("--config", default=str(HERE / "models.toml"))
    ap.add_argument("--models", help="comma-separated names from models.toml (default: all)")
    ap.add_argument("--suites", default="tasks,needle")
    ap.add_argument("--tasks-dir", default=str(HERE / "tasks"))
    ap.add_argument("--needle-lengths", default="8000,32000,64000,128000,190000")
    ap.add_argument("--needle-depths", default="0.1,0.5,0.9")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--no-switch", action="store_true",
                    help="don't touch docker; use whatever server is running")
    args = ap.parse_args()

    env = load_env(INFERENCE / ".env")
    all_models = load_models(Path(args.config))
    names = args.models.split(",") if args.models else list(all_models)
    suites = set(args.suites.split(","))
    lengths = [int(x) for x in args.needle_lengths.split(",")]
    depths = [float(x) for x in args.needle_depths.split(",")]

    tasks = []
    for f in sorted(Path(args.tasks_dir).glob("*.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                tasks.append(json.loads(line))

    run_dir = HERE / "results" / datetime.now().strftime("run-%Y%m%d-%H%M")
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"results -> {run_dir}")

    records = []
    with open(run_dir / "raw.jsonl", "a") as out:
        for name in names:
            cfg = all_models[name]
            base = cfg.get("base_url", "http://localhost:8080/v1")
            key = api_key_for(cfg, env)
            params = cfg.get("params", {})
            if not args.no_switch:
                switch_to(cfg["profile"])
            model_id = wait_ready(base, key)
            print(f"  ready: {model_id}")
            chat_stream(base, key, model_id, [{"role": "user", "content": "hi"}], 16, params)  # warm-up

            if "tasks" in suites and tasks:
                records += run_tasks(name, base, key, model_id, tasks, args.max_tokens, params, out)
            if "needle" in suites:
                records += run_needle(name, base, key, model_id, lengths, depths, params, out)

    print("\n" + summarize(records, names, depths, run_dir))
    print(f"\nraw outputs: {run_dir / 'raw.jsonl'}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
