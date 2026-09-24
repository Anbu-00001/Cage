"""eval — the Constraint Cage evaluation-methodology package.

This package is the code companion to `docs/EVALUATION.md` (read that first;
this package implements it, not the other way around). It is intentionally
**dependency-free** (Python 3.11+ stdlib only: `dataclasses`, `enum`,
`statistics`, `random`, `math`, `hashlib`, `json`, `typing`) so the harness
runs on a bare laptop install with nothing to `pip install` — consistent
with the project's low-footprint ethos.

Modules, roughly in dependency order:

    taxonomy.py       Pre-registered outcome/failure codebook (Part 3).
    schema.py          The canonical EpisodeRecord ("one episode as JSON").
    statistics.py       Wilson/Bayesian CIs, bootstrap, ICC(1), kappa (Part 2).
    confounds.py        Thermal/memory validity gates, determinism honesty (Part 5).
    contamination.py    Procedural instances, held-out probes, transfer rate (Part 4).
    metrics.py           Aggregate metrics over batches of episodes (Part 6).
    runner.py            Batch-runner design: trial matrix + execution contract (Part 1).
    report.py            Per-cell summaries tying the above together (Part 7).

Nothing in this package imports from `src/` — the concrete agent loop, VM
orchestrator, and telemetry collectors are a different lane of this repo and
are wired in only through the `Protocol` interfaces in `runner.py`.

Run the unit tests with:

    python3 -m unittest discover -s eval/tests -t . -v

or, if pytest is installed:

    python3 -m pytest eval/tests -v
"""

__version__ = "0.1.0"
