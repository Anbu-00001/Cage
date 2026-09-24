# De-risking research — the parts most likely to bite

Targeted web research (2026-09-24) on the six highest-risk technical unknowns before
committing implementation effort. Each item: the risk, what the research says, the
recommendation, and residual open questions. Legend tags as elsewhere; `[VERIFIED-2026-09]`
= confirmed against a primary/community source this session (linked at the bottom).

> TL;DR ranking of what could actually cost days or break the safety story:
> 1. **Memory channels** — still the #1 unknown; a stock 16 GB unit *may be single-channel*. [OPEN]
> 2. **RAPL energy access** — root-only by default; needs a udev rule or joules/solve is blocked. [VERIFIED-2026-09] → mitigated
> 3. **JSON/tool-call reliability** — was the scariest loop-killer; **solved by grammar-constrained decoding**. [VERIFIED-2026-09]
> 4. **P/E-core thread pinning** — real 3× swing; pin to P-cores. [VERIFIED-2026-09]
> 5. **vsock channel** — straightforward; one libvirt XML stanza. [VERIFIED-2026-09]
> 6. **QEMU confinement + fast reset** — libvirt gives most of it for free; use overlay-discard reset. [VERIFIED-2026-09]

---

## 1. Memory channels — single vs dual (THE bandwidth multiplier) `[FACT — measured 2026-09-24]`

**Risk:** decode tok/s ≈ bandwidth ÷ model size. Single-channel ~halves it → every tok/s
`[EST]` in the design docs could be 2× optimistic.

**MEASURED on this unit `[FACT]`:** `bench/membw` (C++ STREAM triad, built + run here) reports
**42.2 GB/s peak realized bandwidth** → **single-channel**. A dual-channel DDR5-5200 config
would land ~60–75 GB/s on STREAM triad; 42 GB/s sits right at the single-channel theoretical
(~41.6 GB/s). Thread scaling: 1 thread 11.6 · 2 → 12.9 · 4 → 13.5 · 8 → 39.2 · 12 → 42.2 GB/s.
(Confirm the module count with `sudo dmidecode -t memory` — needs a password here — but the
bandwidth is decisive on its own.) **Prediction `ffe5dd` resolved FALSE** (I'd guessed dual).

**Consequences (act on these):**
- **Halve the design docs' tok/s table.** At 42 GB/s: 3B Q4 (~2 GB) → ~21 tok/s ceiling; 7B Q4
  (~4.5 GB) → ~9 tok/s. This *strengthens* the "3B–4B default, 7B comparator" choice — 7B is now
  clearly Yellow/Red for sustained autonomous use. Bias to 1B–4B.
- **Cheapest upgrade in the project:** if `dmidecode` shows 1×16 GB, adding a matched 8 GB stick
  (→ 2×8 dual-channel) would roughly *double* the tok/s ceiling. Flag it in the write-up.
- **Thread-count — RESOLVED by direct `llama-bench` measurement (see §4).** The membw STREAM
  ceiling (~42 GB/s) needs many threads, which tempted the hypothesis "decode may want more
  threads too." **Measured: it does NOT.** Real decode is *fastest at 2 threads (the P-cores)*
  and degrades as E-core threads are added. STREAM's parallel scaling does not transfer to
  llama.cpp decode — a clean "measure, don't assume" catch that confirms the "2 fast cores"
  thesis rather than the bandwidth-ceiling extrapolation.

## 2. RAPL energy counters — root-only by default `[VERIFIED-2026-09]` → mitigated

**Risk:** joules/solve and solves/watt-hour are headline metrics. If RAPL can't be read, the
whole energy leg is blocked.

**Findings:** since the PLATYPUS side-channel disclosure (CVE-2020-8694), Linux distros made
`/sys/class/powercap/intel-rapl:*/energy_uj` **root-readable only**. Non-root reads fail with
`permission denied` (confirmed across node_exporter, codecarbon, pyJoules, powerjoular issue
trackers). Prediction `78f6ed` **resolved TRUE**.

**Recommendation:** ship a documented setup step — a **persistent udev rule** rather than a
one-off chmod:
```
# /etc/udev/rules.d/70-rapl.rules  (installed by scripts/validate_env.sh --fix-rapl)
SUBSYSTEM=="powercap", ACTION=="add", RUN+="/bin/chmod -R a+r /sys/devices/virtual/powercap"
```
(Some kernels need the rule applied to `/sys/devices/virtual/powercap` because the sysfs
files are virtual; the plain `intel-rapl` class path can be finicky — verify with
`udevadm test`.) Fallback: read energy via `perf stat -e power/energy-pkg/` which is gated by
`kernel.perf_event_paranoid` instead — document both paths. **Record in the reproducibility
manifest whether the run used the udev rule or perf**, since the access path is itself a
config variable.

## 3. Structured output / tool-calling reliability `[VERIFIED-2026-09]` → largely solved

**Risk:** the design docs call broken JSON "the #1 loop-killer" — a small model that emits
malformed tool calls stalls every episode.

**Findings:** llama.cpp has **native GBNF grammar-constrained decoding** and will **convert a
JSON Schema → grammar automatically** (`--json-schema` / `response_format` /
`--grammar-file`). Constrained decoding **masks invalid tokens at each step, so malformed JSON
is never generated** (not corrected after the fact — prevented). Community evidence: ~1000
structured-extraction calls on **Llama-3.2-3B Q4_K_M** with **no retries, no defensive
parsing**, ~5–8 % throughput overhead.

**Recommendation:** define every typed tool as a pydantic model (already done in
`src/agent/tools.py`), export its JSON Schema, and pass it to `llama-server` as the grammar
constraint per step. This turns "hope the model emits valid JSON" into a guarantee and lets us
**delete speculative parse-retry code** — budget the 5–8 % overhead. Residual `[OPEN]`:
grammar constrains *syntax*, not *semantics* (it can still pick a valid-but-wrong tool or
argument) — that's a reasoning failure the taxonomy already captures (`tool-hallucination`),
not a parse failure.

## 4. P-core / E-core thread pinning `[FACT — measured on this unit 2026-09-24]`

**Risk:** naively using all 12 threads on the hybrid 150U can *reduce* tok/s via cross-cluster
scheduling and cache contention.

**MEASURED on this laptop `[FACT]`** — `llama-bench`, Qwen2.5-0.5B Q4_K_M (0.46 GB), decode (tg64):

| threads | decode tok/s |
|---|---|
| **2 (P-cores)** | **39.6** ← best |
| 4 | 20.9 |
| 8 | 20.9 |
| 12 | 15.7 |

**Decode is fastest at exactly 2 threads and monotonically degrades as E-core threads are
added** — a direct, on-device confirmation of the whole "two fast cores, not twelve" thesis
(constraint-cage.md Part 1). Prefill (pp) is noisier and prefers more threads (compute-bound),
but decode — which dominates autonomous-loop latency — wants the 2 P-cores alone. Temp went
53→59 °C across the sweep (no thermal issue). This *refutes* the membw-derived "decode may want
more threads" guess (§1): STREAM's embarrassingly-parallel streaming saturates aggregate DRAM
with many threads, but llama.cpp decode has per-token dependencies where E-cores' low IPC +
cross-cluster latency dominate.

**tok/s anchors — BOTH MEASURED on this unit `[FACT]`** (`llama-bench`, Q4_K_M, decode/tg):

| model | size | best decode tok/s | effective GB/s | best threads |
|---|---|---|---|---|
| Qwen2.5-**0.5B** | 0.46 GB | **39.6** | ~18 | 2 |
| Qwen2.5-**3B** (the driver) | 1.95 GB | **~4.4** | ~8.6 | 4 (≈ t=2's 4.0) |

**The driver runs at only ~4 tok/s on this single-channel laptop.** Two corrections this forces:
1. Effective bandwidth is **not constant across model size** — my 0.5B→3B extrapolation (predicted
   9–13 tok/s, `bb1c81`) was **wrong (resolved FALSE)**: the larger 3B footprint realizes only
   ~8.6 GB/s at low thread counts vs the 0.5B's ~18, so measured 3B decode (~4) is ~half the naive
   scaling. Always measure the actual driver, never extrapolate across a 6× size gap.
2. Optimal threads is **model-size-dependent**: 0.5B peaks at 2 threads, 3B is flat/slightly better
   at 4 (more compute per token before bandwidth saturates). Both are close; the "≈2 P-cores" rule
   holds directionally.

**Design implication (real):** at ~4 tok/s a ~200-token step takes ~50 s, so a 40-step episode is
~30+ min — the "many cheap attempts" premise is strained at 3B on this box. Levers: (a) prefer a
**1–1.5B driver** here and lean harder on scaffolding to cut tokens/step; (b) the 2×8 GB
dual-channel upgrade (~doubles bandwidth → ~8 tok/s) becomes the highest-ROI change; (c) the
planner-arbitrage tier (cheap local executor + occasional API planner) looks more attractive.
This is exactly the kind of constraint the project exists to surface honestly.

**Findings (prior, web):** on Intel 12th-gen hybrids, **P-core-only execution measured ~3× faster**
than mixed scheduling for llama.cpp; some users disable E-cores in BIOS for inference. Prediction
`a244fe` **resolved TRUE**, now doubly confirmed by the measurement above.

**Findings:** on Intel 12th-gen hybrids, **P-core-only execution measured ~3× faster** than
mixed scheduling for llama.cpp; pure affinity alone isn't perfect (E-cores may still take
60–70 % load unless explicitly excluded); some users disable E-cores in BIOS for inference.
Prediction `a244fe` **resolved TRUE**. General llama.cpp guidance: `--threads` = **physical**
cores, not logical, and its default (all threads) is "rarely optimal."

**Recommendation:** pin inference to the 2 P-cores. Concretely: identify P-core CPU ids via
`lscpu --all --extended` (look for the higher max-MHz cluster), then
`taskset -c <p-core-ids> llama-server --threads 2 --threads-batch 4 ...`. Reserve E-cores for
QEMU/OS/telemetry via `taskset`/cgroup `cpuset`. **Benchmark `--threads 2` vs `4` vs `all`
with `llama-bench`** and report the winner — this doubles as a nice figure. Keep BIOS E-cores
*on* (we need them for the VM); isolate by affinity, not by disabling.

## 5. Host↔guest vsock channel `[VERIFIED-2026-09]` → low risk

**Risk:** the "narrow, logged, no-network" action channel is core to Architecture C; if it's
fiddly it could stall Phase 3.

**Findings:** trivial in libvirt. Host is always **CID 2**; each guest gets a unique **CID > 2**.
Guest needs **no configuration** — the `AF_VSOCK` family gives standard POSIX socket calls
(`bind/listen/accept/connect/send/recv`). libvirt XML:
```xml
<devices>
  <vsock model='virtio'><cid auto='no' address='3'/></vsock>
</devices>
```
(or `auto='yes'` to let libvirt assign the CID). Load `vhost_vsock` on the host; `vsock` in
the guest.

**Recommendation:** implement `VsockChannel` (stub already in `src/orchestrator/channel.py`)
against `socket.socket(AF_VSOCK, SOCK_STREAM)`; guest runs a tiny action-executor daemon that
accepts one connection, reads a length-prefixed typed request, runs it, returns
result+exit+timing. Log every frame host-side. This keeps the guest network-free (isolation by
topology). Residual `[OPEN]`: confirm `AF_VSOCK` present in the Alpine guest kernel (mainline
since 4.8; Alpine `virt` kernel includes it — verify).

## 6. QEMU confinement + fast per-trial reset `[VERIFIED-2026-09]` → mostly free

**Risk (safety-critical):** the whole safety story is "host is sacred." Getting confinement
wrong undermines the project.

**Findings — confinement:** using libvirt correctly gives most of the defense for free.
libvirt launches QEMU with its **built-in seccomp policy** (`obsolete=deny`,
`elevateprivileges=deny`), and on Ubuntu applies **AppArmor sVirt** — a *per-VM profile keyed
to the domain UUID* that permits only the files that VM needs. Add **cgroup** resource caps and
**Linux namespaces** to shrink the host resources QEMU can see. This matches the docs' Part 19
checklist and is standard, not custom kernel work.

**Findings — reset:** the docs said "external qcow2 + libvirt snapshots," but research shows
**libvirt has no `snapshot-revert` for *external* snapshots** (only internal, which are slow to
create). The faster, simpler pattern for a resettable cage is the **backing-file overlay**:
keep an immutable `golden.qcow2`, create a thin per-trial overlay
`qemu-img create -f qcow2 -b golden.qcow2 -F qcow2 trial.qcow2`, boot from the overlay, and
**reset = delete the overlay and recreate it** (sub-second; only the overlay's dirty blocks are
discarded). Golden image never changes → provable clean resets (checksum the golden).

**Recommendation:** (a) run QEMU **unprivileged** via the libvirt *session* (qemu:///session)
or a dedicated low-priv user, keep **AppArmor sVirt enforcing**, add cgroup mem/cpu caps and
an **isolated NAT or no NIC**; (b) implement reset as **overlay discard-and-recreate**, not
libvirt snapshot-revert; checksum `golden.qcow2` and record it in the manifest. Update the
design note in `docs/ARCHITECTURE.md`/`constraint-cage.md` accordingly (source docs stay
frozen; the corrected mechanism lives here and in the VM scripts). Residual `[OPEN]`: measure
actual reset wall-time; target < 2 s.

---

## Net effect on the plan

- **Two risks downgraded to near-zero** by built-ins: JSON reliability (grammar) and vsock.
- **Two risks mitigated with a documented one-liner**: RAPL (udev rule), P-core pinning (taskset).
- **One design refinement**: reset via qcow2 overlay discard, not external-snapshot revert.
- **One genuine unknown remains**: memory channels — resolve with `dmidecode` before Phase 1
  benchmarking; it's the gate on model-size choice.

## Sources

- RAPL root-only / udev rule: node_exporter #2090, codecarbon #244/#232, pyJoules #13, powerjoular #1, Arch BBS 307345 — https://github.com/prometheus/node_exporter/issues/2090 · https://bbs.archlinux.org/viewtopic.php?id=307345
- llama.cpp P-core vs E-core (~3×): ggml-org/llama.cpp Discussion #572 — https://github.com/ggml-org/llama.cpp/discussions/572 ; CPU-only deployment study — https://ceur-ws.org/Vol-4164/paper11.pdf
- Dell Inspiron 16 5640 memory (2 SO-DIMM slots, not soldered): Dell Owner's Manual — https://www.dell.com/support/manuals/en-us/inspiron-16-5640-laptop/inspiron-16-5640-owners-manual/memory
- vsock in libvirt/QEMU (CID 2 = host, guest CID>2): QEMU wiki Features/VirtioVsock — https://wiki.qemu.org/Features/VirtioVsock ; KubeVirt vsock guide — https://kubevirt.io/user-guide/compute/vsock/
- QEMU hardening (seccomp/sVirt/cgroups/namespaces): libvirt qemu driver — https://libvirt.org/drvqemu.html ; QEMU security docs — https://qemu.readthedocs.io/en/v9.2.4/system/security.html ; OpenStack security guide — https://docs.openstack.org/security-guide/compute/hardening-the-virtualization-layers.html
- GBNF grammar-constrained JSON/tool-calls on 3B: llama.cpp grammars README — https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md ; on-device 3B evidence — https://mvpfactory.io/blog/structured-output-and-tool-calling-with-on-device-llms-on-android-grammar
- qcow2 overlay reset / external-snapshot revert limitation: fabianlee external snapshots — https://fabianlee.org/2021/01/10/kvm-creating-and-reverting-libvirt-external-snapshots/ ; qemu-img backing files — https://dustymabe.com/2015/01/11/qemu-img-backing-files-a-poor-mans-snapshotrollback/
