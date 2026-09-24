"""Aggregate live-sweep cell JSONs into a markdown table + the key deltas
(closure ablation, scale), each with a Wilson CI. Prints markdown ready for
docs/RESULTS.md §6.

usage: aggregate.py cellA.json cellB.json ...
"""
import json
import sys


def load(path):
    with open(path) as fh:
        return json.load(fh)


cells = [load(p) for p in sys.argv[1:]]

print("| Cell | model | closure | nudge | n | solved | solve rate (Wilson95) | found | found_not_submitted |")
print("|---|---|---|---|---|---|---|---|---|")
by_cell = {}  # keyed by (model, closure, nudge, decoys) so cells never collide
for c in cells:
    s = c["summary"]
    rows = c["rows"]
    model = rows[0]["model"] if rows else "?"
    closure = rows[0]["closure"] if rows else "?"
    nudge = rows[0]["nudge"] if rows else "?"
    decoys = 0 if "decoys=0" in s["label"] else 1  # default (older cells): decoys on
    by_cell[(model, closure, nudge, decoys)] = s
    lo, hi = s["wilson_lo"], s["wilson_hi"]
    print(f"| {s['label']} | {model} | {closure} | {nudge} | {s['n']} | {s['solved']} | "
          f"{s['rate']:.2f} [{lo:.2f},{hi:.2f}] | {s['found']}/{s['n']} ({s['found_rate']:.2f}) | "
          f"{s['found_not_submitted']} |")


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
# Each delta holds every OTHER variable fixed (decoys on for the ablation/scale
# reads, since the decoy cell is its own comparison). Keys: (model,closure,nudge,decoys).
for model in sorted({k[0] for k in by_cell}):
    on = by_cell.get((model, 1, 0, 1))
    off = by_cell.get((model, 0, 0, 1))
    if on and off:
        d, lo, hi = rate_diff(on, off)
        print(f"**Closure ablation ({model}, nudge off, decoys on):** solve rate "
              f"{on['rate']:.2f} (on) vs {off['rate']:.2f} (off) — Δ={d:+.2f} [{lo:+.2f},{hi:+.2f}]; "
              f"found rate {on['found_rate']:.2f} vs {off['found_rate']:.2f}")

# scale: closure on, decoys on, 7b vs 3b
seven = by_cell.get(("qwen2.5-7b-q4km", 1, 0, 1))
three = by_cell.get(("qwen2.5-3b-q4km", 1, 0, 1))
if seven and three:
    d, lo, hi = rate_diff(seven, three)
    print(f"**Scale (closure on, decoys on):** 7B {seven['rate']:.2f} vs 3B {three['rate']:.2f} — "
          f"Δ={d:+.2f} [{lo:+.2f},{hi:+.2f}]; found rate 7B {seven['found_rate']:.2f} vs 3B {three['found_rate']:.2f}")

# decoy effect: 7b closure on, decoys on vs off
dec_on = by_cell.get(("qwen2.5-7b-q4km", 1, 0, 1))
dec_off = by_cell.get(("qwen2.5-7b-q4km", 1, 0, 0))
if dec_on and dec_off:
    d, lo, hi = rate_diff(dec_off, dec_on)
    print(f"**Decoy effect (7B, closure on):** solve rate {dec_off['rate']:.2f} (no decoys) vs "
          f"{dec_on['rate']:.2f} (decoys) — Δ={d:+.2f} [{lo:+.2f},{hi:+.2f}]; "
          f"found rate {dec_off['found_rate']:.2f} vs {dec_on['found_rate']:.2f}")
