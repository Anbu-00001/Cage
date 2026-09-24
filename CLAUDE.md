# CLAUDE.md — repo guide for the Constraint Cage

Guidance for any AI agent (or human) working in this repository. Read this before
editing. It captures what the project **is**, what is **settled**, and the guardrails.

## What this project is

**The Constraint Cage** (positioning name: *The Trust-Boundary Ladder — an escape-lab
on a laptop*) is **contained, authorized, educational/defensive security research** run
entirely on the owner's own laptop. The research question:

> How many engineered privilege/trust boundaries can a small (3B–8B, Q4-quantized),
> **CPU-only, no-GPU**, laptop-hosted LLM agent discover and *chain* unassisted — measured
> **per joule**, with an **interpretable failure taxonomy** of exactly where and why it stalls?

It began as two design/teardown documents ([constraint-cage.md](constraint-cage.md) = v1
feasibility teardown; [constraint-cage-v2.md](constraint-cage-v2.md) = v2 market
positioning). Everything else in this repo builds those into a real project.

## Safety scope — non-negotiable

This is the entire safety story; do not blur it in any file, commit, or write-up:

- **In-guest boundaries only.** Every "boundary" the agent crosses is a privilege/trust
  boundary the researcher **engineered inside their own disposable Alpine KVM guest**
  (e.g. user→service, service→root via a deliberately weak setuid helper). "Escape" means
  crossing that **in-guest** boundary — **never** the VM/hypervisor boundary.
- **The host is sacred.** No hypervisor/VM escape is targeted or developed. Host stays
  patched; QEMU runs unprivileged, cgroup/seccomp-confined.
- **No third-party systems, no live networks.** Isolated NAT or no NIC. The agent never
  sees the real LAN or internet.
- **Planted fakes only.** No real credentials, keys, or secrets near the guest.
- **Lab fixtures, not attack playbooks.** Challenges are teaching misconfigurations with
  no public writeup, generated fresh per seed. We do not weaponize real CVEs or ship
  working exploits against anything external.

If a change would weaken any of the above, stop and flag it.

## Settled design — do NOT relitigate

These were decided in the teardown and are load-bearing. Improve *within* them:

- **Architecture C:** llama.cpp model + thin orchestrator on the **host**; the KVM/QEMU
  Alpine guest is the isolated, snapshot-able **cage**; the agent touches it only through
  a **narrow, logged vsock/SSH channel**. (Not model-in-VM; not big-planner-both-local.)
- **Driver model:** 3B–4B instruct, **Q4_K_M**, strong tool-calling = default. 7B = hard-mode
  comparator. Frontier API only as an optional *planner-arbitrage* tier (Arch D).
- **Hardware truth:** Intel Core 7 150U = **2 P-cores + 8 E-cores**, 16 GB RAM, AVX2/no
  AVX-512, 15 W. **Two fast cores, not twelve.** Decode is memory-bandwidth-bound.
- **Guest:** 2 vCPU (E-cores) · 1.5–3 GB · 8–20 GB qcow2 CoW · UEFI · isolated NAT · vsock
  · external snapshots. Off: shared folders, clipboard, USB/GPU passthrough, LAN bridge.
- **Agent loop:** one model, one loop (OBSERVE→STATE→HYPOTHESIS→PLAN→ACTION→OBSERVATION→
  EVALUATE→UPDATE→NEXT). Executor + structured/failure memory + summarizer + goal tracker.
  **Periodic** (not per-step) re-plan. **Few typed tools. No sub-agents** (multi-inference
  is unaffordable here).
- **Positioning:** lead with the verified-open triple intersection (CPU-only laptop no-GPU
  ≤8B as a reported variable × autonomous discovery+chaining of engineered boundaries ×
  efficiency + failure taxonomy). **Avoid**: any "first" claim on LLM-privesc; bare
  "sandbox escape" naming; hype ("AI escaped"/"0-day"/"self-aware"); "red-teaming" as the
  headline; pitching raw capability % as the whole story.

## Claim discipline (the Legend)

Every quantitative claim carries a tag; keep this convention everywhere:
`[FACT]` measured/spec-sheet · `[EST]` engineering estimate, verify by measurement ·
`[ASSUME]` stated assumption · `[REC]` recommendation · `[OPEN]` resolve by measuring a
named parameter · `[LIT-VERIFIED]`/`[LIT-INFERRED]` from the literature ·
`[VERIFIED-YYYY-MM]` personally confirmed via web this session.

**The three measurements that collapse most `[EST]` → `[FACT]`** (still `[OPEN]`):
1. Memory **channels** (`sudo dmidecode -t memory`) — single vs dual **halves/doubles every
   tok/s number**. This is the single most important unknown.
2. Measured **tok/s** for 3B & 7B Q4 at 4k ctx *with the VM running* (`llama-bench`).
3. **Sustained** P-core clock + PkgWatt after ~10 min load (`turbostat`).

## Repo map

```
constraint-cage.md      v1 — feasibility teardown (source, do not rewrite)
constraint-cage-v2.md   v2 — market positioning (source, do not rewrite)
README.md               front door
CLAUDE.md               this file
run.sh                  one-command episode reproducer
docs/
  SCRATCHPAD.md         living working notes for the build-up
  ARCHITECTURE.md       component/data-flow/RAM-budget/boundary
  RESEARCH.md           consolidated, verified research brief
  REFERENCES.md         checked bibliography w/ verification status
  EVALUATION.md         implementable eval methodology + statistics
  CHALLENGES.md         the graded cage (Levels 1-7) + procedural design
  POSITIONING.md        positioning, naming, honest risks, resume framing
src/agent/              the agent loop, typed tools, memory, state machine
src/orchestrator/       host-side episode driver + llama-server + guest channel
src/telemetry/          1 Hz RAPL/temp/freq/PSI/tok-s collector
eval/                   batch runner, statistics (Wilson/bootstrap CI, ICC), taxonomy
challenges/             challenge specs + seeded procedural generator
vm/scripts/             guest build / snapshot / revert
scripts/                env-validation, llama.cpp build helpers
config/                 versioned run configs (pin everything for reproducibility)
```

## Conventions

- **Reproducibility is the currency.** Pin the inference stack (llama.cpp commit, quant,
  ctx, threads, sampling, seed), store the *seed* not the instance, hash the GGUF and the
  golden qcow2. One command → byte-comparable transcript.
- **No hero runs.** Report distributions over ≥N seeds with CIs; transfer across seeds is
  the definitive luck-vs-strategy test. See [docs/EVALUATION.md](docs/EVALUATION.md).
- **Laptop-honest.** 16 GB and 2 fast cores. Prefer Alpine/musl, headless (TTY) during
  runs, cgroup caps, zram. Never sacrifice telemetry integrity or snapshot safety.
- Tooling available on this device: **CodeGraph** (per-project index — run `codegraph init`
  once if `.codegraph/` is absent), **Serena** (live LSP), **graphify**. Keep `.codegraph/`
  and `graphify-out/` in `.git/info/exclude`, not `.gitignore`.
- Calibration: this device has `ana` (Anamnesis). Log falsifiable predictions before
  non-trivial calls; resolve them when reality answers.

## Current status

Bootstrapping from the two design docs into a working repo. See
[docs/SCRATCHPAD.md](docs/SCRATCHPAD.md) for live status and the v0.1→0.5 roadmap in the
README. Nothing has been benchmarked on the real unit yet — the three `[OPEN]`
measurements above are the first real-work milestone.
