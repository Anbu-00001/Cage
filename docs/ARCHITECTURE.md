# Architecture

System design for **The Constraint Cage** (positioning name: *The Trust-Boundary
Ladder*). This document describes what is actually implemented in `src/`,
`config/`, and `scripts/` today, and marks every not-yet-wired seam with an
explicit **TODO** rather than describing aspirational code as if it exists.

## Legend

Same convention as the two source teardowns — keep it everywhere:

| Tag | Meaning |
|---|---|
| **[FACT]** | Measured, or taken from a vendor spec sheet. |
| **[EST]** | Engineering estimate — verify by measurement. |
| **[OPEN]** | Open question — resolve by measuring a named parameter. |
| **[REC]** | A settled recommendation from the design docs (do not relitigate — see `CLAUDE.md`). |

---

## 1. The one decision everything else follows: Architecture C

The design docs evaluate five ways to arrange {model, agent, VM} on one 16 GB,
2-fast-core laptop (`constraint-cage.md` Part 3) and settle on **Architecture
C**: the model and the orchestrator both run **on the host**; the VM is a
**restricted, disposable target**, reached only through a narrow, logged
channel — never the agent's home.

```
                    HOST  (Ubuntu 24.04, headless during runs)
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│   llama-server (llama.cpp, C++, GGUF Q4_K_M, 3B–4B)                   │
│        ▲ HTTP (httpx)             src/orchestrator/llm_client.py     │
│        │ POST /v1/chat/completions                                   │
│        │                                                             │
│   ┌────┴──────────────────────────────────────────────────────┐     │
│   │  src/orchestrator/episode.py  — Episode                    │     │
│   │    builds: CompletionClient, ActionChannel, ToolRegistry    │     │
│   │    runs:   AgentLoop.run()  →  persists EpisodeResult JSON  │     │
│   └────┬──────────────────────────────────────────────────────┘     │
│        │ constructs & drives                                        │
│        ▼                                                             │
│   ┌───────────────────────────────────────────────────────────┐     │
│   │  src/agent/loop.py  — AgentLoop  (pure; no orchestrator     │     │
│   │  or transport imports — see §3)                             │     │
│   │                                                             │     │
│   │   OBSERVE → STATE → HYPOTHESIS → PLAN → ACTION →            │     │
│   │   OBSERVATION → EVALUATE → UPDATE BELIEF → NEXT             │     │
│   │                                                             │     │
│   │   src/agent/memory.py      StructuredMemory + failure dedup │     │
│   │   src/agent/summarizer.py  HeuristicSummarizer (default)    │     │
│   │   src/agent/tools.py       ToolRegistry (5 typed tools)     │     │
│   │   src/agent/models.py      pydantic schema for every hop    │     │
│   └────┬──────────────────────────────────────────────────────┘     │
│        │ ToolCall → ActionChannel.execute(command) → ToolResult      │
│        │            src/orchestrator/channel.py                     │
│        │                                                             │
│   ┌────┴──────────────────────────────────────────────────────┐     │
│   │  src/telemetry/collector.py — 1 Hz sampler (runs alongside, │     │
│   │  not on the agent's critical path)                          │     │
│   │    RAPL joules · sensors temps · turbostat freq · PSI ·     │     │
│   │    RAM/swap · tok/s  →  NDJSON / SQLite (src/telemetry/sink.py) │  │
│   └───────────────────────────────────────────────────────────┘     │
│                                                                       │
└───────────────────────────┼───────────────────────────────────────────┘
                             │  narrow, logged action channel
                             │  SSH (stub) or virtio-vsock (stub)
                             ▼
┌───────────────────────────────────────────────────────────────────────┐
│              KVM/QEMU guest — Alpine Linux  (the cage)                │
│                                                                       │
│   Levels 0–7: unprivileged user → FS locks → net limits →            │
│   process/cgroup limits → capability drops → engineered flaw →       │
│   multi-stage chain          (owned by challenges/**, not this lane) │
│                                                                       │
│   Reachable ONLY via the channel above. No shared folders, no        │
│   clipboard, no USB/GPU passthrough, no LAN bridge.                  │
└───────────────────────────────────────────────────────────────────────┘
```

Everything above the horizontal line is implemented in this lane
(`src/agent`, `src/orchestrator`, `src/telemetry`) and is real, typed,
importable Python, unit-tested against fakes (`tests/test_smoke.py`).
Everything below the line — the actual guest image, the Level 0–7 challenge
content, the libvirt snapshot/revert plumbing — is owned by the VM/challenge
lane (`challenges/**`, `vm/**`); see §6 for the exact seam.

---

## 2. Data flow — one step of the loop

```
 1. Episode.run()
      └─ AgentLoop.run()  [src/agent/loop.py]
 2.   for step in range(step_budget):                       # HARD cap, Part 7
 3.     _maybe_replan(step)          # only every replan_interval steps, Part 7
 4.     _maybe_summarize()           # only if render() exceeds char_budget, Part 2
 5.     prompt = render_step_prompt(goal, StructuredMemory.render(), tools.describe(),
                                     last_observation)
 6.     raw = CompletionClient.complete(prompt, temperature, seed, max_tokens)
 7.     step_output = parse_step_output(raw)  # -> AgentStepOutput (pydantic)
 8.     if StructuredMemory.has_tried(step_output.hypothesis, step_output.action):
            BLOCK — do not call the channel; this is the failure-memory guard
 9.     else:
            result = ToolRegistry.dispatch(step_output.action)
              -> validates args against the tool's own schema
              -> Tool.run() -> ActionChannel.execute(command) -> ToolResult
10.     evaluation = CONFIRMED | DENIED | INCONCLUSIVE   # cheap heuristic, no extra inference
11.     UPDATE BELIEF: add_fact(...) or add_failure(...) into StructuredMemory
12.     if step_output.action.tool == "submit_flag" and result.ok:
            score against Goal.success_predicate -> GOAL_REACHED or another failure
13.   NEXT (loop) until GOAL_REACHED | STEP_BUDGET_EXHAUSTED | GAVE_UP | ERROR
14. Episode persists EpisodeResult (full StepRecord transcript) to
      {transcript_dir}/{name}-seed{seed}.json
```

Two inference-cost decisions are structural, not just prompt instructions,
because a small model reliably ignores instructions under pressure:

- **Periodic, not per-step, re-planning.** `_maybe_replan` only fires every
  `loop.replan_interval` steps (default 5) and produces a short
  `strategy_note` folded into the next steps' prompts — an extra full
  inference call every single step would roughly double per-step cost on a
  2-P-core host (`constraint-cage.md` Part 1/7/13). **[REC]**
- **Failure-memory blocking happens in code, before dispatch**, not as a
  prompt instruction the model can ignore. `StructuredMemory.has_tried()` is
  checked against every proposed `(hypothesis, action)` pair; an exact repeat
  never reaches `ActionChannel.execute` a second time. This is the concrete
  implementation of Part 7's "stops the loop retrying the same dead end — the
  #1 small-model failure."

Context management is a **heuristic, zero-inference-cost fold** by default
(`HeuristicSummarizer`, `src/agent/summarizer.py`): once `StructuredMemory`'s
rendered size exceeds `loop.char_budget`, the oldest facts/failures are
collapsed into `state.summary` and only the most recent N are kept verbatim.
An `LLMSummarizer` variant exists behind the same `Summarizer` protocol for
the scaffolding-vs-scale ablation (`constraint-cage.md` Part 16) but is not
the default, because spending a whole inference call to compress text is a
bad trade on a 2-P-core budget when a deterministic heuristic does the job
for free — and keeps a run reproducible (Part 18) as a side effect.

---

## 3. Component boundary: `src/agent` never imports `src/orchestrator`

This is the one layering rule that keeps the agent loop unit-testable
without a model or a VM:

- `src/agent/interfaces.py` defines two `typing.Protocol`s — `CompletionClient`
  (one method: `complete(prompt) -> str`) and `ActionChannel` (one method:
  `execute(command) -> ToolResult`).
- `src/agent/loop.py`, `tools.py`, `memory.py`, `summarizer.py` depend only on
  those protocols and on `src/agent/models.py` (plain pydantic data, no I/O).
- `src/orchestrator/llm_client.py` and `src/orchestrator/channel.py` provide
  the concrete implementations — real ones (`LlamaServerClient` over HTTP via
  `httpx`; `SSHChannel`/`VsockChannel`) and fake ones (`FakeLLMClient`;
  `LocalMockChannel`) — that satisfy those protocols structurally (duck
  typing; no inheritance, no import of `src.agent` from `src.orchestrator`'s
  concrete classes themselves).
- `src/orchestrator/episode.py` is the only place that wires a concrete
  `CompletionClient` + `ActionChannel` into an `AgentLoop`.

Consequence: `tests/test_smoke.py` constructs a full `Episode` — config,
tool registry, memory, loop — using only `FakeLLMClient` (a scripted list of
JSON strings) and `LocalMockChannel` (an exact-match command→result
dictionary), and every assertion runs in well under a second with zero
external processes. That is also exactly what `run.sh --smoke` and
`python3 -m src.orchestrator.cli --smoke` exercise from the CLI.

---

## 4. The RAM budget — where this lane's pieces sit in the 16 GB

Reproduced from `constraint-cage.md` Part 4 / `constraint-cage-v2.md` B4
(3B driver, host running headless, **[EST]** until measured on the target
unit — see §7):

| Consumer | Lean | Comfortable | Owned by |
|---|---|---|---|
| Host OS + services (no GUI) | 1.2 GB | 2.0 GB | OS, not this repo |
| LLM weights (3B Q4_K_M) | 2.2 GB | 2.7 GB | `llama-server` process, started by `scripts/build_llama_cpp.sh` output |
| KV cache (ctx-dependent) | 0.4 GB | 1.2 GB | `llama-server`, bounded by `config.model.ctx` |
| **Agent + orchestrator runtime** | **0.2 GB** | **0.8 GB** | **this lane** — `src/agent`, `src/orchestrator` (pure Python today; Part 22/tech-stack calls out migrating the hot loop to Rust once the design stabilises, to shrink this row) |
| Guest VM (Alpine) | 1.5 GB | 3.0 GB | `challenges/**` / `vm/**` (golden image + libvirt) |
| QEMU overhead (non-guest) | 0.2 GB | 0.5 GB | libvirt/QEMU |
| **Telemetry + log buffer** | **0.2 GB** | **0.6 GB** | **this lane** — `src/telemetry` (NDJSON/SQLite sink, flushed aggressively per Part 11's REC) |
| FS cache / headroom | rest | rest | Linux page cache |
| **Subtotal committed** | **~6.1 GB** | **~10.8 GB** | |

The two rows this lane owns (agent+orchestrator runtime, telemetry) are
deliberately the smallest, least negotiable line items in the table — the
model and the guest are where the real budget pressure lives, and both are
outside this lane's control surface. `config/example.yaml`'s
`model.threads: 4` pins inference to the 2 P-cores' 4 hardware threads
specifically so the telemetry collector and orchestrator (both cheap,
E-core-friendly Python) never contend with decode for the fast cores
(`constraint-cage.md` Part 1: "reserve E-cores for VM + agent + telemetry").

**[OPEN]** None of the "Lean"/"Comfortable" figures above have been measured
on the actual target laptop yet. `scripts/validate_env.sh` plus a profiled
`run.sh` pass (with `/usr/bin/time -v` or `psutil`) is how this table's
`agent runtime` and `telemetry` rows convert from **[EST]** to **[FACT]**.

---

## 5. Host ↔ guest boundary: the one channel, and why it's narrow

Per Part 5/19 of the design docs, the guest is reachable **only** through
`src/agent/interfaces.py::ActionChannel` — never a filesystem bridge,
clipboard, or passthrough device. `src/orchestrator/channel.py` implements
three concrete channels behind that one interface:

| Channel | Status | Notes |
|---|---|---|
| `LocalMockChannel` | **Implemented, used today** | In-memory exact-match fixture. What `--smoke`, `tests/test_smoke.py`, and (until a real guest exists) the plain `--config` CLI path all use. No subprocess, no network, no VM. |
| `SSHChannel` | **Runnable-shaped stub** | Shells out to the `ssh` CLI per command. Every guest-specific assumption (host key policy, key path, user) is a `VMConfig` field, not hardcoded. TODO before pointing at a real cage: pin `known_hosts` instead of `StrictHostKeyChecking=accept-new`, and consider a persistent `ControlMaster` socket so per-step latency isn't dominated by repeated SSH handshakes. |
| `VsockChannel` | **Runnable-shaped stub, needs a guest-side counterpart** | Speaks a minimal newline-delimited JSON protocol over `AF_VSOCK`: `{"command", "timeout_s"}` in, `{"exit_code", "stdout", "stderr"}` out. Preferred transport per Part 5 (never touches a network stack — isolation by construction). **Nothing inside the guest speaks this protocol yet** — that listener is VM/challenge-image plumbing (`vm/**`), intentionally out of scope for this lane. Calling `execute()` today fails cleanly with a connection error, which is the correct, honest behavior for an unimplemented transport. |

Every channel logs `command`, `exit_code`, `ok`, and `duration_s` at INFO
level (`logger = logging.getLogger("cage.channel")`) — the "narrow, logged
channel" safety property from Part 19 has an audit trail by construction,
not by convention.

`Episode.reset_guest` (`src/orchestrator/episode.py`) is currently a
loud no-op: it logs a warning that the guest is **not** being reverted to a
golden snapshot rather than silently pretending isolation holds between
episodes. Wiring a real `libvirt`/`virsh` snapshot-revert call there is the
other half of the VM/challenge lane's integration surface — see §6.

---

## 6. Explicit seams for the other lanes

This lane's code is written to the *interfaces* the rest of the project
needs, without depending on their not-yet-final implementations:

| Seam | Where | What the other lane supplies |
|---|---|---|
| Real challenge goals | `src/orchestrator/episode.py::make_smoke_goal()`, called from `cli.py` | A `Goal` (id, description, level, `success_predicate`) loaded from `challenges/**`'s seeded generator instead of the hardcoded smoke fixture. `Goal` is already the exact pydantic shape needed (`src/agent/models.py`). |
| Guest snapshot revert | `src/orchestrator/episode.py::_default_reset_guest` (a `ResetGuestHook` callable) | A real `libvirt`/`virsh` revert-to-`golden`-snapshot call, swapped in via `Episode(reset_guest=...)`. |
| vsock listener inside the guest | `src/orchestrator/channel.py::VsockChannel` | A guest-side process speaking the documented newline-delimited JSON protocol on `(cid, port)`. |
| Batch running / statistics | `EpisodeResult` (`src/agent/models.py`) | `eval/**`'s runner consumes the same pydantic `EpisodeResult`/`StepRecord` schema this lane already writes to `{transcript_dir}/*.json` — no format translation needed. |
| Telemetry correlated with episodes | `src/telemetry/collector.py` + `TelemetryCollector.run()` | Not yet joined to `Episode.run()` by timestamp/episode-id — today they are two independently runnable pieces (`python -m src.telemetry` vs. `run.sh`). Joining them (e.g. tagging each `TelemetrySample` with the active episode's id) is a small follow-up once an episode reliably takes long enough to be worth correlating. |

---

## 7. Tech-stack mapping (Part 22's polyglot-by-constraint table, as built)

| Layer | Design doc's pick | What's actually in this lane today | Gap / next step |
|---|---|---|---|
| Inference engine | llama.cpp / GGUF, C++ | Not vendored here — `scripts/build_llama_cpp.sh` builds it CPU-only (AVX2, no CUDA/Vulkan/Metal) into `third_party/llama.cpp/build/bin/` | Pick + benchmark a checkpoint (Part 13); nothing this lane can do until `llama-bench` runs on the target host |
| Orchestrator / agent loop | Python → Rust (tokio) once stable | **Python** (`src/agent`, `src/orchestrator`) — typed with pydantic, protocol-decoupled per §3 | Matches Part 22's own sequencing: "Python to iterate fast early; migrate the hot loop to Rust for v0.4+." Migrating is a deliberate non-goal until the design is proven, not an oversight. |
| Model binding | `llama-server` over HTTP | `src/orchestrator/llm_client.py::LlamaServerClient` — `httpx`, OpenAI-compatible `/v1/chat/completions` | none — this is the shipped shape |
| Host↔guest channel | virtio-vsock / SSH | `src/orchestrator/channel.py` — both implemented as stubs, `LocalMockChannel` as the test double | Needs a real guest + guest-side vsock listener (§6) |
| Telemetry collector | Rust/Go, 1 Hz | **Python stub** (`src/telemetry`) per this task's brief | A Rust/Go rewrite is the Part 22 tech-stack recommendation for the *hardened* version; today's Python collector already fails soft per-source and is cheap enough for 1 Hz, but hasn't been profiled for cycle-stealing on the P-cores (§4's [OPEN]) |
| VM control | libvirt + QEMU/KVM | Not in this lane (`challenges/**`, `vm/**`) | — |
| Sandbox primitives | cgroups v2, seccomp, nftables | Not in this lane | — |
| Analysis / eval | Python (pandas/Polars) | Not in this lane (`eval/**`) | Consumes this lane's `EpisodeResult` JSON directly (§6) |

---

## 8. Reproducibility: what `config/example.yaml` pins

Per `constraint-cage.md` Part 18, one YAML file + a `--seed` should fully
determine one episode. `src/orchestrator/config.py::RunConfig` is the typed
schema; today it pins:

- **Model**: GGUF path + SHA-256 (currently `null` — **[OPEN]**, filled in
  once Part 13's checkpoint comparison runs), quant string, `llama-server`
  URL, context length, thread count.
- **Sampling**: temperature (default `0.0` — Part 17: fix sampling when
  measuring capability, not creativity), top-p/top-k, repeat penalty, seed.
- **VM**: image path, snapshot name, vCPU count, RAM, channel kind + its
  connection params.
- **Loop**: step budget, replan interval, summarizer char budget.
- **Telemetry**: enabled/hz/sink/output path.

`RunConfig.seed` (the top-level, `--seed`-controlled field) is what's
threaded into both the LLM's `seed` parameter and the transcript's output
filename (`{name}-seed{seed}.json`) — see the comment in
`Episode.run()` for why this is kept distinct from (but currently
authoritative over) `sampling.seed`, which stays in the schema as a
separately documented, pinned artifact for future runs that want LLM
sampling noise decoupled from the episode/challenge-instance seed.

---

## 9. What's genuinely done vs. stubbed — a one-screen honesty check

| Piece | Status |
|---|---|
| `AgentLoop` (OBSERVE→...→NEXT), typed tools, structured + failure memory, heuristic summarizer, periodic re-plan | **Implemented**, unit-tested, zero external dependencies to run |
| `ToolRegistry` (5 tools: `run_command`, `read_file`, `list_dir`, `check_port`, `submit_flag`) | **Implemented** |
| `LlamaServerClient` (real HTTP client) | **Implemented**; untested against a live `llama-server` (none running in this environment) — fails loudly with a connection error rather than silently, see `src/orchestrator/cli.py` |
| `FakeLLMClient`, `LocalMockChannel` | **Implemented**, this is what proves the plumbing today |
| `SSHChannel` | **Implemented**, unexercised against a real guest |
| `VsockChannel` | **Implemented client-side**, no guest listener exists yet — expected to fail until the VM lane ships one |
| `Episode` (config → loop → transcript) | **Implemented**; `reset_guest` is a loud no-op pending libvirt wiring |
| Telemetry collector (RAPL/sensors/turbostat/PSI/mem/tok-s → NDJSON/SQLite) | **Implemented** as a best-effort stub; every source fails soft; **not yet profiled or correlated with episodes** |
| `config/example.yaml` | **Implemented**; model path/hash left `null` pending Part 13 benchmarking |
| `scripts/validate_env.sh`, `scripts/build_llama_cpp.sh` | **Implemented**, read-only / standard build steps |
| `run.sh` | **Implemented**: creates/updates a venv, forwards to the CLI, defaults to `--smoke` with no arguments |

Everything in this table is exercised by `tests/test_smoke.py` except the
real `LlamaServerClient`/`SSHChannel`/`VsockChannel` paths, which need a
running model server / real guest respectively to test against — by
design, those fail honestly rather than being mocked into looking done.
