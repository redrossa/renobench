#!/usr/bin/env python3
"""
Disk / memory probe for one long, fresh request (stdlib only, run on forge).

Sends a prompt the server cannot have cached (random filler + a random id), lets
the model generate, and records how much the machine read from its physical
disks and how hard it leaned on swap -- split at the first streamed token into
prefill and decode. Built for strata, which streams MoE experts from RAM/NVMe,
but works against any OpenAI-compatible server in models.toml; strata's
per-request /metrics (expert-cache hit rate, reuse, drafts) are added when the
server exposes them.

Disk counters are machine-wide, so run it with nothing else busy.

Usage (on forge, with the model already being served):
  scripts/ssd-probe.py --model flash
  scripts/ssd-probe.py --model flash --runs 3 --prompt-tokens 72000 --max-tokens 1500

Writes results/ssd-probe/<model>-<YYYYMMDD-HHMM>.{md,jsonl}. Re-render a
report from its raw file (never edit recorded numbers by hand):
  scripts/ssd-probe.py --from results/ssd-probe/flash-20261126-0419.jsonl
"""
import argparse
import json
import random
import statistics
import sys
import time
import urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import harness  # noqa: E402  (stdlib-only sibling module)

SKIP_DEV = ("loop", "ram", "zram", "dm-", "md", "sr", "fd")
STRATA_FIELDS = ("prompt_tokens", "reused", "prompt_ms", "output_tokens", "decode_ms",
                 "decode_tok_s", "hit_rate", "pcie_share", "file_mb",
                 "drafts_offered", "drafts_accepted")


# ---------------------------------------------------------------- counters

def disks():
    """Whole physical disks (no partitions, loop, ram or device-mapper)."""
    return sorted(p.name for p in Path("/sys/block").iterdir()
                  if not p.name.startswith(SKIP_DEV))


def disk_read_bytes(devs):
    total = 0
    for line in Path("/proc/diskstats").read_text().splitlines():
        f = line.split()
        if f[2] in devs:
            total += int(f[5]) * 512  # sectors read
    return total


def meminfo():
    m = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        m[k] = int(v.split()[0]) * 1024
    return m


def vmstat():
    v = dict(line.split() for line in Path("/proc/vmstat").read_text().splitlines())
    return {k: int(v[k]) for k in ("pgmajfault", "pswpin", "pswpout")}


def snap(devs):
    m = meminfo()
    return {"t": time.perf_counter(), "disk": disk_read_bytes(devs), **vmstat(),
            "swap_used": m["SwapTotal"] - m["SwapFree"], "mem_avail": m["MemAvailable"]}


def delta(a, b):
    s = max(b["t"] - a["t"], 1e-9)
    return {"s": s, "disk_gb": (b["disk"] - a["disk"]) / 1e9,
            "disk_mb_s": (b["disk"] - a["disk"]) / 1e6 / s,
            "majfault": b["pgmajfault"] - a["pgmajfault"],
            "swapin_pages": b["pswpin"] - a["pswpin"],
            "swapout_pages": b["pswpout"] - a["pswpout"]}


# ---------------------------------------------------------------- strata extras

def strata_metrics(root, key):
    """strata's JSON /metrics, or None (llama.cpp serves Prometheus text there)."""
    try:
        m = harness.http_json(root + "/metrics", key=key, timeout=10)
        return m if isinstance(m, dict) and "requests" in m else None
    except Exception:
        return None


def wait_idle(root, key, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        m = strata_metrics(root, key)
        if m is None or ((m.get("live") or {}).get("state") == "idle"
                         and not (m.get("live") or {}).get("queued")):
            return
        print("  server busy, waiting...", flush=True)
        time.sleep(10)
    raise TimeoutError("server never went idle")


# ---------------------------------------------------------------- one run

def fresh_prompt(n_tokens, tok_per_word):
    rng = random.Random(time.time_ns())
    words = harness.filler_words(int(n_tokens / tok_per_word), rng)
    return (f"Document {rng.getrandbits(64):016x}.\n\n" + " ".join(words) +
            "\n\nWrite a long, detailed essay (at least 1200 words) inventing a "
            "history for the place this document describes.")


def run_once(base, root, key, model, prompt, max_tokens, params, devs):
    wait_idle(root, key)
    marks = {}
    s0 = snap(devs)
    wall0 = time.time()
    r = harness.chat_stream(base, key, model, [{"role": "user", "content": prompt}],
                            max_tokens, params,
                            on_first=lambda: marks.setdefault("first", snap(devs)))
    s2 = snap(devs)
    s1 = marks.get("first", s2)
    rec = {k: r[k] for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens",
                             "finish_reason", "ttft_s", "total_s", "gen_tps", "prefill_tps")}
    rec.update(prefill=delta(s0, s1), decode=delta(s1, s2),
               swap_used_before_mb=s0["swap_used"] / 2**20,
               swap_used_after_mb=s2["swap_used"] / 2**20,
               mem_avail_after_mb=s2["mem_avail"] / 2**20)
    m = strata_metrics(root, key)
    if m:
        mine = [q for q in m["requests"] if q.get("time", 0) >= wall0 - 1]
        if mine:
            q = max(mine, key=lambda q: q["time"])
            rec["strata"] = {k: q.get(k) for k in STRATA_FIELDS}
    return rec


# ---------------------------------------------------------------- report

def fmt(x, nd=1):
    return "-" if x is None else f"{x:,.{nd}f}"


def write_report(path, recs):
    first = recs[0]
    req = first["request"]
    L = [f"# Disk / memory probe: {first['model']}", "",
         f"- served model: `{first['model_id']}`",
         f"- recorded: {first['started']} by `scripts/ssd-probe.py`",
         f"- request: fresh ~{req['prompt_tokens']:,}-token prompt, "
         f"`max_tokens` {req['max_tokens']}",
         "- prompt is random filler with a random id, so nothing is reused",
         f"- disk reads: `{', '.join(req['disks'])}` in `/proc/diskstats`",
         "- disk counters are machine-wide; nothing else was running",
         "- prefill/decode split at the first streamed token", "",
         "| run | prompt tok | reused | prefill s | prefill tok/s | prefill read GB | "
         "out tok | decode s | decode tok/s | decode read GB | expert hit | "
         "swap out MB | swap after MB |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(recs, 1):
        st = r.get("strata") or {}
        p, d = r["prefill"], r["decode"]
        pre_tps = r["prompt_tokens"] / p["s"] if r.get("prompt_tokens") else None
        dec_tps = st.get("decode_tok_s") or (
            r["completion_tokens"] / d["s"] if r.get("completion_tokens") else None)
        hit = st.get("hit_rate")
        L.append(f"| {i} | {fmt(r.get('prompt_tokens'), 0)} | {fmt(st.get('reused'), 0)} | "
                 f"{fmt(p['s'])} | {fmt(pre_tps, 0)} | {fmt(p['disk_gb'], 2)} | "
                 f"{fmt(r.get('completion_tokens'), 0)} | {fmt(d['s'])} | {fmt(dec_tps)} | "
                 f"{fmt(d['disk_gb'], 2)} | {'-' if hit is None else f'{hit:.1%}'} | "
                 f"{fmt((p['swapout_pages'] + d['swapout_pages']) * 4096 / 2**20, 0)} | "
                 f"{fmt(r['swap_used_after_mb'], 0)} |")
    if len(recs) > 1:
        def m(f, nd=1):
            vals = [v for v in map(f, recs) if v is not None]
            return fmt(statistics.median(vals) if vals else None, nd)
        L += ["", f"Medians over {len(recs)} runs:", "",
              "| prefill tok/s | prefill read GB | decode tok/s | decode read GB |",
              "|---|---|---|---|",
              f"| {m(lambda r: r['prompt_tokens'] / r['prefill']['s'] if r.get('prompt_tokens') else None, 0)} "
              f"| {m(lambda r: r['prefill']['disk_gb'], 2)} "
              f"| {m(lambda r: (r.get('strata') or {}).get('decode_tok_s'))} "
              f"| {m(lambda r: r['decode']['disk_gb'], 2)} |"]
    L.append("")
    path.write_text("\n".join(L))


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="disk/memory probe for one long fresh request")
    ap.add_argument("--config", default=str(ROOT / "models.toml"))
    ap.add_argument("--model", help="name from models.toml")
    ap.add_argument("--from", dest="from_raw", metavar="JSONL",
                    help="re-render the .md for an existing raw file, no requests")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--prompt-tokens", type=int, default=72000)
    ap.add_argument("--max-tokens", type=int, default=1500)
    args = ap.parse_args()

    if args.from_raw:
        raw = Path(args.from_raw)
        recs = [json.loads(x) for x in raw.read_text().splitlines() if x.strip()]
        write_report(raw.with_suffix(".md"), recs)
        print(raw.with_suffix(".md").read_text())
        return
    if not args.model:
        ap.error("--model is required (or --from to re-render)")

    cfg = harness.load_models(Path(args.config))[args.model]
    env = harness.load_env(harness.INFERENCE / ".env")
    key = harness.api_key_for(cfg, env)
    base = cfg.get("base_url", "http://localhost:8080/v1").rstrip("/")
    root = base.removesuffix("/v1")
    params = cfg.get("params", {})
    devs = disks()

    model_id = harness.wait_ready(base, key)
    tpw = harness.calibrate(base, key, model_id, params)
    print(f"[{args.model}] {model_id}: {tpw:.3f} tokens/word, disks {devs}", flush=True)

    out_dir = ROOT / "results" / "ssd-probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    stem = out_dir / f"{args.model}-{started.strftime('%Y%m%d-%H%M')}"
    request = {"prompt_tokens": args.prompt_tokens, "max_tokens": args.max_tokens,
               "disks": devs}
    recs = []
    with open(stem.with_suffix(".jsonl"), "a") as raw:
        for i in range(args.runs):
            print(f"  run {i + 1}/{args.runs} ...", end=" ", flush=True)
            try:
                rec = run_once(base, root, key, model_id,
                               fresh_prompt(args.prompt_tokens, tpw),
                               args.max_tokens, params, devs)
            except urllib.error.HTTPError as e:
                sys.exit(f"HTTP {e.code}: {e.read()[:400]!r}")
            rec.update(model=args.model, model_id=model_id, run=i + 1,
                       started=started.strftime("%Y-%m-%d %H:%M"), request=request)
            raw.write(json.dumps(rec) + "\n")
            raw.flush()
            recs.append(rec)
            print(f"prefill {rec['prefill']['s']:.1f}s / {rec['prefill']['disk_gb']:.1f} GB, "
                  f"decode {rec['decode']['s']:.1f}s / {rec['decode']['disk_gb']:.1f} GB", flush=True)
    write_report(stem.with_suffix(".md"), recs)
    print((stem.with_suffix(".md")).read_text())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
