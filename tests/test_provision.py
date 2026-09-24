"""Phase 3 tests: challenge instances render into clean guest provisioning,
and scoring runs over the channel by exit status.

These don't stand up a real VM (that's Phase 2 on the target host); they test
the rendering + channel-scoring logic that will drive it, against every
registered spec and a mock channel.
"""

from __future__ import annotations

import pytest

from challenges.provision import build_provisioning_script, run_scripted_solver, run_success_check
from challenges.specs import REGISTRY
from src.agent.models import ToolResult
from src.orchestrator.channel import LocalMockChannel

ALL_SPEC_IDS = [g.spec.spec_id for g in REGISTRY.all()]


@pytest.mark.parametrize("spec_id", ALL_SPEC_IDS)
@pytest.mark.parametrize("probe", [False, True])
def test_provisioning_script_is_clean(spec_id, probe):
    inst = REGISTRY.by_id(spec_id).generate(seed=1234, probe=probe)
    script = build_provisioning_script(inst)
    assert script.startswith("#!/bin/sh")
    assert "@@" not in script  # no unresolved template tokens reach the guest
    assert "set -eu" in script
    assert len(script.strip().splitlines()) > 3  # actually does something


@pytest.mark.parametrize("spec_id", ALL_SPEC_IDS)
def test_success_check_reads_exit_status(spec_id):
    inst = REGISTRY.by_id(spec_id).generate(seed=7)
    # Channel where the success check "passes" (exit 0).
    ok_channel = LocalMockChannel(
        responses={inst.success_check: ToolResult(ok=True, exit_code=0, stdout="")}
    )
    assert run_success_check(inst, ok_channel) is True
    # Default mock response is exit 127 -> not solved (nothing was set up).
    assert run_success_check(inst, LocalMockChannel()) is False


@pytest.mark.parametrize("spec_id", ALL_SPEC_IDS)
def test_scripted_solver_runs_every_step_then_checks(spec_id):
    inst = REGISTRY.by_id(spec_id).generate(seed=99)
    # A channel that succeeds for every intended step AND the success check.
    responses = {step: ToolResult(ok=True, exit_code=0) for step in inst.intended_solution}
    responses[inst.success_check] = ToolResult(ok=True, exit_code=0)
    run = run_scripted_solver(inst, LocalMockChannel(responses=responses))
    assert run.solved is True
    assert run.steps == len(inst.intended_solution)
    assert run.steps >= 1  # every level has at least one solve step
