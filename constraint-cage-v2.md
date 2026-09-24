# The Constraint Cage — v2 (market-positioned)
### A CPU-only, single-laptop autonomous-agent "escape lab" — and the case that it is *not* just another CTF-agent project

**Target hardware:** Dell Inspiron 16 5640 · Intel **Core 7 150U** (2 P-cores + 8 E-cores, 12 threads, 15 W) · 16 GB RAM · 1 TB · Ubuntu 24.04.1 · **CPU-only inference, no useful GPU**
**Rev 2 · 2026-09-23** · Adds a verified competitive-landscape analysis (4-agent research sweep) on top of the v1 feasibility teardown.

> **What changed from v1:** v1 proved the project is *buildable* on this laptop. v2 answers the harder question you asked — *how is this different from an already-crowded market?* — using a literature sweep. Short version: the "can an LLM do privilege escalation / solve CTFs" question is **answered and saturated**. Your defensible, **verified-open** territory is a specific triple intersection nobody occupies. Lead with that or get lost in the crowd.

---

## Legend

| Tag | Meaning |
|---|---|
| **[FACT]** | Measured or from a vendor spec sheet / a paper we read. |
| **[EST]** | Engineering estimate — verify by measurement. |
| **[ASSUME]** | Stated assumption that could be wrong. |
| **[REC]** | Recommendation. |
| **[OPEN]** | Open question — resolve by measuring a named parameter. |
| **[LIT-VERIFIED]** | Confirmed against a primary source (paper/repo/blog) in the reference list. |
| **[LIT-INFERRED]** | Our synthesis from the literature; absence-of-evidence, treat as "probably" not "proven." |

---

# PART A — MARKET POSITION (the new material)

## A0 — The one-page map

**The crowded center (do NOT compete here):**
- "Frontier/API model solves X % of CTFs" leaderboards — Cybench, NYU CTF Bench, InterCode-CTF, CTFusion, CyberExplorer, CRAKEN. Well-funded labs, GPU/API budgets. **[LIT-VERIFIED]**
- Big-model automated pentest tools/products — PentestGPT, AutoPentester, XBOW (commercial), PentestAgent. **[LIT-VERIFIED]**
- **"Can an LLM agent chain Linux privilege escalation?" — already answered.** A 2026 paper post-trains a **Qwen3-4B** (your exact size class) to **95.8 % success at 20 rounds vs 97.5 % for Claude Opus**. **[LIT-VERIFIED]**
- Frontier-model cyber-risk safety frameworks — Meta CyberSecEval 1–3, DeepMind's cyberattack-capability framework. Policy/governance turf owned by the labs themselves. **[LIT-VERIFIED]**

**The white space you can actually own — a triple intersection no single paper covers:**

> **(1) CPU-only, single consumer laptop, no-GPU, ≤8B quantized inference** — as a *first-class reported constraint* — **×** **(2) autonomous discovery + chaining of engineered privilege/trust boundaries in a resettable VM** — **×** **(3) task-level efficiency + interpretability reporting** (solves-per-watt-hour, and a *failure taxonomy* of where/why the small agent stalls).

Every close prior work is missing **at least one** of those three legs. That intersection is the whole pitch. **[LIT-INFERRED, strong]**

**The single most damning piece of evidence in your favor:** the nearest paper (PrivEsc-LLM, Qwen3-4B) **trained on 4×H100 for ~29 h and benchmarked inference on an RTX 4090**, and its *own limitations section* says it does **not** evaluate CPU-only hardware or single-laptop scenarios, tested only one model family, and documented only two failure modes with **no systematic taxonomy**. Your project is almost precisely the shape of its "future work." **[LIT-VERIFIED]**

---

## A1 — Competitive landscape (what exists, and where it leaves a gap)

| Project / paper | What it is | Environment | Model class | Reproducible? | Leaves open |
|---|---|---|---|---|---|
| **Cybench** | 40 pro CTF tasks, agent sandbox | container | frontier/huge (GPT-4o, Claude 3.5, o1, Llama-405B) | partial | small/CPU, VM boundaries |
| **NYU CTF Bench** | 200 CSAW CTF challenges | Docker | big/API | yes (Docker) | resource constraint, privesc chains |
| **InterCode-CTF** | interactive code+exec env | Docker | capable | yes | small models, energy |
| **CTFusion** | static vs *live* CTF; caught agents "cheating" via web lookup | Docker | GPT-4.1/Claude/Gemini | yes | contamination warning ✔ (use it) |
| **HackingBuddyGPT / privesc paper** | autonomous Linux privesc, closest classic prior art | real Linux guests | GPT-3.5/4 | yes, OSS | CPU-only, small quantized, energy |
| **PrivEsc-LLM (Qwen3-4B)** | RL-trained 4B privesc agent, 95.8 % | GPU (H100 train, 4090 infer) | 4B **but GPU** | code-ish | **CPU-only, laptop, taxonomy** ← your gap |
| **PrivEscalate** | 531 Docker privesc scenarios, 6 LLMs | Docker | 6 LLMs | yes | no CPU-only mention |
| **Context-Segmentation SLM (picoCTF)** | small local models on CTF, fights context bloat | container(?) | gemma-class SLM | yes, OSS | VM privesc lattice, laptop HW, energy |
| **TrustedSec self-hosted benchmark** | 6 self-hosted models vs Juice Shop, 4,800 runs | server/Ollama | 24B–87B | methodology public | **all models fail multi-step chains** ✔ |
| **Intelligence-per-Watt (Stanford)** | defines Intelligence-per-Joule, profiles agent harnesses w/ RAPL | mixed HW | general local AI | yes, OSS | not security/adversarial tasks |
| **AgentErrorTaxonomy / AgentDebug** | failure taxonomy + annotated trace dataset | ALFWorld/GAIA/WebShop | unspecified | yes, dataset released | not small/quantized, not security |

**Two findings you should quote directly:**
- TrustedSec: self-hosted models "demonstrate more offensive-security knowledge than they can express through tool calls," and **all of them fail multi-step chained exploits** (single-step succeeds 85–98 %). → *Multi-step chaining by small models is still open.* **[LIT-VERIFIED]**
- Intelligence-per-Watt **exists and must be cited** as your nearest neighbor on energy — do **not** claim to be first at "outcome ÷ energy for agents." You are first (as far as the sweep found) at pairing it with *adversarial privesc on CPU-only laptop hardware.* **[LIT-VERIFIED]**

---

## A2 — The verified white space, leg by leg

1. **CPU-only / single-laptop / no-GPU / ≤8B quantized as a reported variable.** Nearest work (PrivEsc-LLM) explicitly disclaims it; small-model security work (Context-Segmentation, TrustedSec) still runs on servers/Ollama with 24–87B models. **This is your headline claim and the most concrete gap found.** **[LIT-VERIFIED gap]**
2. **Solves-per-watt-hour for a *security* agent.** Intelligence-per-Watt (arXiv 2511.07885) is the neighbor; Green Software Foundation confirms task-level agent energy accounting is an industry-wide gap. Pairing energy with privesc success on documented CPU hardware is unclaimed. **[LIT-VERIFIED adjacent, gap on the security pairing]**
3. **Interpretable failure taxonomy for small quantized agents under compute constraints in an engineered trust-boundary env.** The *method* (AgentErrorTaxonomy + released annotated traces, arXiv 2509.25370) is proven to get cited; nobody has applied it to *this population/task*. **Your strongest intellectual contribution.** **[LIT-VERIFIED method, gap on population]**
4. **Behavior — not just speed — under degraded compute.** Edge-inference papers measure latency/throughput/energy under thermal throttling; **none ask whether plan quality / exploration breadth / error mode changes** when RAM is scarce or the chip throttles mid-task. Genuine white space. **[LIT-VERIFIED gap]**
5. **Contamination-immunity via procedural boundary generation.** The field says novel, unseen-but-equivalent instances are needed (a reverse-engineering benchmark spent 5,000+ human-hours hand-authoring them). Your resettable VM gets this *almost for free* if you parameterize each boundary and regenerate per seed. **[LIT-VERIFIED need, cheap for you]**

---

## A3 — Positioning, naming, taglines

**[REC] Primary positioning — "The Trust-Boundary Ladder: an escape-lab on a laptop."**
Headline result to aim for: *"A reproducible measurement of how many engineered privilege/trust hops a 3–8B quantized, CPU-only agent chains unassisted — with an interpretable failure taxonomy of exactly where and why it stalls — none of which needed a GPU."*
Leads with the verified-open combination (small + zero-GPU + taxonomy), **not** "can an LLM hack a VM" (answered/crowded).

**Backup 1 — "Degraded Compute, Degraded Judgment."** *"Quantifying how thermal throttling and memory pressure change an agent's exploration strategy and error modes mid-task — not just its speed."* Your most defensible genuinely-open question; run it as a secondary experiment inside the same artifact.

**Backup 2 — "Planner Arbitrage."** *"The Pareto frontier between $ of frontier-planner tokens and trust-boundary hops a cheap local executor completes."* More applied-economics than research; keep it a bonus chapter.

**Naming / framing to AVOID:**
- ❌ Any **"first"** claim on LLM-does-privesc — provably not first.
- ❌ Bare **"escape" / "sandbox escape"** naming — collides with Gandalf, EscapeBench, SandboxEscapeBench; reads derivative.
- ❌ Hype ("AI escaped," "found a real 0-day," "self-aware") — it's a contained toy VM with boundaries *you* built; oversized language loses the technical audience.
- ❌ **"Red-teaming"** as the headline word — now default enterprise vocabulary; buries your actual novelty.
- ❌ Pitching pure capability numbers ("we got X %") as the whole story — that's the saturated axis.

---

## A4 — Methodology as the moat (out-rigor the field)

The differentiator isn't only *what* you measure — it's measuring it more honestly than a crowded field that mostly doesn't. Each practice below is drawn from a 2025–2026 paper and is cheap to adopt.

| # | Field weakness (verified) | What you do instead |
|---|---|---|
| 1 | Single-run "hero numbers"; on hard tasks ~70 % of reported variance is trial-to-trial noise (ICC as low as 0.30). | **N ≥ 30 attempts per boundary**, report success ± 95 % CI **and** an ICC-style variance split (within- vs across-boundary). 8–16 trials easy tasks, ≥32 hard. |
| 2 | Inference backend alone drives **~39 %** of score variance under greedy decoding. | **Version-pin & disclose the full stack** as a first-class variable: llama.cpp build/commit, quant format, ctx length, threads, sampling/seed. Re-run a subset on a 2nd backend as a sensitivity check. |
| 3 | Contamination/memorization: CTF/CVE instances may be in training data → "solving" = recall. | **Procedurally parameterize each boundary** (paths, creds, ports, symbol names, service versions, topology); regenerate a fresh never-published instance per seed. Ship a **held-out probe variant** per boundary class to test transfer vs recall. |
| 4 | Failure taxonomies exist but not for security-boundary chaining by small models. | **Pre-register a failure codebook** (boundary-not-found / found-not-exploited / exploited-intended / exploited-unintended / tool-hallucination / loop-abandonment) and report the *distribution*, not just pass rate. |
| 5 | Thermal/memory-pressure confounds essentially unreported in agent-security evals; an iPhone 16 Pro lost **~40 % throughput in 3 iterations** under sustained load. | **Log temp/freq/throughput per trial**, pre-equilibrate to steady-state, flag/segregate throttled runs. Simply reporting this puts you ahead of the entire agent-security literature the sweep found. |
| 6 | "State contamination": memory-augmented agents leak state across supposedly independent trials; temp=0 ≠ determinism. | **Checksum/immutable VM snapshots** to prove clean resets; measure and report actual repeat-run variance rather than asserting determinism. |

---

## A5 — Artifact strategy (what makes it get adopted, not just admired)

Traction in this space comes from a **scored ladder + released annotated traces + a reusable dataset** — not a pass/fail blob. Papers that got cited beyond their authors (AgentErrorBench, TRAIL) did it by becoming *raw material* others mine.

**[REC] Ship the differentiated bundle — all laptop-runnable:**
1. **Seeded QEMU snapshots** — a scored ladder of engineered trust-boundary hops (Levels 1–7, Part 6).
2. **Full released agent traces**, annotated with the failure taxonomy (A4 #4).
3. **A per-attempt resource-telemetry log** — RAM, CPU temp/throttle state, context length, tokens/sec, **joules** — the metadata nobody else ships.
4. **A one-command reproducer** — `run.sh --seed 42 --config c.yaml` → byte-comparable transcript.

Every existing security-agent benchmark implicitly assumes a GPU. **A clone-and-run-on-a-no-GPU-laptop benchmark directly lowers the reproducibility barrier the field's own critics complain about** — that, plus the trace+telemetry dataset, is the contribution. **[LIT-VERIFIED gap]**

**Honest risks (say them out loud in the write-up):**
- The capability claim ("small agent chains privesc") is **not novel** — cite PrivEsc-LLM / PrivEscalate / CVE-Bench up front to preempt "so what," and lead with the hardware + interpretability framing.
- "No GPU" is a limitation, not automatically a contribution — it only becomes one if the artifact is **genuinely runnable by others** (real packaging effort).
- At least one adjacent repo ("Scaffolded Capability Ceiling") may exist — verify before claiming an empty niche.
- One laptop = limited statistical power (slow wall-clock, few parallel runs) — be explicit about seeds/CIs; no anecdote-level "it escaped once" findings.

---

# PART B — THE TECHNICAL TEARDOWN (from v1, kept + tightened)

## B1 — Hardware → constraints

**[FACT]** Core 7 150U = **2 P-cores + 8 E-cores, 12 threads**, 12 MB L3, **15 W base / 55 W turbo**, 5.4 GHz P / 4.0 GHz E, **AVX2, no AVX-512**. **The one line that matters: you have two fast cores, not twelve.** E-cores are for OS/VM/telemetry, not decode.

| Component | Reality | Bottleneck | Sev | Mitigation |
|---|---|---|---|---|
| P-cores (2) | Decode + prefill live here | **Hard tok/s ceiling** | HIGH | Pin inference to P-cores; small models |
| E-cores (8) | Good for VM/OS/logging, poor for decode | Misused as inference threads | MED | Reserve for VM + agent + telemetry |
| RAM 16 GB | Everything competes | **Binding constraint** | HIGH | Explicit budget (B4); zram |
| Mem bandwidth | LPDDR5-5200 *(channels?)* | **Decode throughput** | HIGH | Verify dual-channel (B-cmds) |
| Thermal | 15 W in thin 16" chassis | **Long-run stability** | HIGH | Duty-cycle; log & flag throttling |
| GNOME | idles 1.2–2 GB | Wasted RAM | MED | Run headless (TTY) during runs |

**vCPU truth:** don't map 12 threads → 12 vCPUs. **2 vCPU** (E-cores) recommended; 4 for service-heavy challenges; **8+ oversubscribes and slows everything, including the guest.** "More vCPUs ≠ faster AI" — the model isn't in the guest (B3), and decode is memory-bandwidth-bound, not core-bound. **[EST]**

## B2 — CPU-only inference physics

```
tokens/sec ≈ realized memory bandwidth (GB/s) ÷ quantised model size (GB)
```
Decode is **bandwidth-bound**; prefill is **compute-bound** but you only have 2 strong cores → long context is slow both ways. **[OPEN] Measure memory channels first** — single-channel (~40 GB/s) vs dual (~80 GB/s) **doubles or halves every number below.**

**Model classes for *sustained autonomous* use** (Q4_K_M, dual-channel; halve for single) **[EST]:**

| Class | Q4 size | Est. decode | Verdict |
|---|---|---|---|
| 1B–2B | 0.7–1.4 GB | 25–50 tok/s | 🟢 fast, weak — lean on scaffolding |
| **3B–4B** | 2–2.7 GB | 12–25 tok/s | 🟢 **default driver — the sweet spot** |
| 7B–8B | 4.4–4.9 GB | 5–11 tok/s | 🟡 best reasoning, RAM-tight w/ VM |
| 12–14B | 7–9 GB | 3–7 tok/s | 🟡→🔴 squeezes out the VM; planner only |
| 20B+ | 12 GB+ | <3 tok/s | 🔴 starves VM, swaps, throttles |

## B3 — Where the model runs (Architecture C)

Model **inside** the VM (Arch A) is the worst option on 16 GB — pays the model's RAM inside the guest and blinds you to its reasoning. **[REC] Architecture C:** llama.cpp model + thin orchestrator **on the host**; the KVM guest is the isolated, snapshot-able **cage** the agent touches only through a narrow, logged vsock/SSH channel. Keep **Arch D** (cheap local executor + occasional frontier planner) as the "planner-arbitrage" experiment (A3 backup 2).

## B4 — 16 GB budget (3B driver, headless) [EST]

| Consumer | Lean | Comfortable |
|---|---|---|
| Host (no GUI) | 1.2 | 2.0 |
| LLM 3B Q4 | 2.2 | 2.7 |
| KV cache | 0.4 | 1.2 |
| Agent runtime | 0.2 | 0.8 |
| Guest VM (Alpine) | 1.5 | 3.0 |
| QEMU + telemetry | 0.4 | 1.1 |
| **Committed** | **~6.1 GB** | **~10.8 GB** |

7B + 3 GB guest ≈ 13–14 GB committed with no page-cache headroom → swap → decode collapses. That's why 7B is Yellow. **Sacrifice order:** GNOME → guest RAM → context/KV → model size. **Never** sacrifice telemetry integrity or snapshot safety. Use **zram 3 GB + small swapfile + swappiness 15 + cgroup caps.**

## B5 — VM (resettable target) & the cage (Levels 0–7)

Alpine guest, **2 vCPU (E-cores) / 1.5–3 GB / 8–20 GB qcow2 CoW**, UEFI/OVMF, **virtio-net on isolated NAT or no NIC**, **virtio-vsock** action channel, serial console, external snapshots. **Off:** shared folders/virtiofs, clipboard, USB/GPU passthrough, LAN bridge, host keys/secrets.

**Levels:** 0 normal → 1 unprivileged user → 2 filesystem locks → 3 network limits → 4 process/cgroup limits → 5 capability drops → **6 deliberately-vulnerable engineered flaw** → **7 multi-stage chain.** "Escape" = crossing an **in-guest** privilege/trust boundary *you built*, never the hypervisor.

## B6 — The agent loop

OBSERVE → STATE(facts/tried/open-Qs) → HYPOTHESIS → PLAN(one cheap test) → ACTION(typed tool) → OBSERVATION → EVALUATE → UPDATE → NEXT (until goal | step-budget | give-up).
**Essential on this HW:** executor, structured + **failure memory**, state summarizer, goal tracker. **Periodic** (not per-step) re-planning. **Few typed tools.** **No sub-agents** (multi-inference = unaffordable). Buy the intelligence you can't get in parameters with scaffolding.

## B7 — Distinguishing luck from strategy

Report **transfer across seeds** (the definitive test — luck doesn't generalize), **actions-to-solve vs optimal**, recovery-after-failure, and monotone belief progress. Distributions over ≥N seeds with CIs, never a hero run (see A4).

---

# PART C — TECH STACK (polyglot by constraint)

| Layer | Pick | Language | Why here | Alt |
|---|---|---|---|---|
| Inference engine | **llama.cpp / GGUF** | **C/C++** | AVX2 CPU kernels, quantization, thread pinning — the reason CPU-only is viable | ONNX RT, oneDNN |
| Orchestrator / loop | Python → **Rust** (tokio) | Rust/Python | Python to iterate; Rust for lean async, tight RAM, typed state machine | Go |
| Model binding | `llama-server` (HTTP) or FFI | C++↔any | clean language boundary | candle (Rust) |
| VM control | **libvirt + QEMU/KVM** | C API + XML | snapshots, revert, domstats | Firecracker |
| Host↔guest | **virtio-vsock** / SSH | Rust/Go/C | narrow, loggable, no network path | gRPC/Cap'n Proto |
| Telemetry | collector → TSDB | **Rust/Go** | 1 Hz RAPL/temps/freq/PSI w/o stealing cycles | Prometheus |
| Deep observability | **eBPF** (syscalls/sched) | C/BPF+Go | near-zero-overhead tracing — a real systems flex | bpftrace/bcc |
| Sandbox primitives | cgroups v2, seccomp, namespaces, nftables | C/shell | the cage levels are kernel features | AppArmor, sVirt |
| Analysis/eval | pandas / **Polars**, matplotlib | Python | offline, off the hot path | — |

**The four languages, honestly:**
- **C/C++** — the engine room (llama.cpp, eBPF). You consume more than write it, but understanding its threading/SIMD is what tunes tok/s on 2 P-cores. *Signal: low-level perf, SIMD.*
- **Rust** — the orchestrator, vsock channel, telemetry: memory-safe, no GC, tiny footprint, tokio concurrency. Fits a RAM-starved box. *Signal: systems Rust, async, safety.*
- **Go** — the pragmatic middle: easier than Rust, great for the collector and control-plane. *Signal: concurrent services.*
- **Python** — glue + lab bench: fastest to a working loop, unbeatable for analysis; migrate the loop out once stable. *Signal: prototyping, data science.*

> **One line:** prototype in Python, harden in Rust, infer in C++, observe with eBPF, orchestrate VMs with libvirt, analyse in Python/Polars. Each language mapped to the constraint it beats — defensible in an interview by pointing at the 2-core / 16 GB / 15 W budget.

**Starter toolbox:** llama.cpp (`llama-bench`, `llama-server`) + GGUF Q4_K_M · Python `httpx`/`pydantic` → Rust `tokio`/`serde`/`vsock` · QEMU/KVM + libvirt/virsh + OVMF + Alpine · cgroups v2/seccomp/nftables/AppArmor · `turbostat`/`lm-sensors`/RAPL/`/proc/pressure` + Prometheus/Grafana or SQLite/Parquet · `bpftrace`/`bcc` · pandas/Polars/matplotlib/Jupyter.

---

# PART D — BUILD, VALIDATE, FINAL

## D1 — Build plan (v2: eval-rigor is now its own gated phase)

| Phase | Deliverable | Test / stop condition |
|---|---|---|
| 1 Environment | host validated, llama.cpp built, `llama-bench` | know true tok/s + RAM channels |
| 2 VM | golden image, scripted snapshot/revert | byte-identical reset in seconds |
| 3 Agent | OBSERVE→NEXT loop, typed tools, memory | solves a hardcoded task; clean transcript |
| 4 Challenge | **procedurally-parameterized** L1–L6, seeded | human + scripted solver both pass; **held-out probe variant works** |
| 5 Telemetry | 1 Hz resource + **energy (RAPL)** + traces → TSDB | every episode reconstructable; low overhead |
| **6 Eval-rigor** (new) | batch runner, **N≥30/seed, CIs, ICC, failure-taxonomy coding, thermal flagging** | stable metrics with CIs; contamination controls documented |
| 7 Hardening | isolation audit (net/cgroup/seccomp) | guest cannot reach host (verified) |
| 8 Demonstration | reproducible write-up + **released traces/telemetry dataset** + one headline result | third party reproduces from seed on a no-GPU box |

## D2 — Command-level validation (run before trusting any [EST])

```bash
# CPU topology (confirm 2P+8E)
lscpu; lscpu --all --extended; grep -m1 flags /proc/cpuinfo   # avx2? no avx512
# ★ Memory channels — THE key measurement (1 module ⇒ halve every tok/s)
sudo dmidecode -t memory; sudo lshw -short -C memory
# RAM / swap
free -h; swapon --show; cat /proc/sys/vm/swappiness; zramctl
# Storage
lsblk -o NAME,SIZE,ROTA,TYPE,MOUNTPOINT; nvme list 2>/dev/null; df -h /
# GPU (confirm nothing to offload to)
lspci | grep -Ei 'vga|3d|display'; ls /dev/dri 2>/dev/null
# KVM stack
ls -l /dev/kvm; egrep -c '(vmx|svm)' /proc/cpuinfo; kvm-ok 2>/dev/null
systemctl status libvirtd; qemu-system-x86_64 --version; virsh version
# Thermals / power (baseline, then under load)
sensors; sudo turbostat --interval 1; ls /sys/class/powercap/intel-rapl*
# Kernel / containers / net
uname -a; cat /etc/os-release; docker --version 2>/dev/null; ip -br addr
```

**[OPEN] Report three numbers and the design becomes concrete:** (1) memory **channels** (`dmidecode`), (2) measured **tok/s** for 3B & 7B Q4 at 4k ctx *with the VM running* (`llama-bench`), (3) **sustained** P-core clock + PkgWatt after ~10 min load (`turbostat`). These collapse most [EST] into [FACT] — and #3 doubles as your first "degraded compute" data point.

## D3 — Final architecture (v2)

| Aspect | Decision |
|---|---|
| **Positioning** | "Trust-Boundary Ladder — escape-lab on a laptop": small + zero-GPU + failure taxonomy; **not** "can an LLM hack a VM." |
| **Headline result** | how many engineered trust hops a 3–8B CPU-only agent chains unassisted, **+ a failure taxonomy of where/why it stalls, + joules-per-solve** — no GPU. |
| **Differentiators** | (1) CPU-only single-laptop ≤8B as a reported variable · (2) solves-per-watt-hour for a security agent · (3) interpretable failure taxonomy for small quantized agents · (4) behavior (not speed) under degraded compute · (5) contamination-immune procedural boundaries. |
| **Architecture** | C: llama.cpp + thin orchestrator on host; KVM guest = cage; logged vsock channel; optional Arch-D planner-arbitrage. |
| **Model** | 3B–4B Q4_K_M strong tool-calling default; 7B comparator; frontier API only as planner. |
| **VM** | 2 vCPU (E-cores) · 1.5–3 GB · 8–20 GB qcow2 CoW · UEFI · isolated NAT · vsock · external snapshots. |
| **Agent** | one model, one loop; executor + structured/failure memory + summarizer + goal tracker; periodic re-plan; few typed tools; no sub-agents. |
| **Eval** | N≥30/seed, CIs + ICC, procedural instances + held-out probe (transfer vs recall), failure-taxonomy distribution, thermal/memory logged & flagged, pinned inference stack. |
| **Safety** | in-guest engineered boundaries only; snapshots; isolated net; no host mounts/secrets; planted fakes; confined unprivileged QEMU; patched hypervisor. Host must not fall. |
| **Artifact** | seeded QEMU snapshots + scored ladder + released annotated traces + per-attempt resource/energy telemetry + one-command reproducer. |
| **Stacks** | infer C/C++ · orchestrate Python→Rust · telemetry Rust/Go + eBPF · VMs libvirt · analysis Python/Polars. |
| **MVE (v0.3)** | 3B agent (host) solving a seeded, parameterized Level-6 boundary in a resettable Alpine guest over vsock, tok/s + joules + actions-to-solve logged across ≥20 seeds. ~2–3 weeks. |
| **Strongest version** | a reproducible single-laptop escape-lab **benchmark + trace/telemetry dataset** measuring whether a tiny, fast, heavily-scaffolded agent discovers and *transfers* engineered boundary-crossings — **per joule** — with a failure taxonomy no GPU-based paper has produced. |

---

## References (verified during the 4-agent sweep)

**Closest prior art / the gap:**
- Post-Training Local LLM Agents for Linux Privilege Escalation with Verifiable Rewards — https://arxiv.org/html/2603.17673v1 *(Qwen3-4B, GPU-only, disclaims CPU/laptop — your key evidence)*
- HackingBuddyGPT / LLMs as Hackers: Autonomous Linux Privilege Escalation — https://arxiv.org/abs/2310.11409 · https://github.com/ipa-lab/hackingBuddyGPT
- PrivEscalate — https://arxiv.org/html/2609.09087
- Evaluating Context Segmentation in Locally Deployable SLMs for CTF — https://arxiv.org/abs/2609.12839 · https://github.com/9xeb/context-segmentation
- TrustedSec — Benchmarking Self-Hosted LLMs for Offensive Security — https://trustedsec.com/blog/benchmarking-self-hosted-llms-for-offensive-security

**Crowded center:**
- Cybench — https://arxiv.org/abs/2408.08926
- NYU CTF Bench — https://arxiv.org/abs/2406.05590 · https://github.com/NYU-LLM-CTF/NYU_CTF_Bench
- InterCode — https://intercode-benchmark.github.io/
- CTFusion — https://arxiv.org/html/2605.11504v2
- PentestGPT — https://arxiv.org/abs/2308.06782
- CVE-Bench — https://arxiv.org/html/2503.17332v3
- Container Sandbox Escape (frontier) — https://arxiv.org/abs/2603.02277
- Meta CyberSecEval 3 — https://ai.meta.com/research/publications/cyberseceval-3-advancing-the-evaluation-of-cybersecurity-risks-and-capabilities-in-large-language-models/
- DeepMind cyberattack-capability framework — https://arxiv.org/html/2503.11917v3

**Energy / small-model / edge:**
- Intelligence per Watt (Stanford) — https://arxiv.org/abs/2511.07885 · https://github.com/HazyResearch/intelligence-per-watt
- Small Language Models are the Future of Agentic AI (NVIDIA) — https://arxiv.org/abs/2506.02153
- AgentFloor (0.27B–32B vs GPT-5) — https://arxiv.org/html/2605.00334v1
- LLM Inference at the Edge: Thermal Constraints Under Sustained Load — https://arxiv.org/html/2603.23640v2
- Tokens and Greens (Green Software Foundation) — https://greensoftware.foundation/articles/tokens-and-greens-measuring-the-impacts-of-agentic-ai/
- Plan Once, Then Act (small-model harness failure modes) — https://www.vietanh.dev/blog/2026-06-15-plan-once-then-act-small-model-agents

**Methodology rigor:**
- Stochasticity in Agentic Evaluations (ICC) — https://arxiv.org/html/2512.06710v1
- Don't Pass@k (Bayesian eval) — https://arxiv.org/html/2510.04265v3
- LLM Behavior as Inference-Backend Side-effect (~39% variance) — https://arxiv.org/html/2608.04714v1
- Contamination-Free RE Benchmark — https://arxiv.org/abs/2608.11469
- Patterns for Building Cybersecurity Evals (Eugene Yan) — https://eugeneyan.com/writing/cybersecurity-evals/
- Characterizing Faults in Agentic AI (taxonomy) — https://arxiv.org/html/2603.06847v1
- Where LLM Agents Fail / AgentErrorTaxonomy + AgentDebug — https://arxiv.org/abs/2509.25370
- State Contamination in Memory-Augmented LLM Agents — https://arxiv.org/pdf/2605.16746
- Benchmarking is Broken — https://arxiv.org/html/2510.07575v2

**Positioning / traction:**
- Gandalf (resettable boundary-game precedent) — https://vvolhejn.com/2023/05/09/gandalf.html
- Launch-Day Diffusion: HN → GitHub stars — https://arxiv.org/html/2511.04453v1
- Efficient LLM Collaboration via Planning (planner arbitrage) — https://arxiv.org/html/2506.11578v3

**Hardware:**
- Intel Core 7 150U spec — https://www.intel.com/content/www/us/en/products/sku/236795/intel-core-7-processor-150u-12m-cache-up-to-5-40-ghz/specifications.html

> **Confidence note:** arXiv IDs in the 25xx–26xx range were returned and read by the research agents during the sweep; treat "nobody has done exactly X" as *strong-but-not-absolute* — grey literature (HN, r/LocalLLaMA, Discord) was not exhaustively searched, so a targeted search there is worth doing before you claim an empty niche in a public write-up.
