# Roadmap — phased build plan

Turns the design docs' v0.1→0.5 ladder (constraint-cage.md Part 15) and 8-phase plan
(Part 22 / v2 D1) into a concrete, executable sequence tied to the **current repo state** and
gated by [docs/DE-RISKING.md](DE-RISKING.md). Each phase has: goal · key tasks · which
existing files it makes real · stop condition · risk gate.

**Status key:** ✅ done · 🔨 in progress · ⬜ not started

---

## Phase 0 — Skeleton & scaffolding ✅ DONE

Repo structure, agent loop, eval harness, challenge specs, all docs, CLAUDE.md, memory.
**55/55 tests pass**; challenge generator produces all 7 levels deterministically; cross-lane
imports resolve; import-root + `.gitignore` + `pyproject.toml` in place.
*Deliverable met: a repo a reviewer can open, read, and run the smoke/eval tests in.*

---

## Phase 1 — Host reality & real inference 🔨  (gate: memory channels — RESOLVED)

**Update 2026-09-24:** the memory-channel gate is measured — `bench/membw` reports **42.2 GB/s
= single-channel** (docs/DE-RISKING.md §1). Model-size decision locked to 1B–4B (7B ≈ 9 tok/s is
too slow). Grammar-constrained `LlamaServerClient` is done. Remaining: build llama.cpp +
`llama-bench` sweep on the real host, and the `--fix-rapl` / P-core-pin steps.


**Goal:** collapse the big `[EST]`→`[FACT]` unknowns and get one *real* (non-mock) agent step.

- Run `scripts/validate_env.sh`; **`sudo dmidecode -t memory` FIRST** → resolves single vs dual
  channel (DE-RISKING §1) and the model-size decision.
- `scripts/build_llama_cpp.sh` (CPU/AVX2, no CUDA); `llama-bench` 3B & 7B Q4 at 4k ctx
  **with the VM idle then running**; sweep `--threads 2/4/all` pinned to P-cores via `taskset`
  (DE-RISKING §4) → pick the winner, save the figure.
- Install RAPL udev rule via `validate_env.sh --fix-rapl` (DE-RISKING §2); confirm `energy_uj`
  readable as the run user.
- Make `src/orchestrator/llm_client.py` real: talk to `llama-server`, pass each typed tool's
  **JSON-Schema-derived GBNF grammar** so tool calls can't be malformed (DE-RISKING §3);
  delete speculative parse-retry paths.

**Makes real:** `scripts/*`, `src/orchestrator/llm_client.py`, `config/example.yaml` (pin the
measured stack). **Stop:** real tok/s + joules recorded; a single agent step runs against a
real model with grammar-constrained output. **Risk gate:** if single-channel, lock to 1B–3B.

## Phase 2 — The cage (VM + channel + reset + confinement) 🔨  (scripted hand-off ready)

**Update 2026-09-24:** the full Phase-2 hand-off is written and validated (bash -n clean,
domain XML well-formed) — it just needs the user to run it as root (running QEMU/libvirt on the
daily driver is their call, per the safety scope). Pieces: `vm/domain.xml.template` (2 E-core
vCPUs, UEFI, overlay disk, vsock-only, no NIC), `vm/scripts/build_golden_image.sh` (Alpine
golden + daemon + OpenRC), `reset_overlay.sh` (overlay-discard reset, functionally verified),
`define_domain.sh`, `verify_isolation.sh` (Part-7 hardening audit), and the ordered runbook
[docs/GUEST-SETUP.md](GUEST-SETUP.md). Remaining: the user runs it + the runtime isolation checks.


**Goal:** a pristine, resettable, isolated Alpine target the agent reaches only over vsock.

- Build `golden.qcow2` (Alpine, `virt` kernel with `AF_VSOCK`); checksum it.
- **Reset = overlay discard-and-recreate** (DE-RISKING §6), not libvirt external-snapshot
  revert: `qemu-img create -f qcow2 -b golden.qcow2 -F qcow2 trial.qcow2`; delete+recreate per
  trial. Target < 2 s.
- Guest action daemon: accept one vsock connection, length-prefixed typed request → run →
  return result+exit+timing. Host `VsockChannel` (real impl of the stub).
- Confinement: qemu:///session or low-priv user, **AppArmor sVirt enforcing**, cgroup mem/cpu
  caps, isolated NAT or no NIC (DE-RISKING §6).

**Makes real:** `vm/scripts/*`, `src/orchestrator/channel.py` (`VsockChannel`). **Stop:**
byte-identical reset < 2 s (checksummed); guest cannot reach host (verified); agent runs a
command in-guest over vsock. **Risk gate:** isolation audit must pass before any Level-6 flaw
is installed.

## Phase 3 — Challenges live in the guest 🔨  (rendering + scoring done)

**Update 2026-09-24:** `challenges/provision.py` renders the root build-time provisioning
script from a resolved instance and scores trials in-guest over the channel by exit status
(`run_success_check` / `run_scripted_solver`), +28 tests. Remaining (needs a live guest from
Phase 2): actually apply provisioning to the overlay as root and confirm human + scripted
solver both solve L1–L6 with the probe variant.


**Goal:** the procedural challenge specs actually provision inside the guest and are solvable.

- Wire `challenges/` generator output (provisioning shell fragments) into the guest build:
  apply resolved fragments to the overlay at boot (cloud-init-style or an init script).
- Scripted "optimal" solver per level (for scoring bounds + calibration); confirm human +
  scripted solver both solve L1–L6; **held-out probe variant** works (transfer vs recall).

**Makes real:** challenge→guest provisioning applier, `eval/` scored-solver hooks. **Stop:**
calibrated difficulty curve; probe variants pass. **Risk gate:** every fixture stays in-guest
(re-assert scope from CLAUDE.md).

## Phase 4 — Telemetry & episode integration ⬜

**Goal:** every episode fully reconstructable with resource + energy + trace.

- Run `src/telemetry/collector.py` at 1 Hz during episodes (RAPL joules, temps, freq, PSI,
  tok/s); tag each episode with thermal/memory state; **flag throttled trials**.
- `src/orchestrator/episode.py`: replace `make_smoke_goal()`/no-op reset with real challenge
  goals + real overlay reset; emit an `EpisodeRecord` (eval schema) per run.

**Makes real:** `src/telemetry/*` (live), `episode.py` (real seams filled). **Stop:** one
`run.sh --seed N` produces a complete, reconstructable episode record. **Risk gate:**
telemetry overhead must not steal decode cycles (measure).

## Phase 5 — Eval rigor at scale 🔨  (spine connected end-to-end)

**Update 2026-09-24:** `eval/bridge.py` connects the real agent loop + real challenge
generator + real `BatchRunner` + real stats/report into one pipeline. Demonstrated: 44 episodes
(L2×12 + L6×32) → EpisodeRecords → distribution table with Wilson 95% CIs and per-cell top
taxonomy code (+4 tests). Outcomes are fixture-driven for now (plumbing proof); real numbers
arrive when the episode builder is swapped to LlamaServerClient + VsockChannel on the host.


**Goal:** distributions, not hero runs.

- `eval/runner.py` batch across **N≥30 seeds × conditions** (baseline random / scripted
  optimal / minimal-scaffold control / full treatment); one variable at a time.
- Compute success ± Wilson CI, ICC within/across-boundary, failure-taxonomy distribution,
  transfer rate; contamination + thermal gates applied.

**Makes real:** `eval/*` end-to-end on real episodes. **Stop:** stable metrics with CIs on at
least L1–L3. **Risk gate:** honest statistical power given one laptop (report it).

## Phase 6 — MVE → headline artifact ⬜

**Goal:** the publishable result + released dataset.

- **MVE (v0.3):** 3B agent solving a seeded L6 across ≥20 seeds; tok/s + joules +
  actions-to-solve logged.
- Then the full ladder + **released annotated traces + per-attempt telemetry dataset +
  one-command reproducer** (`run.sh --seed 42 --config …` → byte-comparable transcript).

**Makes real:** the whole thing. **Stop:** a third party reproduces a result from a seed on a
**no-GPU** box.

---

## Dependency order & what's writable now

```
P0 ✅ ──▶ P1 (host/inference) ──▶ P2 (cage) ──▶ P3 (challenges) ──▶ P4 (telemetry) ──▶ P5 (eval) ──▶ P6 (MVE)
                    │                  │
       gate: dmidecode channels   gate: isolation audit
```

**Hardware-independent code we can write now** (needs the host only to *run*, not to *author*):
the real grammar-constrained `LlamaServerClient`, the real `VsockChannel` + guest daemon, the
overlay-reset scripts, `validate_env.sh --fix-rapl` + channel/P-core detection, and the
challenge→provisioning applier. Those are the first code targets once the viz showcase lands.
