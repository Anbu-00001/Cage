"""Smoke test for `eval.runner.BatchRunner` using fully in-memory fakes for
the `AgentController` / `EnvironmentController` / `TelemetryCollector`
`Protocol`s -- proves the trial-matrix and confound-metadata wiring works
without any real VM/model/telemetry infrastructure attached."""

from __future__ import annotations

import unittest

from eval.runner import BatchRunner, TrialSpec, trials_for_boundary_class
from eval.schema import (
    Condition,
    EpisodeRecord,
    InferenceBackendConfig,
    MemoryTelemetry,
    ProbeVariant,
    ThermalTelemetry,
)
from eval.taxonomy import FailureCode


def _backend() -> InferenceBackendConfig:
    return InferenceBackendConfig(
        engine="llama.cpp", engine_commit="deadbeef", model_id="test-3b",
        quantization="Q4_K_M", ctx_length=4096, n_threads=4, pinned_cores=(0, 1),
        temperature=0.0, top_p=1.0, top_k=1, repeat_penalty=1.1, sampling_seed=0,
    )


class FakeEnv:
    def revert_to_golden(self) -> str:
        return "golden-checksum"

    def instantiate_boundary(self, boundary_class: str, seed: int) -> str:
        return f"{boundary_class}-{seed}"

    def checksum(self) -> str:
        return "golden-checksum"


class FakeTelemetry:
    def start(self) -> None:
        pass

    def stop(self):
        thermal = ThermalTelemetry(
            pkg_temp_c_max=60.0, pkg_watt_avg=12.0, sustained_p_core_mhz_avg=3000.0,
            throttle_events=0, equilibrated_before_trial=True,
        )
        memory = MemoryTelemetry(
            peak_rss_mb=2048.0, swap_used_mb=0.0, psi_some_avg10=0.0,
            psi_full_avg10=0.0, caches_dropped_before_trial=True,
        )
        return thermal, memory


class FakeAgent:
    def run_episode(self, spec: TrialSpec, env: FakeEnv) -> EpisodeRecord:
        solved = spec.seed % 2 == 0
        placeholder_thermal = ThermalTelemetry(0.0, 0.0, 0.0, 0, False)
        placeholder_memory = MemoryTelemetry(0.0, 0.0, 0.0, 0.0, False)
        return EpisodeRecord(
            episode_id=f"ep-{spec.boundary_class}-{spec.seed}",
            timestamp_utc="2026-09-24T00:00:00Z",
            seed=spec.seed,
            boundary_class=spec.boundary_class,
            boundary_instance_id=f"{spec.boundary_class}-{spec.seed}",
            probe_variant=ProbeVariant.SEEN,
            condition=spec.condition,
            backend=spec.backend,
            outcome=FailureCode.EXPLOITED_INTENDED if solved else FailureCode.BOUNDARY_NOT_FOUND,
            solved=solved,
            gave_up=False,
            steps_taken=5,
            optimal_steps=3,
            tokens_prompt=100,
            tokens_completion=50,
            wall_clock_seconds=10.0,
            tok_per_sec_decode=15.0,
            ttft_seconds=0.5,
            energy_joules=100.0,
            thermal=placeholder_thermal,
            memory=placeholder_memory,
            vm_snapshot_checksum_pre="golden-checksum",
            vm_snapshot_checksum_post_revert="golden-checksum",
            trace_ref=f"traces/{spec.boundary_class}-{spec.seed}.jsonl",
        )


def _runner(boundary_classes: tuple[str, ...], seeds: tuple[int, ...]) -> BatchRunner:
    return BatchRunner(
        boundary_classes=boundary_classes,
        conditions=(Condition.TREATMENT_FULL,),
        seeds=seeds,
        backend=_backend(),
        agent=FakeAgent(),
        env=FakeEnv(),
        telemetry=FakeTelemetry(),
    )


class BatchRunnerPlanTests(unittest.TestCase):
    def test_plan_uses_tiered_trial_counts(self) -> None:
        runner = _runner(("L1", "L6"), tuple(range(40)))
        plan = runner.plan()
        l1_trials = [t for t in plan if t.boundary_class == "L1"]
        l6_trials = [t for t in plan if t.boundary_class == "L6"]
        self.assertEqual(len(l1_trials), trials_for_boundary_class("L1"))
        self.assertEqual(len(l6_trials), trials_for_boundary_class("L6"))
        self.assertEqual(trials_for_boundary_class("L1"), 12)
        self.assertEqual(trials_for_boundary_class("L6"), 32)

    def test_plan_raises_on_untiered_boundary_class(self) -> None:
        runner = _runner(("L99",), tuple(range(40)))
        with self.assertRaises(ValueError):
            runner.plan()

    def test_plan_raises_when_not_enough_seeds_supplied(self) -> None:
        runner = _runner(("L6",), tuple(range(5)))  # L6 needs 32
        with self.assertRaises(ValueError):
            runner.plan()


class BatchRunnerRunTrialTests(unittest.TestCase):
    def test_run_trial_populates_confound_metadata_and_authoritative_telemetry(self) -> None:
        runner = _runner(("L1",), (2, 3))
        spec = TrialSpec("L1", Condition.TREATMENT_FULL, 2, _backend())
        record = runner.run_trial(spec)
        self.assertTrue(record.solved)  # seed=2 is even in FakeAgent
        self.assertEqual(record.extra["golden_checksum"], "golden-checksum")
        self.assertIn("probe_variant_computed", record.extra)
        # The harness's TelemetryCollector overwrites the agent's placeholder.
        self.assertEqual(record.thermal.pkg_temp_c_max, 60.0)
        self.assertTrue(record.thermal.equilibrated_before_trial)

    def test_run_batch_runs_every_planned_trial(self) -> None:
        runner = _runner(("L1",), tuple(range(12)))
        records = runner.run_batch()
        self.assertEqual(len(records), trials_for_boundary_class("L1"))


if __name__ == "__main__":
    unittest.main()
