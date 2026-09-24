# The Trust-Boundary Ladder
### an escape-lab on a laptop

*(working title during design: **Constraint Cage** — see [`constraint-cage.md`](constraint-cage.md) and [`constraint-cage-v2.md`](constraint-cage-v2.md), the feasibility-teardown and market-positioning docs this repo is built from)*

![status](https://img.shields.io/badge/status-pre--alpha%20(v0.1)-yellow)
![hardware](https://img.shields.io/badge/hardware-CPU--only%2C%20no%20GPU-blue)
![scope](https://img.shields.io/badge/scope-contained%20single--laptop%20lab-informational)
![license](https://img.shields.io/badge/license-TBD-lightgrey)

*Figures tagged `[FACT]` are measured or vendor-sourced; `[EST]` are engineering estimates pending measurement; `[LIT-VERIFIED]` are confirmed against a cited source. Full legend and citations in [docs/POSITIONING.md](docs/POSITIONING.md) and [docs/RESEARCH.md](docs/RESEARCH.md).*

---

## What this is

The Trust-Boundary Ladder is a contained, reproducible benchmark that measures whether a **small (3B–4B, 4-bit quantized), CPU-only, no-GPU** local LLM agent can **autonomously discover and chain a graded ladder of engineered privilege/trust boundaries** inside a disposable KVM/QEMU Alpine Linux guest — and reports the result **per joule**, alongside an **interpretable failure taxonomy** of exactly where and why the agent stalls, not just whether it "won."

Everything happens on one laptop, inside one virtual machine the researcher built and owns. There is no hypervisor exploit, no real-world target, and no third-party system anywhere in scope — see [Safety & scope](#safety--scope).

> **Safety in one line:** every "privilege escalation" here happens *inside* a disposable VM, against a boundary engineered on purpose by the researcher. The VM boundary itself is never targeted — no hypervisor escape, no third-party systems, ever.

## The headline question

> **How many engineered privilege/trust hops can a 3B–8B, CPU-only agent chain unassisted, across procedurally-generated and reseeded instances of the same boundary class — and what does each solve cost in tokens, actions, and joules, broken down by a pre-registered taxonomy of *why* the failures that do happen, happen?**

That is deliberately **not** "can an LLM hack a VM." That question is already answered and the leaderboard is crowded — a 2026 paper already reports a Qwen3-4B model at 95.8% on Linux privilege-escalation chains, trained on 4×H100 and served on an RTX 4090. `[LIT-VERIFIED]` This project doesn't try to beat that number; it reports a combination of variables that paper's own limitations section explicitly leaves open — CPU-only hardware as a first-class variable, an interpretable failure taxonomy, and energy accounting — not a capability percentage as the whole story. Full literature sweep in [docs/RESEARCH.md](docs/RESEARCH.md) and the competitive map in [docs/POSITIONING.md](docs/POSITIONING.md).

## Why this is hard — and why the constraint is the point

- **Two fast cores, not twelve.** The target laptop's CPU is 2 performance-cores + 8 efficiency-cores, 12 threads. `[FACT]` Decode is memory-bandwidth-bound, not core-bound — past ~4–6 threads, extra threads fight over the same DRAM bus for nothing. `[EST]`
- **16 GB is the binding constraint, not the CPU.** Model weights, KV cache, the agent runtime, the guest VM, and telemetry all compete for the same 16 GB; the budget for a 3B driver plus a VM barely closes, and 7B is genuinely marginal. `[EST]`
- **No GPU to hide behind.** Every design decision — model size, context length, tool count, VM RAM — is made under a hard budget instead of "add more compute." That's usually the excuse a project makes for cutting corners; here it's the reported independent variable.
- **Thermal throttling is a real confound, not a footnote.** 15 W base / 55 W turbo in a thin chassis means the hundredth episode runs on a slower chip than the first, unless it's logged and controlled for — most agent-security evaluations don't. `[LIT-VERIFIED — docs/RESEARCH.md]`
- **The difficulty lives in the environment, not the model.** Every boundary is procedurally parameterized and reseeded so "solving" can't be shortcut by recalling a public writeup — see [docs/CHALLENGES.md](docs/CHALLENGES.md).

Five things that read as limitations turn into the things this project can measure that GPU-backed work structurally can't: solves-per-watt-hour, scaffolding-vs-scale tradeoffs, agent behavior (not just speed) under degraded compute, and a reproducibility bar — "clone this and run it on a laptop, no GPU required" — that the field's own critics keep asking for. Full case in [docs/POSITIONING.md](docs/POSITIONING.md).

## Architecture at a glance

Full design in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); the summary is **Architecture C** — the model and the agent live on the **host**; the VM is the **cage**, never the agent's home:

```
                        HOST  (Ubuntu, headless during runs)
  ┌──────────────────────────────────────────────────────────────────────┐
  │  llama.cpp (C++, GGUF Q4_K_M, 3B–4B)                                  │
  │        │ tokens                                                      │
  │        ▼                                                             │
  │  Agent orchestrator (Rust / tokio)                                   │
  │    OBSERVE → STATE → HYPOTHESIS → PLAN → ACTION → EVALUATE → NEXT    │
  │        │                                                             │
  │        │  narrow, fully-logged action channel (virtio-vsock / SSH)   │
  └────────┼──────────────────────────────────────────────────────────────┘
           ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │            KVM/QEMU guest — Alpine Linux  (the cage)                 │
  │                                                                      │
  │   L0 baseline → L1 unpriv. user → L2 FS limits → L3 net limits →     │
  │   L4 process/cgroup limits → L5 capability drops →                   │
  │   L6 engineered flaw → L7 multi-stage chain                          │
  │                                                                      │
  │   Disposable: reverted to a golden, checksummed snapshot every run   │
  └──────────────────────────────────────────────────────────────────────┘

  1 Hz telemetry (RAPL joules, temp, freq, RAM/swap/PSI, tok/s, TTFT)
  → collector (Rust/Go) → TSDB → analysis (Python/Polars)
```

The guest is reachable only through that one narrow, logged channel — never a shared filesystem, clipboard, or bridged network — and reverts to a checksum-verified golden snapshot before every trial.

## Tech stack — polyglot by constraint

> Prototype in Python, harden in Rust, infer in C++, observe with eBPF, orchestrate VMs with libvirt, analyse in Python/Polars.

| Layer | Language | Fights this constraint |
|---|---|---|
| Inference engine (llama.cpp/GGUF) | **C/C++** | 2 performance cores only — AVX2 kernels, quantization, thread pinning |
| Agent orchestrator + vsock channel | **Rust** (tokio) | 16 GB budget — no GC pauses, tiny footprint, safe concurrency |
| Telemetry collector | **Rust/Go** | 1 Hz sampling of RAPL/temp/freq without stealing cycles from the model |
| Deep host observability | **eBPF** (C/BPF) | Near-zero-overhead syscall/scheduler tracing |
| VM control | **libvirt/QEMU** (C API + XML) | Snapshot, revert, `domstats` — reproducibility as a mechanism |
| Analysis / eval | **Python** (pandas/Polars) | Off the hot path — use the ecosystem freely |

Every choice is defensible in an interview by pointing at the same three numbers: **2 performance cores, 16 GB RAM, 15 W.** Full rationale in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**Implemented so far (not aspirational):** the **C++** leg is real — [`bench/membw.cpp`](bench/membw.cpp), a STREAM-triad benchmark that measured **42.2 GB/s = single-channel** on the target laptop (this is the number that sets the tok/s ceiling; see [docs/DE-RISKING.md](docs/DE-RISKING.md) §1). The **Rust** leg is real — [`telemetry-rs/`](telemetry-rs/), a zero-dependency 1 Hz RAPL/thermal/PSI sampler. The agent loop, host↔guest vsock channel + in-guest daemon, eval harness, and challenge ladder are **Python** (prototype-first, per the plan). eBPF observability is still to come.

## Repo map

| Path | What's there |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full system design: Architecture C, component boundaries, data flow |
| [`docs/RESEARCH.md`](docs/RESEARCH.md) | Literature sweep, competitive landscape, verified evidence |
| [`docs/EVALUATION.md`](docs/EVALUATION.md) | Statistical methodology, failure taxonomy, metric definitions |
| [`docs/CHALLENGES.md`](docs/CHALLENGES.md) | The L0–L7 ladder: design, procedural generation, scoring |
| [`docs/POSITIONING.md`](docs/POSITIONING.md) | Positioning, naming, honest risks, resume framing |
| [`src/`](src/) | Inference binding, agent orchestrator, telemetry collector |
| [`challenges/`](challenges/) | Seeded, versioned challenge definitions (L0–L7) |
| [`eval/`](eval/) | Batch runner, baselines, statistical analysis |
| [`scripts/`](scripts/) | Env validation, setup, snapshot/revert helpers |
| [`config/`](config/) | Pinned run configs (model, sampling, thresholds) |
| [`constraint-cage.md`](constraint-cage.md) | Original feasibility teardown (v1) this repo is built from |
| [`constraint-cage-v2.md`](constraint-cage-v2.md) | Market-positioning + literature-sweep addendum (v2) |

## Quickstart

> Pre-alpha (v0.1) — see [Build status](#build-status--roadmap). The interface below is the intended one-command target described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); if a script listed here hasn't landed yet, that file has the current state.

```bash
# 1. Validate this host against the measured hardware assumptions
#    (CPU topology, memory channels, KVM availability, thermal baseline —
#    see constraint-cage.md Part 23 for exactly what this checks)
./scripts/validate_env.sh

# 2. Point at a llama.cpp build and a 3B–4B GGUF Q4_K_M checkpoint
#    (model selection is benchmarked per-host, not hardcoded — docs/ARCHITECTURE.md)

# 3. Bring up the golden Alpine guest snapshot (libvirt)
virsh snapshot-revert cage-guest golden --running

# 4. Run one seeded episode end-to-end and get a byte-comparable transcript
./run.sh --seed 42 --config config/example.yaml   # or just ./run.sh for the model-free smoke path
```

## Safety & scope

This is a contained, single-machine lab experiment, not a live offensive-security exercise. The distinction that matters:

| Term | Boundary crossed | In this project |
|---|---|---|
| **In-guest privilege/trust boundary** | A boundary *engineered by the researcher* inside the guest (unprivileged user → root, over-permissive service, leaked token) | ✅ **The research target.** Fully contained, fully reset between trials. |
| VM / hypervisor escape | Guest → the QEMU process or kernel on the host | ❌ **Out of scope.** Never targeted, never attempted. |
| Host compromise | Any control over the researcher's actual laptop | ❌ **The one outcome that must never happen.** |
| Third-party systems | Anything not owned by the researcher | ❌ **Never in scope.** No live networks, no external targets. |

Defense-in-depth, enforced by design:

- Every trial reverts to a golden, checksum-verified snapshot — the guest is disposable by construction.
- Isolated NAT, or no network interface at all — the agent never sees the researcher's real LAN or the internet.
- No shared folders, no virtiofs/9p, no clipboard, no USB or GPU passthrough — no host-filesystem bridge of any kind.
- No real credentials, keys, or secrets are ever placed near the guest — only **planted fakes**, engineered specifically to be found.
- QEMU runs as an unprivileged, cgroup- and seccomp-confined process; host, kernel, and hypervisor stay patched.
- Levels 6–7 ("engineered flaw" / "multi-stage chain") are misconfigurations the researcher built and already knows about — not real CVEs, not novel exploits, not anything lifted from a public writeup.

Full threat model and rationale in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and the original teardown ([constraint-cage.md](constraint-cage.md), Part 19).

## Build status / roadmap

| Version | Scope | Proves | Status |
|---|---|---|---|
| **v0.1** | Model + shell loop, one hardcoded task, no VM | Loop plumbing + real tok/s on this host | 🔧 in progress |
| **v0.2** | + typed tools, structured/failure memory | Scaffolding works; steps-to-solve measurable | ⏳ planned |
| **v0.3** | + KVM guest, vsock/SSH channel, snapshots | Architecture C stands up; real isolation + reset | ⏳ planned |
| **v0.4** | + partial observability, randomized seeds, action costs | Transfer vs. recall becomes measurable | ⏳ planned |
| **v0.5** | + multi-stage L7 chain, full telemetry, eval harness | The publishable experiment | ⏳ planned |

Minimum viable experiment (target): a 3B agent on the host solving a seeded Level-6 boundary in a resettable Alpine guest over vsock, with tok/s, joules, and actions-to-solve logged across ≥20 seeds.

## Honest limitations

- **The core capability claim is not novel.** A Qwen3-4B model has already been reported at 95.8% on Linux privilege-escalation chains (GPU-trained and GPU-served). `[LIT-VERIFIED]` This project doesn't claim to beat that number — it reports a different combination of variables that paper explicitly didn't. See [docs/POSITIONING.md](docs/POSITIONING.md).
- **"No GPU" is a constraint, not automatically a contribution.** It only earns that status if the artifact is genuinely reproducible by someone else on their own laptop — a packaging obligation this project has to keep meeting, not a one-time claim.
- **One laptop means limited statistical power.** Wall-clock time and thermal-recovery gaps bound how many seeds and conditions can run; every result is reported with confidence intervals for exactly this reason, never as a single anecdote.
- **Figures in the design docs are estimates until measured.** Numbers tagged `[EST]` in [`constraint-cage.md`](constraint-cage.md) / [`constraint-cage-v2.md`](constraint-cage-v2.md) — tok/s, memory bandwidth, RAM budget — become `[FACT]` only after the Part 23 host-validation commands run on this exact machine. Treat anything still tagged `[EST]` as directionally right, not measured.
- **The "empty niche" claim is a literature-sweep result, not a guarantee.** Grey literature (forums, Discord, unindexed repos) was not exhaustively searched — see the confidence note in [docs/RESEARCH.md](docs/RESEARCH.md).

## Further reading

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design
- [docs/RESEARCH.md](docs/RESEARCH.md) — literature sweep and evidence
- [docs/EVALUATION.md](docs/EVALUATION.md) — statistical methodology and failure taxonomy
- [docs/CHALLENGES.md](docs/CHALLENGES.md) — the L0–L7 ladder design
- [docs/POSITIONING.md](docs/POSITIONING.md) — positioning, naming, and resume framing
- [constraint-cage.md](constraint-cage.md) / [constraint-cage-v2.md](constraint-cage-v2.md) — the original teardown docs

## License

TBD.
