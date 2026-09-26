"""Aggregate live-sweep cell JSONs into a markdown table + the key deltas
(closure ablation, scale, decoy, commit), each with a Wilson CI. Prints markdown
ready for docs/RESULTS.md §6.

Pools ROWS across every input file by cell key (model, closure, nudge, decoys,
commit) and recomputes stats from the pooled rows — so a cell run in seed batches
(e.g. 101-105 then 106-110) aggregates to one n=10 cell, and the deltas use the
pooled rates. usage: aggregate_sweep.py cellA*.json cellF*.json ...
"""
import json
import sys
from math import sqrt


def load(path):
    with open(path) as fh:
        return json.load(fh)


def wilson(successes, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def key_of(row):
    return (row["model"], row["closure"], row["nudge"],
            int(row.get("decoys", 1)), int(row.get("commit", 0)))


# Pool rows across all files by cell key.
pooled = {}
for path in sys.argv[1:]:
    doc = load(path)
    rows = doc if isinstance(doc, list) else doc.get("rows", [])
    for r in rows:
        # older rows may lack decoys/commit fields; recover from label if needed
        lbl = r.get("label", "")
        r.setdefault("decoys", 0 if "decoys=0" in lbl else 1)
        r.setdefault("commit", 1 if "commit=1" in lbl else 0)
        pooled.setdefault(key_of(r), []).append(r)

by_cell = {}  # cell key -> computed summary dict
for k, rows in pooled.items():
    n = len(rows)
    solved = sum(1 for r in rows if r["solved"])
    found = sum(1 for r in rows if r["found"])
    fns = sum(1 for r in rows if r["found_not_submitted"])
    rate, lo, hi = wilson(solved, n)
    by_cell[k] = dict(model=k[0], closure=k[1], nudge=k[2], decoys=k[3], commit=k[4],
                      n=n, solved=solved, rate=rate, wilson_lo=lo, wilson_hi=hi,
                      found=found, found_rate=found / n if n else 0.0,
                      found_not_submitted=fns)

print("| model | closure | nudge | decoys | commit | n | solved | solve rate (Wilson95) | found | fns |")
print("|---|---|---|---|---|---|---|---|---|---|")
for k in sorted(by_cell):
    s = by_cell[k]
    print(f"| {s['model']} | {s['closure']} | {s['nudge']} | {s['decoys']} | {s['commit']} | "
          f"{s['n']} | {s['solved']} | {s['rate']:.2f} [{s['wilson_lo']:.2f},{s['wilson_hi']:.2f}] | "
          f"{s['found']}/{s['n']} ({s['found_rate']:.2f}) | {s['found_not_submitted']} |")


def rate_diff(a, b):
    """Wilson CI on the difference via Newcombe's method (approx: independent
    Wilson intervals). Returns (diff, lo, hi)."""
    from math import sqrt
    # crude: diff of rates with a normal-approx CI floor; the per-arm Wilson
    # already caveats small n. This is a directional read, not a p-value.
    pa, na = a["rate"], a["n"]
    pb, nb = b["rate"], b["n"]
    diff = pa - pb
    se = sqrt(max(pa * (1 - pa) / na, 1e-9) + max(pb * (1 - pb) / nb, 1e-9))
    return diff, diff - 1.96 * se, diff + 1.96 * se


print()
# Each delta holds every OTHER variable fixed. Keys: (model,closure,nudge,decoys,commit).
# The baseline cell for all reads is (m, closure=1, nudge=0, decoys=1, commit=0).
for model in sorted({k[0] for k in by_cell}):
    on = by_cell.get((model, 1, 0, 1, 0))
    off = by_cell.get((model, 0, 0, 1, 0))
    if on and off:
        d, lo, hi = rate_diff(on, off)
        print(f"**Closure ablation ({model}, nudge off, decoys on):** solve rate "
              f"{on['rate']:.2f} (on) vs {off['rate']:.2f} (off) — Δ={d:+.2f} [{lo:+.2f},{hi:+.2f}]; "
              f"found rate {on['found_rate']:.2f} vs {off['found_rate']:.2f}")

# scale: closure on, decoys on, commit off, 7b vs 3b
seven = by_cell.get(("qwen2.5-7b-q4km", 1, 0, 1, 0))
three = by_cell.get(("qwen2.5-3b-q4km", 1, 0, 1, 0))
if seven and three:
    d, lo, hi = rate_diff(seven, three)
    print(f"**Scale (closure on, decoys on):** 7B {seven['rate']:.2f} vs 3B {three['rate']:.2f} — "
          f"Δ={d:+.2f} [{lo:+.2f},{hi:+.2f}]; found rate 7B {seven['found_rate']:.2f} vs 3B {three['found_rate']:.2f}")

# decoy effect: 7b closure on, commit off, decoys on vs off
dec_on = by_cell.get(("qwen2.5-7b-q4km", 1, 0, 1, 0))
dec_off = by_cell.get(("qwen2.5-7b-q4km", 1, 0, 0, 0))
if dec_on and dec_off:
    d, lo, hi = rate_diff(dec_off, dec_on)
    print(f"**Decoy effect (7B, closure on):** solve rate {dec_off['rate']:.2f} (no decoys) vs "
          f"{dec_on['rate']:.2f} (decoys) — Δ={d:+.2f} [{lo:+.2f},{hi:+.2f}]; "
          f"found rate {dec_off['found_rate']:.2f} vs {dec_on['found_rate']:.2f}")

# commit-confidence effect: 7b closure on, decoys on, commit on vs off
com_on = by_cell.get(("qwen2.5-7b-q4km", 1, 0, 1, 1))
com_off = by_cell.get(("qwen2.5-7b-q4km", 1, 0, 1, 0))
if com_on and com_off:
    d, lo, hi = rate_diff(com_on, com_off)
    print(f"**Commit-confidence effect (7B, closure on, decoys on):** solve rate "
          f"{com_on['rate']:.2f} (commit rule) vs {com_off['rate']:.2f} (baseline) — "
          f"Δ={d:+.2f} [{lo:+.2f},{hi:+.2f}]; found rate {com_on['found_rate']:.2f} vs {com_off['found_rate']:.2f}")
