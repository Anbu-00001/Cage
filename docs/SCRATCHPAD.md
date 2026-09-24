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

## De-risking research + phasing — DONE (2026-09-24)

Web research on the 6 riskiest unknowns → `docs/DE-RISKING.md`; phase plan → `docs/ROADMAP.md`.
Key outcomes (ana predictions resolved):
- `78f6ed` RAPL root-only by default → **TRUE** (needs udev rule; joules/solve mitigated).
- `a244fe` pin to P-cores (not all 12 threads) → **TRUE** (~3× on Intel hybrids).
- `ffe5dd` dual-channel → **STILL OPEN**: Inspiron 16 5640 has 2 SO-DIMM slots, NOT soldered;
  stock often 1×8 → a 16GB unit is either 1×16 (single) or 2×8 (dual). MUST run `dmidecode`.
- **Biggest de-risk:** JSON/tool-call reliability is solved by llama.cpp GBNF grammar (JSON
  Schema → grammar, invalid tokens masked) — delete parse-retry code.
- **Design refinement:** reset via qcow2 **overlay discard-and-recreate**, NOT libvirt
  external-snapshot revert (libvirt can't revert external snapshots).
- vsock = one libvirt XML stanza (host CID 2, guest CID>2); confinement mostly free via
  libvirt (built-in seccomp + AppArmor sVirt + cgroups).

**Code-writing is GATED on the viz agent returning** (per user). First code targets when it
lands (all authorable now, host only needed to run): real grammar-constrained LlamaServerClient,
real VsockChannel + guest daemon, overlay-reset vm/scripts, validate_env.sh --fix-rapl +
channel/P-core detection, challenge→provisioning applier. Phase order in ROADMAP.md.

## Code increment — Phase 1/2 foundations (2026-09-24, viz gate cleared)

Viz landed (viz/index.html, 63 KB, 2D canvas showcase, headless-Chrome verified). Then wrote
real code per ROADMAP (all authorable now; host only needed to *run*):

- **Grammar-constrained inference (DE-RISKING §3):** `CompletionClient.complete` +
  `LlamaServerClient` + `FakeLLMClient` now take `json_schema`; the real client emits
  `response_format:{type:json_schema,...}` so llama-server constrained-decodes → malformed
  tool calls impossible. Loop passes `AgentStepOutput.model_json_schema()` each step; retry
  loop kept only as a fallback. New test `tests/test_llm_grammar.py` (httpx MockTransport, 4 tests).
- **Hardened host↔guest channel (DE-RISKING §5):** fixed a real stream-socket bug —
  `VsockChannel` read a single `recv()` (truncates large guest output). Added newline-framed
  `send_json_line`/`recv_json_line`/`parse_action_response` with a 16 MB cap; rewrote execute.
- **Guest daemon (NEW):** `vm/guest/action_daemon.py` — self-contained stdlib listener
  (AF_VSOCK + AF_INET test mode), per-command timeout w/ process-group kill, 64 KB output
  truncation. New test `tests/test_channel_wire.py` runs the REAL daemon over loopback with
  the REAL framing (5 tests incl. the multi-recv regression + timeout).
- **Fast reset (DE-RISKING §6):** `vm/scripts/reset_overlay.sh` — qcow2 overlay discard over
  a checksummed immutable golden; **functionally verified with qemu-img** (overlay has golden
  as backing). `vm/scripts/build_golden_image.sh` — Alpine golden via alpine-make-vm-image +
  virt-copy-in (daemon + OpenRC service + cage user + vsock module), read-only + checksummed.
- **RAPL (DE-RISKING §2):** `scripts/setup_rapl_access.sh` (mutating, installs udev rule);
  `validate_env.sh` got a read-only "Derived hints" section (memory-module count, P-core ids,
  RAPL readability). validate_env.sh stays read-only; the write lives in the separate script.

**Verification:** 64/64 tests pass (was 55; +9). All shell `bash -n` clean; daemon compiles;
reset primitive live-tested. ana predictions resolved: 78f6ed RAPL TRUE, a244fe P-core TRUE,
bd5408 code-first-run TRUE. ffe5dd (channels) still OPEN → needs dmidecode on the unit.

**Known cosmetic:** IDE Pyright still flags `src.*`/`eval.*` import-root despite
pyrightconfig.json extraPaths — runtime is authoritative & green; likely needs a Pylance
reload. Not a runtime issue.

## Open questions to resolve later

- [ ] Measure memory channels (dmidecode) — collapses most [EST].
- [ ] Which exact 3-4B checkpoint (defer until llama-bench on this unit).
- [ ] Verify the "empty niche" claim against grey literature before any public claim.

## Log

- 2026-09-24: dir explored, git init, skeleton dirs, scratchpad created, prediction f0d7d3 logged (p=0.70). About to launch fleet.
- 2026-09-24: fleet of 5 sonnet agents launched (A=scaffold, B=research, C=eval, D=challenges, E=positioning). All background. Now writing CLAUDE.md + memory while they run.
- 2026-09-24: CLAUDE.md + 3 memory files written. User will create the repo & push themselves — removed the empty `.git` I had made; **do NOT stage/commit/push or add co-authorship.** Nothing was ever staged. Fleet agents only write files (no git).
- 2026-09-24: user created remote → https://github.com/Anbu-00001/Cage . I will PROVIDE commit commands (no co-authors) at the end; user runs them + pushes. I do not run git.
