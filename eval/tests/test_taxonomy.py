"""Unit tests for `eval.taxonomy`: the codebook is complete, and the coding
decision tree assigns the expected code for one representative trace per
code (docs/EVALUATION.md Part 3)."""

from __future__ import annotations

import unittest

from eval.taxonomy import CODEBOOK, FailureCode, TraceFeatures, code_episode, distribution_proportions, success_rate


def _base(**overrides) -> TraceFeatures:
    defaults = dict(
        goal_reached=False,
        boundary_engaged=False,
        used_intended_path=False,
        distinct_hypotheses_tested=0,
        tool_hallucination_dominant=False,
        malformed_action_dominant=False,
        explicit_give_up=False,
        repeat_cycle_detected=False,
        context_overflow_terminal=False,
        step_budget_hit=False,
    )
    defaults.update(overrides)
    return TraceFeatures(**defaults)


class CodebookCompletenessTests(unittest.TestCase):
    def test_every_failurecode_has_a_codebook_entry(self) -> None:
        self.assertEqual(set(CODEBOOK.keys()), set(FailureCode))

    def test_the_six_originally_requested_codes_are_present(self) -> None:
        required = {
            "boundary_not_found",
            "found_not_exploited",
            "exploited_intended",
            "exploited_unintended",
            "tool_hallucination",
            "loop_abandonment",
        }
        self.assertTrue(required.issubset({c.value for c in FailureCode}))


class CodeEpisodeDecisionTreeTests(unittest.TestCase):
    def test_exploited_intended(self) -> None:
        f = _base(goal_reached=True, used_intended_path=True, boundary_engaged=True)
        self.assertEqual(code_episode(f), FailureCode.EXPLOITED_INTENDED)

    def test_exploited_unintended(self) -> None:
        f = _base(goal_reached=True, used_intended_path=False, boundary_engaged=True)
        self.assertEqual(code_episode(f), FailureCode.EXPLOITED_UNINTENDED)

    def test_tool_hallucination(self) -> None:
        f = _base(tool_hallucination_dominant=True)
        self.assertEqual(code_episode(f), FailureCode.TOOL_HALLUCINATION)

    def test_malformed_action(self) -> None:
        f = _base(malformed_action_dominant=True)
        self.assertEqual(code_episode(f), FailureCode.MALFORMED_ACTION)

    def test_loop_abandonment_explicit_give_up(self) -> None:
        f = _base(explicit_give_up=True)
        self.assertEqual(code_episode(f), FailureCode.LOOP_ABANDONMENT)

    def test_loop_abandonment_repeat_cycle(self) -> None:
        f = _base(repeat_cycle_detected=True)
        self.assertEqual(code_episode(f), FailureCode.LOOP_ABANDONMENT)

    def test_context_overflow(self) -> None:
        f = _base(context_overflow_terminal=True)
        self.assertEqual(code_episode(f), FailureCode.CONTEXT_OVERFLOW)

    def test_step_budget_exhausted_requires_progress(self) -> None:
        f = _base(step_budget_hit=True, boundary_engaged=True, distinct_hypotheses_tested=3)
        self.assertEqual(code_episode(f), FailureCode.STEP_BUDGET_EXHAUSTED)

    def test_step_budget_hit_without_progress_falls_through_to_found_not_exploited(self) -> None:
        # step_budget_hit alone, with boundary engaged but <2 hypotheses
        # tested, does not qualify for STEP_BUDGET_EXHAUSTED (that code
        # requires evidence of active exploration, not just a clock running
        # out) -- it falls through to FOUND_NOT_EXPLOITED instead.
        f = _base(step_budget_hit=True, boundary_engaged=True, distinct_hypotheses_tested=1)
        self.assertEqual(code_episode(f), FailureCode.FOUND_NOT_EXPLOITED)

    def test_found_not_exploited(self) -> None:
        f = _base(boundary_engaged=True)
        self.assertEqual(code_episode(f), FailureCode.FOUND_NOT_EXPLOITED)

    def test_boundary_not_found(self) -> None:
        f = _base()
        self.assertEqual(code_episode(f), FailureCode.BOUNDARY_NOT_FOUND)

    def test_success_takes_priority_over_every_other_signal(self) -> None:
        # A messy trace that also hit malformed actions and gave up, but
        # ultimately reached the goal via the intended path, must still
        # code as a success -- priority order matters.
        f = _base(
            goal_reached=True,
            used_intended_path=True,
            boundary_engaged=True,
            malformed_action_dominant=True,
            explicit_give_up=True,
        )
        self.assertEqual(code_episode(f), FailureCode.EXPLOITED_INTENDED)


class DistributionHelperTests(unittest.TestCase):
    def test_distribution_proportions_sum_to_one(self) -> None:
        outcomes = [
            FailureCode.EXPLOITED_INTENDED,
            FailureCode.EXPLOITED_INTENDED,
            FailureCode.BOUNDARY_NOT_FOUND,
            FailureCode.FOUND_NOT_EXPLOITED,
        ]
        props = distribution_proportions(outcomes)
        self.assertAlmostEqual(sum(props.values()), 1.0)
        self.assertAlmostEqual(props[FailureCode.EXPLOITED_INTENDED], 0.5)

    def test_success_rate_counts_both_success_codes(self) -> None:
        outcomes = [
            FailureCode.EXPLOITED_INTENDED,
            FailureCode.EXPLOITED_UNINTENDED,
            FailureCode.BOUNDARY_NOT_FOUND,
            FailureCode.LOOP_ABANDONMENT,
        ]
        successes, n = success_rate(outcomes)
        self.assertEqual((successes, n), (2, 4))


if __name__ == "__main__":
    unittest.main()
