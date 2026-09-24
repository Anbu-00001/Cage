# observability/ — eBPF instruments (the polyglot stack's eBPF/C leg)

Near-zero-overhead, in-kernel probes for the systems questions this project
actually cares about. eBPF is the "genuine systems flex" the design docs call
for (constraint-cage.md ★ Tech stack): instead of a userspace sampling loop
that steals cycles from the thing it measures, these attach to kernel
tracepoints and aggregate in-kernel.

| Script | Answers | Ties to |
|---|---|---|
| [`runqlat.bt`](runqlat.bt) | Does the E-core guest steal on-CPU time from P-core inference? (run-queue latency per process) | "2 fast cores, not twelve" — Part 1 |
| [`syscall_footprint.bt`](syscall_footprint.bt) | What do the host pieces (orchestrator/llama-server/QEMU) *do* per step? (syscall counts) | cost-of-a-step, complements RAPL telemetry |
| [`blockio.bt`](blockio.bt) | Overlay-reset cost & swap thrash (block-I/O latency) | reset < 2 s (DE-RISKING §6), memory-pressure confounder (EVALUATION §5) |

## Scope & safety

- **Host-side only.** These trace HOST processes (the orchestrator, `llama-server`,
  `qemu-system`). They do **not** see the guest's internal syscalls — those are
  behind the VM boundary, which is deliberate: the host is sacred (CLAUDE.md
  safety scope). To trace inside the cage, run bpftrace *in the guest*.
- **Read-only.** They observe; they never modify kernel state or the guest.

## Running them

Not installed or run by this repo's tests — eBPF needs **root** and the
**bpftrace** toolchain, neither of which the test suite assumes. To use:

```bash
sudo apt install bpftrace            # Ubuntu 24.04: one package, ships the runtime
sudo bpftrace observability/runqlat.bt
# Ctrl-C to print the aggregated histograms.
```

These are ready-to-run instruments written to bpftrace's standard idioms; they
are marked "not executed in this repo's tests" in each header because verifying
them requires a live workload + root, which is Phase 1/2 on the target host. A
`bcc`/`libbpf`-based C version of `runqlat` would be the next step if a compiled,
distributable binary is wanted over a script — the tracepoints used are the
same.

## How this feeds the eval

Each script prints per-interval aggregates you can capture alongside a trial's
`EpisodeRecord`: run-queue latency and block-I/O tails become extra confound
evidence (was this trial scheduler- or swap-perturbed?), and the syscall
footprint is a cheap cross-check on the step count. None of it is on the
inference hot path.
