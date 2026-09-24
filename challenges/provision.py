"""Phase 3 glue: turn a generated ``ChallengeInstance`` into something that
actually stands up inside the guest, and score it honestly.

Two responsibilities, deliberately separated by *privilege*:

1. **Provisioning (root, build-time).** ``build_provisioning_script`` assembles
   the instance's resolved shell fragments into one script the VM builder runs
   **as root against the overlay before the trial boots** (adduser, chmod 4755,
   nft, setcap, ... all need root). This is NOT run over the agent's channel:
   the agent later acts as the *unprivileged* cage user, which is the whole
   point — the engineered boundary is the gap between that user and root.

2. **Scoring (over the logged channel).** ``run_success_check`` /
   ``run_scripted_solver`` execute in-guest over the ``ActionChannel`` and read
   the verdict from an *exit status*, never from the agent's own claim of
   success (constraint-cage.md Part 8/18). The check was generated host-side
   from a (spec_id, seed) the agent never saw, so it can't be gamed by echoing
   a guessed string.

The scripted solver exists to calibrate difficulty (Phase 3 stop condition:
"human + scripted solver both solve") and to bound F-class action-efficiency
scoring (v1 Part 9).
"""

from __future__ import annotations

from dataclasses import dataclass

from challenges.schema import ChallengeInstance
from src.agent.models import ToolResult


def assert_fully_resolved(instance: ChallengeInstance) -> None:
    """Guard against shipping a half-templated instance into a guest: no
    ``@@token@@`` may survive into any script the builder or scorer runs."""
    blobs = [*instance.provisioning_script, instance.success_check, *instance.intended_solution]
    for blob in blobs:
        if "@@" in blob:
            raise ValueError(f"unresolved @@token@@ in instance {instance.spec_id} seed={instance.seed}: {blob!r}")


def build_provisioning_script(instance: ChallengeInstance) -> str:
    """The root, build-time script that installs the engineered boundary into
    the guest overlay. Idempotency is the spec author's concern; we only
    guarantee ordering and fail-fast (`set -eu`)."""
    assert_fully_resolved(instance)
    header = (
        "#!/bin/sh\n"
        f"# AUTO-GENERATED for spec={instance.spec_id} seed={instance.seed} "
        f"probe={instance.is_probe}\n"
        "# Run as ROOT against the trial overlay before boot. Never run on the host.\n"
        "set -eu\n\n"
    )
    body = "\n\n".join(frag.strip() for frag in instance.provisioning_script)
    return header + body + "\n"


def run_success_check(instance: ChallengeInstance, channel, *, timeout_s: float = 15.0) -> bool:
    """Execute the resolved success predicate in-guest; exit 0 == solved."""
    result: ToolResult = channel.execute(instance.success_check, timeout_s=timeout_s)
    return result.exit_code == 0


@dataclass
class SolverRun:
    solved: bool
    step_results: list[ToolResult]

    @property
    def steps(self) -> int:
        return len(self.step_results)


def run_scripted_solver(instance: ChallengeInstance, channel, *, timeout_s: float = 15.0) -> SolverRun:
    """Run the intended solution steps in order over the channel, then the
    success check. Used to prove a freshly-generated instance is actually
    solvable (calibration), and to record the optimal actions-to-solve that
    the agent's efficiency is measured against."""
    assert_fully_resolved(instance)
    results = [channel.execute(step, timeout_s=timeout_s) for step in instance.intended_solution]
    solved = run_success_check(instance, channel, timeout_s=timeout_s)
    return SolverRun(solved=solved, step_results=results)
