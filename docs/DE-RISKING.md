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

## 1. Memory channels — single vs dual (THE bandwidth multiplier) `[OPEN]`

**Risk:** decode tok/s ≈ bandwidth ÷ model size. Single-channel ~halves it → every tok/s
`[EST]` in the design docs could be 2× optimistic.

**Findings `[VERIFIED-2026-09]`:** the Dell Inspiron 16 5640 has **two SO-DIMM slots and no
soldered RAM** — memory is upgradeable DDR5-5200/5600. Stock units commonly ship a **single
8 GB module**. Therefore a 16 GB unit is *either* **1×16 GB (single-channel)** *or*
**2×8 GB (dual-channel)** — the box's tok/s ceiling is decided by which one this unit has.

**Recommendation:** run `sudo dmidecode -t memory` **first**, before any benchmarking. If it
reports one populated slot → **single-channel; halve every tok/s estimate** and bias to
1B–3B models. If two matched modules → dual-channel, 3B–4B is comfortable. If it's 1×16 GB,
a **~₹2–4k second 8 GB module (2×8) is the single cheapest performance upgrade** in the whole
project and should be recommended in the write-up. **Prediction `ffe5dd` stays open until
`dmidecode` is run on this exact unit.**

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

## 4. P-core / E-core thread pinning `[VERIFIED-2026-09]`

**Risk:** naively using all 12 threads on the hybrid 150U can *reduce* tok/s via cross-cluster
scheduling and cache contention.

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
