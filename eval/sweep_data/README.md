# Live-cage seed-sweep results (raw)

Raw per-cell JSON backing **docs/RESULTS.md §6** — the first seed sweep of the agent
against the live cage. Each file is one `(model, condition)` cell over 5 paired,
seed-distinct Objective-A fixtures (seeds 101–105), temp 0, `step_budget=6`,
`n_predict=384`. Each row records **found** (token reached an observation) and **solved**
(submitted + host-scored), so `found ∧ ¬solved = found_not_submitted`.

| File | Model | Closure | Nudge | Decoys | solved | found |
|---|---|---|---|---|---|---|
| `cellA_7b_closure1.json` | 7B | on | off | yes | 2/5 | 5/5 |
| `cellC_7b_closure0.json` | 7B | off | off | yes | 1/5 | 5/5 |
| `cellB_3b_closure1.json` | 3B | on | off | yes | 0/5 | 0/5 |
| `cellD_7b_closure1_nudge1.json` | 7B | on | on | yes | 2/5 | 5/5 |
| `cellE_7b_closure1_nodecoy.json` | 7B | on | off | **no** | **4/5** | 5/5 |

**Headline:** scale governs *finding* (7B 5/5 vs 3B 0/5); the closure prompt turns the
*submit* instruction on; and the residual `found_not_submitted` gap is **decoy-induced
verification hesitation** — removing decoys doubles the solve rate (0.40 → 0.80). See §6 for
the full three-rung interpretation and the honest (n=5, underpowered) caveats.

## Reproduce

Bring up the guest (docs/GUEST-SETUP.md) and a llama-server on `127.0.0.1:8080`, then:

```bash
# one cell: MODEL SEEDS CLOSURE NUDGE OUT [DECOYS]
PYTHONPATH=. python3 eval/run_live_sweep.py qwen2.5-7b-q4km 101,102,103,104,105 1 0 out.json 1
# aggregate several cells into the §6 table + deltas
PYTHONPATH=. python3 eval/aggregate_sweep.py eval/sweep_data/cell*.json
```

The wiring is `eval/live_cage.py` (`LiveCageEnvController` plants seed instances over vsock as
the unprivileged `cage` user; `RealTelemetryCollector` gates on temperature). These are the
**tractable fixture** (find a planted token); the root-provisioned L1–L7 engineered
boundaries (`challenges/specs.py`) are a separate, heavier sweep.
