"""Unit tests for `eval.statistics`, on synthetic data with hand-derivable
expected values (docs/EVALUATION.md Appendix A walks the same numbers)."""

from __future__ import annotations

import random
import unittest

from eval.statistics import (
    bayesian_credible_interval,
    bootstrap_ci,
    cohens_kappa,
    design_effect,
    effective_sample_size,
    icc_one_way,
    required_n_for_margin,
    wilson_ci,
)


class WilsonCiTests(unittest.TestCase):
    def test_matches_textbook_value_n20_x10(self) -> None:
        # Standard textbook Wilson 95% CI for x=10, n=20 (p_hat=0.5) is
        # (0.299, 0.701); verify to 3 decimal places.
        lo, hi = wilson_ci(10, 20, confidence=0.95)
        self.assertAlmostEqual(lo, 0.2993, places=3)
        self.assertAlmostEqual(hi, 0.7007, places=3)

    def test_symmetric_around_p_hat_when_p_hat_is_half(self) -> None:
        lo, hi = wilson_ci(50, 100)
        center = (lo + hi) / 2
        self.assertAlmostEqual(center, 0.5, places=3)

    def test_all_successes_does_not_reach_exactly_one(self) -> None:
        # Wilson correctly refuses to claim certainty from a small perfect
        # record -- the whole reason it beats Wald here (Wald gives [1, 1]).
        lo, hi = wilson_ci(10, 10)
        self.assertGreater(lo, 0.5)
        self.assertLess(lo, 1.0)
        self.assertLessEqual(hi, 1.0)

    def test_interval_narrows_with_more_data_at_same_rate(self) -> None:
        lo_small, hi_small = wilson_ci(15, 30)
        lo_big, hi_big = wilson_ci(150, 300)
        self.assertGreater(hi_small - lo_small, hi_big - lo_big)

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            wilson_ci(5, 0)
        with self.assertRaises(ValueError):
            wilson_ci(11, 10)


class BayesianCredibleIntervalTests(unittest.TestCase):
    def test_posterior_mean_near_wilson_center_for_balanced_data(self) -> None:
        rng = random.Random(1234)
        mean, lo, hi = bayesian_credible_interval(10, 10, rng=rng)
        # Jeffreys posterior mean for x=10, n=20 is (10.5)/(21) exactly.
        self.assertAlmostEqual(mean, 10.5 / 21, places=6)
        self.assertLess(lo, mean)
        self.assertLess(mean, hi)

    def test_more_data_narrows_the_credible_interval(self) -> None:
        rng = random.Random(7)
        _, lo_small, hi_small = bayesian_credible_interval(10, 10, rng=rng)
        _, lo_big, hi_big = bayesian_credible_interval(100, 100, rng=rng)
        self.assertGreater(hi_small - lo_small, hi_big - lo_big)


class BootstrapCiTests(unittest.TestCase):
    def test_ci_contains_true_mean_of_constant_data(self) -> None:
        data = [1.0] * 20
        rng = random.Random(42)
        lo, hi = bootstrap_ci(data, rng=rng)
        self.assertAlmostEqual(lo, 1.0)
        self.assertAlmostEqual(hi, 1.0)

    def test_more_data_narrows_the_bootstrap_ci(self) -> None:
        rng = random.Random(99)
        small = [0.0, 1.0] * 5  # n=10, mean 0.5, high variance
        big = [0.0, 1.0] * 200  # n=400, same mean, much less sampling noise
        lo_s, hi_s = bootstrap_ci(small, rng=rng)
        lo_b, hi_b = bootstrap_ci(big, rng=rng)
        self.assertGreater(hi_s - lo_s, hi_b - lo_b)


class IccOneWayTests(unittest.TestCase):
    def test_identical_groups_give_negative_icc(self) -> None:
        # Three groups with exactly the same values: zero between-group
        # variance, nonzero within-group variance -> ICC(1) = -1/(k-1)
        # exactly, for balanced group size k.
        groups = {
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "b": [1.0, 2.0, 3.0, 4.0, 5.0],
            "c": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
        result = icc_one_way(groups)
        self.assertAlmostEqual(result.icc, -0.25, places=6)

    def test_zero_within_group_variance_gives_icc_one(self) -> None:
        # Three groups, each internally constant but with different levels:
        # zero within-group variance -> ICC(1) = 1.0 exactly.
        groups = {"a": [1.0, 1.0, 1.0], "b": [5.0, 5.0, 5.0], "c": [9.0, 9.0, 9.0]}
        result = icc_one_way(groups)
        self.assertAlmostEqual(result.icc, 1.0, places=6)

    def test_requires_at_least_two_groups(self) -> None:
        with self.assertRaises(ValueError):
            icc_one_way({"a": [1.0, 2.0, 3.0]})

    def test_design_effect_and_effective_n(self) -> None:
        # No clustering (cluster_size=1) never inflates variance.
        self.assertEqual(design_effect(icc=0.5, cluster_size=1), 1.0)
        # Higher ICC + bigger clusters shrink the effective N.
        deff = design_effect(icc=0.5, cluster_size=4)
        self.assertEqual(deff, 1 + 3 * 0.5)
        self.assertAlmostEqual(effective_sample_size(100, icc=0.5, cluster_size=4), 100 / deff)


class RequiredNTests(unittest.TestCase):
    def test_matches_hand_derived_value(self) -> None:
        # n = z^2 * p(1-p) / margin^2 with z=1.959964, p=0.5, margin=0.15
        # -> 42.68 -> ceil 43 (docs/EVALUATION.md Part 2.1 worked example).
        self.assertEqual(required_n_for_margin(margin=0.15, p=0.5), 43)

    def test_tighter_p_guess_needs_fewer_trials(self) -> None:
        n_worst_case = required_n_for_margin(margin=0.15, p=0.5)
        n_near_ceiling = required_n_for_margin(margin=0.15, p=0.9)
        self.assertLess(n_near_ceiling, n_worst_case)


class CohensKappaTests(unittest.TestCase):
    def test_perfect_agreement_is_one(self) -> None:
        labels = ["a", "b", "a", "b", "a"]
        self.assertAlmostEqual(cohens_kappa(labels, labels), 1.0)

    def test_matches_hand_derived_partial_agreement(self) -> None:
        rater_a = ["yes", "yes", "no", "no"]
        rater_b = ["yes", "no", "no", "no"]
        # observed = 3/4 = 0.75; chance = 0.5*0.25 + 0.5*0.75 = 0.5
        # kappa = (0.75 - 0.5) / (1 - 0.5) = 0.5
        self.assertAlmostEqual(cohens_kappa(rater_a, rater_b), 0.5, places=6)

    def test_rejects_mismatched_lengths(self) -> None:
        with self.assertRaises(ValueError):
            cohens_kappa(["a"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
