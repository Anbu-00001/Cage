"""Unit tests for `eval.metrics` on a small synthetic batch of episodes."""

from __future__ import annotations

import unittest

from eval.metrics import (
    actions_to_solve_efficiency,
    give_up_rate,
    joules_per_solve,
    solves_per_watt_hour,
    success_rate_with_ci,
    tokens_per_solve,
)
from eval.schema import Condition, EpisodeRecord, InferenceBackendConfig, MemoryTelemetry, ProbeVariant, ThermalTelemetry
from eval.taxonomy import FailureCode


def _backend() -> InferenceBackendConfig:
    return InferenceBackendConfig(
        engine="llama.cpp", engine_commit="deadbeef", model_id="test-3b",
        quantization="Q4_K_M", ctx_length=4096, n_threads=4, pinned_cores=(0, 1),
        temperature=0.0, top_p=1.0, top_k=1, repeat_penalty=1.1, sampling_seed=0,
    )


def _episode(*, solved: bool, steps: int, optimal: int | None, tokens: int, joules: float | None, gave_up: bool = False) -> EpisodeRecord:
    return EpisodeRecord(
        episode_id=f"ep-{steps}-{solved}",
        timestamp_utc="2026-09-24T00:00:00Z",
        seed=1,
        boundary_class="L6",
        boundary_instance_id="inst",
        probe_variant=ProbeVariant.SEEN,
        condition=Condition.TREATMENT_FULL,
        backend=_backend(),
        outcome=FailureCode.EXPLOITED_INTENDED if solved else FailureCode.BOUNDARY_NOT_FOUND,
        solved=solved,
        gave_up=gave_up,
        steps_taken=steps,
        optimal_steps=optimal,
        tokens_prompt=tokens // 2,
        tokens_completion=tokens - tokens // 2,
        wall_clock_seconds=10.0,
        tok_per_sec_decode=15.0,
        ttft_seconds=0.5,
        energy_joules=joules,
        thermal=ThermalTelemetry(60.0, 12.0, 3000.0, 0, True),
        memory=MemoryTelemetry(2048.0, 0.0, 0.0, 0.0, True),
        vm_snapshot_checksum_pre="golden",
        vm_snapshot_checksum_post_revert="golden",
        trace_ref="traces/x.jsonl",
    )


class MetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        # 4 episodes: 2 solved (100 and 200 tokens, 50 and 150 joules), 2 not solved.
        self.episodes = [
            _episode(solved=True, steps=4, optimal=4, tokens=100, joules=50.0),
            _episode(solved=True, steps=8, optimal=4, tokens=200, joules=150.0),
            _episode(solved=False, steps=20, optimal=None, tokens=300, joules=200.0, gave_up=True),
            _episode(solved=False, steps=20, optimal=None, tokens=300, joules=200.0),
        ]

    def test_success_rate_with_ci(self) -> None:
        result = success_rate_with_ci(self.episodes)
        self.assertEqual((result.successes, result.n), (2, 4))
        self.assertAlmostEqual(result.rate, 0.5)
        self.assertLessEqual(result.wilson_lo, result.rate)
        self.assertGreaterEqual(result.wilson_hi, result.rate)

    def test_give_up_rate(self) -> None:
        self.assertAlmostEqual(give_up_rate(self.episodes), 0.25)

    def test_tokens_per_solve_is_total_over_solves(self) -> None:
        # total tokens = 100+200+300+300 = 900, solves = 2 -> 450 tokens/solve
        self.assertAlmostEqual(tokens_per_solve(self.episodes), 450.0)

    def test_tokens_per_solve_none_when_no_solves(self) -> None:
        unsolved = [e for e in self.episodes if not e.solved]
        self.assertIsNone(tokens_per_solve(unsolved))

    def test_joules_per_solve_and_solves_per_watt_hour(self) -> None:
        # total joules across all 4 (all metered) = 50+150+200+200 = 600, solves=2
        self.assertAlmostEqual(joules_per_solve(self.episodes), 300.0)
        # 600 J = 600/3600 Wh = 1/6 Wh; solves/Wh = 2 / (1/6) = 12
        self.assertAlmostEqual(solves_per_watt_hour(self.episodes), 12.0)

    def test_actions_to_solve_efficiency_uses_only_solved_with_optimal(self) -> None:
        result = actions_to_solve_efficiency(self.episodes)
        # ratios: 4/4=1.0, 8/4=2.0 -> median 1.5
        self.assertEqual(result.n, 2)
        self.assertAlmostEqual(result.median_ratio, 1.5)


if __name__ == "__main__":
    unittest.main()
