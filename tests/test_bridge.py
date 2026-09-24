"""End-to-end integration-spine test: the REAL eval BatchRunner drives the
REAL agent loop over REAL generated challenges, no model and no VM, and the
records flow into the REAL stats/report layer.

This is the test that proves the four lanes actually connect: agent loop,
challenges, orchestrator, and eval. Outcomes are fixture-driven (the smoke
solver), so a 100% success rate here is expected and is NOT a capability
result -- it's a plumbing proof (see eval/bridge.py docstring).
"""

from __future__ import annotations

import json

from eval.bridge import (
    GeneratedEnvController,
    LoopAgentController,
    NullTelemetryCollector,
    default_backend,
    episode_result_to_record,
    map_outcome,
    smoke_episode_builder,
)
from eval.report import render_table, summarize_batch
from eval.runner import BatchRunner, TrialSpec
from eval.schema import Condition, ProbeVariant
from eval.taxonomy import FailureCode
from src.agent.models import EpisodeOutcome, EpisodeResult, Goal


def _result(outcome: EpisodeOutcome, steps: int = 3) -> EpisodeResult:
    return EpisodeResult(goal=Goal(id="g", description="d", level=2), outcome=outcome,
                         steps_taken=steps, transcript=[])


def test_map_outcome_covers_every_terminal_outcome():
    # Every EpisodeOutcome must map to a taxonomy code (no KeyError in prod).
    for outcome in EpisodeOutcome:
        code, solved, gave_up = map_outcome(_result(outcome))
        assert isinstance(code, FailureCode)
        assert solved == (outcome == EpisodeOutcome.GOAL_REACHED)
        assert gave_up == (outcome == EpisodeOutcome.GAVE_UP)


def test_record_mapping_roundtrips_to_json():
    spec = TrialSpec(boundary_class="L2", condition=Condition.TREATMENT_FULL, seed=0,
                     backend=default_backend())
    rec = episode_result_to_record(
        _result(EpisodeOutcome.GOAL_REACHED, steps=5), spec,
        boundary_instance_id="L2-x:0", probe_variant=ProbeVariant.SEEN, optimal_steps=4,
    )
    assert rec.solved is True
    assert rec.outcome == FailureCode.EXPLOITED_INTENDED
    assert rec.steps_taken == 5
    # honest zeros where the v0 loop doesn't measure yet
    assert rec.energy_joules is None
    assert json.loads(rec.to_json())["boundary_instance_id"] == "L2-x:0"


def test_generated_env_is_real_and_seed_distinct():
    env = GeneratedEnvController()
    id42 = env.instantiate_boundary("L6", 42)
    sum42 = env.checksum()
    id7 = env.instantiate_boundary("L6", 7)
    sum7 = env.checksum()
    assert id42 != id7 and sum42 != sum7          # seed actually drives the instance
    assert env.revert_to_golden().startswith("golden")
    probe_env = GeneratedEnvController(probe=True)
    assert probe_env.instantiate_boundary("L6", 42).endswith("/probe")
    assert probe_env.probe_variant is ProbeVariant.HELD_OUT


def test_full_batch_runs_and_summarizes(tmp_path):
    runner = BatchRunner(
        boundary_classes=("L2",),                       # easy tier -> 12 trials
        conditions=(Condition.TREATMENT_FULL,),
        seeds=tuple(range(12)),
        backend=default_backend(),
        agent=LoopAgentController(smoke_episode_builder(str(tmp_path))),
        env=GeneratedEnvController(),
        telemetry=NullTelemetryCollector(),
    )
    records = runner.run_batch()
    assert len(records) == 12                            # matches the L2 tier count
    assert all(r.solved for r in records)               # smoke solver always solves
    assert all(r.boundary_instance_id.startswith("L") for r in records)
    # harness stamped its authoritative telemetry + checksums onto each record
    assert all("post_trial_checksum" in r.extra for r in records)

    summaries = summarize_batch(records)
    assert len(summaries) >= 1
    table = render_table(summaries)
    assert isinstance(table, str) and len(table) > 0
