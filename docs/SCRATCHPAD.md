# Scratchpad — Constraint Cage build-up

> Working notes for the session that turns the two design docs (`constraint-cage.md`,
> `constraint-cage-v2.md`) into a resume-level / partially-industry-level project.
> This file is append-mostly; newest status at the top of each section.

## Session goal (2026-09-24)

Take the two teardown/positioning docs and lift the whole thing from "a very good
design document" to "a repo a hiring manager would open and believe." Concretely:

1. Real, navigable repo skeleton (not just prose) — code stubs, configs, scripts.
2. Consolidated **research-data** md files (verified landscape + methodology + evidence).
3. A polished README + positioning + resume framing.
4. Concrete cage/challenge design + eval harness spec.
5. CLAUDE.md (repo guide for future agents) + memory files.

## Hardware ground truth (measured this session)

- `nproc` = 12 threads → matches "2 P-core + 8 E-core, 12 threads" spec. [FACT]
- `free -h`: 15Gi total RAM, ~10Gi available at rest. Matches 16 GB design target. [FACT]
- Memory channels: **NOT yet measured** — this is the single most important [OPEN]
  from both docs (`sudo dmidecode -t memory`). Blocks converting tok/s [EST]→[FACT].
- tok/s, sustained clock, PkgWatt: not yet measured (needs llama.cpp build).

## Fleet plan (sonnet-5 agents, launched in parallel)

| Agent | Lane | Output files | Status |
|---|---|---|---|
| A | Repo scaffold + runnable code skeleton | `src/**`, `scripts/**`, `config/**`, `run.sh`, `docs/ARCHITECTURE.md` | launching |
| B | Research validation + literature sweep | `docs/RESEARCH.md`, `docs/REFERENCES.md` | ✅ DONE (RESEARCH 226L, REFERENCES 254L) |
| C | Eval methodology + stats harness | `docs/EVALUATION.md`, `eval/**` | ✅ DONE (EVALUATION 406L; eval/ + 50/50 tests passing live) |
| D | Cage + challenge design (Levels 1-7, procedural) | `docs/CHALLENGES.md`, `challenges/**` | ✅ DONE (7 specs L1-L7 + generator + CLI; self-verified runs) |
| E | Positioning + README + resume framing | `README.md`, `docs/POSITIONING.md` | ✅ DONE (README 176L, POSITIONING 128L) |

Lanes are disjoint by output path → no write collisions.
Base dirs pre-created so agents don't race on mkdir.

## Decisions / rationale

- **git init done** so the project is versionable and diffs are reviewable.
- Kept the docs' core design (Architecture C, 3B-4B Q4 driver, in-guest engineered
  boundaries only, no hypervisor escape) — this is settled, agents must not relitigate it.
- Model for agents: `sonnet` (per user request "sonnet 5").
- I (Opus) own: skeleton dirs, this scratchpad, CLAUDE.md, memory, final integration.

## Integration TODO (fix after all lanes land — don't touch agents' live files mid-run)

- [ ] **Naming decision** (surfaced by Agent E): public name "The Trust-Boundary Ladder"
      vs repo/codename "Constraint Cage". Default: keep "Constraint Cage" as repo/working
      name (matches dir + source docs), "Trust-Boundary Ladder" as positioning tagline.
      Confirm with user; then naming-consistency pass across all docs.
- [ ] **Lint:** `challenges/schema.py:41` — unused `field` import (Pyright). Trivial fix.
- [ ] **Lint:** `challenges/level1_unprivileged_user.py:19` — `from ..paramlib` unresolved
      (Pyright). Likely missing `__init__.py` / package layout. Fix in integration.
- [ ] **BIG ONE — import root.** Most Pyright errors (`eval.X`, `src.agent.X`,
      `..paramlib` unresolved) share one cause: no declared project root. Fix in
      integration: add `pyproject.toml`/`pyrightconfig.json` at repo root so absolute
      imports resolve, ensure `__init__.py` layout is consistent, then VERIFY at runtime
      (`python -m challenges.cli`, `python -m pytest eval/`) from repo root. Naming `eval/`
      as a package is legal (no stdlib `eval` module) but confirm it doesn't confuse tools.
- [ ] **Cross-lane coupling:** `challenges/schema.py` imports `eval.taxonomy` (D→C). OK
      conceptually (challenges tag their failure taxonomy) but both must import together;
      confirm no circular import and that eval.taxonomy exposes what schema.py expects.
- [ ] Verify doc cross-references resolve (README links to docs/*, CLAUDE.md repo map).
- [ ] Run any smoke test (Agent A) + eval unit tests (Agent C).
- [ ] Trivial unused-import lints: `models.py:20` (Literal), `challenges/schema.py:41`
      (field). Clean up in the import-root pass.
- [ ] Resume bullets are written for finished v0.5, not pre-alpha — flag to user (Agent E
      already caveated in POSITIONING §5).
- [ ] Grey-literature check before any public "empty niche" claim (Agent E + doc note).

### Cross-lane reconciliation from Agent B's research (E wrote before B finished!)
- [ ] **Framing fix (important):** leg (2) "small model chains privesc" is ~answered
      (PrivEsc-LLM 4B → 95.8%). The real, narrower differentiator = does it survive when
      *inference-time* compute is constrained, off-the-shelf, **no RL budget** — PLUS the
      failure-taxonomy + energy legs. README/POSITIONING must not let legs 1 & 2 blur, or
      "so what, PrivEsc-LLM got 95.8%" is the obvious rebuttal. Reconcile E's docs with B.
- [ ] **Naming collision:** ExploitBench (CMU) uses "capability ladder" naming → factor
      into the naming decision (another reason to prefer "Trust-Boundary Ladder" carefully
      or check overlap).
- [ ] **Propagate B's 4 PARTIAL corrections** wherever cited: (1) PrivEsc-LLM doesn't
      literally disclaim CPU/laptop, just never mentions it; (2) edge-thermal iPhone number
      is ~50% in 2 iters, not ~40% in 3; (3) "State Contamination" paper = toxicity through
      summary compression in ONE run, not cross-trial leakage; (4) COPE = flexible role
      alternation, not fixed cheap-exec/expensive-planner. Source docs v1/v2 have the old
      numbers — do NOT edit source docs, but new docs must use corrected figures.
- [ ] **7 new refs** B found (Perses/AsiaCCS, HackSynth, A-LEMS energy, ExploitBench,
      Veerman 21-model CPU-laptop bench, PrivEsc-LLM code repo, + "Scaffolded Capability
      Ceiling" CONFIRMED NON-EXISTENT via GitHub API). Already in docs/REFERENCES.md.
- [ ] Lean harder on TrustedSec 4,800-run finding (all self-hosted 24-87B models fail
      multi-step chaining) — strongest evidence FOR the research question's difficulty.

## Integration pass — DONE (2026-09-24)

All 5 fleet lanes landed. Runtime ground truth: **55/55 tests pass** (5 agent smoke +
50 eval), challenges CLI generates all 7 levels deterministically, cross-lane
`challenges→eval.taxonomy` import works. The ~60 Pyright errors were ALL missing-import-root,
not broken code. Fixes applied by me (Opus, integration):
- ✅ `pyrightconfig.json` + `pyproject.toml` → declare repo root as import base (clears the
  `src.*`/`eval.*`/`challenges.*`/`..paramlib` resolution errors); pytest `pythonpath=["."]`.
- ✅ Real bug: `src/telemetry/sources.py` RAPL delta narrowed only `_last_uj`, left `_last_ts`
  as `float|None` at the subtraction → guard now checks both.
- ✅ README quickstart naming reconciled to actual files: `validate_env.sh` (underscore),
  `config/example.yaml` (+ noted the no-arg smoke path).
- ✅ `.gitignore` added (venv, __pycache__, *.gguf, *.qcow2, runs/, .codegraph/, graphify-out/).
- ✅ POSITIONING.md reconciled with Agent B's primary-source corrections: softened the
  Qwen3-4B "limitations section disclaims CPU" overstatement → "never evaluates, doesn't
  raise it"; added the sharpened differentiator (95.8% needed 4×H100 RL → our open question
  is inference-time-constrained/no-RL/off-the-shelf); cleared the "Scaffolded Capability
  Ceiling" phantom (GitHub 404) and swapped in the real grey-lit findings (Perses, ExploitBench
  naming collision, Veerman bench); FAQ updated.
- ✅ Stale unused-import lints (models Literal, schema field) — agents already cleaned them.
- ⏳ Opus viz agent (three.js / cartoonic showcase) still running → writes viz/ only.

**STILL A USER DECISION:** public name "The Trust-Boundary Ladder" vs repo/codename
"Constraint Cage". Current state: README H1 & POSITIONING lead with Trust-Boundary Ladder;
CLAUDE.md, source docs, dir name = Constraint Cage. Sensible + intentional as a
name/codename split — but user should confirm before it's fully consistent-ized.

## Open questions to resolve later

- [ ] Measure memory channels (dmidecode) — collapses most [EST].
- [ ] Which exact 3-4B checkpoint (defer until llama-bench on this unit).
- [ ] Verify the "empty niche" claim against grey literature before any public claim.

## Log

- 2026-09-24: dir explored, git init, skeleton dirs, scratchpad created, prediction f0d7d3 logged (p=0.70). About to launch fleet.
- 2026-09-24: fleet of 5 sonnet agents launched (A=scaffold, B=research, C=eval, D=challenges, E=positioning). All background. Now writing CLAUDE.md + memory while they run.
- 2026-09-24: CLAUDE.md + 3 memory files written. User will create the repo & push themselves — removed the empty `.git` I had made; **do NOT stage/commit/push or add co-authorship.** Nothing was ever staged. Fleet agents only write files (no git).
- 2026-09-24: user created remote → https://github.com/Anbu-00001/Cage . I will PROVIDE commit commands (no co-authors) at the end; user runs them + pushes. I do not run git.
