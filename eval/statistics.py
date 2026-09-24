"""Statistics primitives for the Constraint Cage evaluation harness.

Implements, deliberately with **zero third-party dependencies** (stdlib
`statistics`, `random`, `math` only) so the harness runs on a bare Python
3.11+ install with nothing to `pip install` — consistent with the project's
laptop-honest, low-dependency-footprint ethos (docs/EVALUATION.md Part 0).

Covers:
  - `wilson_ci` — Wilson score interval for a binomial proportion (the
    primary CI method; docs/EVALUATION.md Part 2.2).
  - `bayesian_credible_interval` — a Beta-Binomial posterior credible
    interval (Jeffreys prior by default), the complementary interval method
    used to avoid a bare "Pass@k" point estimate.
  - `bootstrap_ci` — a generic percentile bootstrap for statistics that
    aren't a simple proportion.
  - `icc_one_way` — a one-way random-effects intraclass correlation, ICC(1),
    with the associated design-effect / effective-N correction
    (docs/EVALUATION.md Part 2.3).
  - `cohens_kappa` — inter-rater agreement for taxonomy coding
    (docs/EVALUATION.md Part 3.3).
  - `required_n_for_margin` — sample-size planning, the arithmetic behind
    the 8-16 / >=32 trial-count tiers (docs/EVALUATION.md Part 2.1).

See docs/EVALUATION.md Part 2 for the statistical design these implement,
and Appendix A for worked numeric examples this module's unit tests also
check against.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import NormalDist, fmean
from typing import Callable, Mapping, Sequence

__all__ = [
    "wilson_ci",
    "bayesian_credible_interval",
    "bootstrap_ci",
    "ICCResult",
    "icc_one_way",
    "design_effect",
    "effective_sample_size",
    "required_n_for_margin",
    "cohens_kappa",
]


def _z_for_confidence(confidence: float) -> float:
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    return NormalDist().inv_cdf(1 - (1 - confidence) / 2)


def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Preferred over the naive Wald interval (`p_hat +/- z*sqrt(p_hat(1-p_hat)/n)`)
    because Wald under-covers badly at small n or extreme p_hat — including
    the degenerate 0/n and n/n cases, where Wald collapses to a zero-width
    interval. That is exactly the regime this project's "easy tier" (n=8-16)
    and any near-ceiling/near-floor boundary class lives in.

    Args:
        successes: number of successful trials, 0 <= successes <= n.
        n: total number of trials, n >= 1.
        confidence: two-sided confidence level, e.g. 0.95.

    Returns:
        (lower, upper) bounds, clipped to [0, 1].
    """
    if n <= 0:
        raise ValueError("n must be >= 1")
    if not 0 <= successes <= n:
        raise ValueError("successes must be in [0, n]")
    z = _z_for_confidence(confidence)
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def bayesian_credible_interval(
    successes: int,
    failures: int,
    *,
    prior_alpha: float = 0.5,
    prior_beta: float = 0.5,
    confidence: float = 0.95,
    n_samples: int = 20_000,
    rng: random.Random | None = None,
) -> tuple[float, float, float]:
    """Beta-Binomial posterior credible interval for a success probability.

    Default prior is Jeffreys' Beta(0.5, 0.5) — an objective,
    weakly-informative prior for a binomial proportion, preferred (per
    docs/EVALUATION.md Part 2.2, which cites the "Don't Pass@k" critique of
    reporting a bare point-estimate pass rate) over a flat Beta(1,1) so the
    interval doesn't over-cover near p=0 or p=1, and preferred over a single
    Pass@k number because it reports a full distribution of plausible true
    success rates rather than one budget-dependent point estimate.

    Implemented by Monte Carlo sampling from the closed-form posterior via
    `random.betavariate`, rather than inverting the regularized incomplete
    beta function in closed form — the stdlib has no such inverse, and
    sampling keeps this module SciPy-free while remaining exact in
    expectation. `n_samples=20_000` keeps the Monte Carlo error on the
    reported bounds under roughly half a percentage point for the n this
    project uses (n in the 8-100 range).

    Args:
        successes, failures: observed counts (successes + failures = n).
        prior_alpha, prior_beta: Beta prior hyperparameters.
        confidence: two-sided credible level.
        n_samples: number of posterior draws.
        rng: injectable RNG, for reproducibility and testing.

    Returns:
        (posterior_mean, lower, upper).
    """
    if successes < 0 or failures < 0:
        raise ValueError("successes and failures must be >= 0")
    rng = rng or random.Random()
    a = prior_alpha + successes
    b = prior_beta + failures
    draws = sorted(rng.betavariate(a, b) for _ in range(n_samples))
    lo_idx = int((1 - confidence) / 2 * n_samples)
    hi_idx = int((1 - (1 - confidence) / 2) * n_samples) - 1
    posterior_mean = a / (a + b)
    return (posterior_mean, draws[lo_idx], draws[max(hi_idx, lo_idx)])


def bootstrap_ci(
    data: Sequence[float],
    statistic: Callable[[Sequence[float]], float] = fmean,
    *,
    n_resamples: int = 2_000,
    confidence: float = 0.95,
    rng: random.Random | None = None,
) -> tuple[float, float]:
    """Percentile bootstrap CI for an arbitrary statistic computed on `data`.

    Used where the estimand isn't a simple binomial proportion — e.g. the
    median actions-to-solve ratio, or a difference-of-rates between two
    conditions.

    Args:
        data: the observed sample.
        statistic: maps a resample (same length as `data`) to a scalar.
            Defaults to the arithmetic mean.
        n_resamples: number of bootstrap resamples.
        confidence: two-sided confidence level.
        rng: injectable RNG, for reproducibility and testing.

    Returns:
        (lower, upper) percentile bootstrap bounds.
    """
    if len(data) == 0:
        raise ValueError("data must be non-empty")
    rng = rng or random.Random()
    n = len(data)
    resample_stats = sorted(statistic(rng.choices(data, k=n)) for _ in range(n_resamples))
    lo_idx = int((1 - confidence) / 2 * n_resamples)
    hi_idx = int((1 - (1 - confidence) / 2) * n_resamples) - 1
    return (resample_stats[lo_idx], resample_stats[max(hi_idx, lo_idx)])


@dataclass(frozen=True, slots=True)
class ICCResult:
    """Result of a one-way random-effects ICC(1) decomposition."""

    icc: float
    ms_between: float
    ms_within: float
    df_between: int
    df_within: int
    n_groups: int
    n_total: int


def icc_one_way(groups: Mapping[str, Sequence[float]]) -> ICCResult:
    """One-way random-effects intraclass correlation, ICC(1) (the
    Fisher/Searle variance-components form), on possibly-unbalanced groups.

    In this project, `groups` keys are boundary-class identifiers and values
    are one numeric outcome per trial (success 0/1, or a continuous
    efficiency score — see docs/EVALUATION.md Part 2.3 for which is more
    appropriate for which question). ICC(1) answers: what fraction of total
    outcome variance is explained by *which boundary class* a trial faced
    (across-boundary / signal) vs. residual trial-to-trial noise on
    repeated, procedurally-fresh instances of the *same* class
    (within-boundary / noise)? A low ICC means class-level success-rate
    rankings drawn from a handful of trials are not trustworthy — the
    field-wide finding this project's trial-count tiers are designed around
    (docs/EVALUATION.md Part 2.3, which cites ICC as low as 0.30 in
    "Stochasticity in Agentic Evaluations").

    ICC(1) can be legitimately negative (between-group variance smaller than
    within-group variance implies by chance); this implementation returns
    the raw value rather than clamping to 0, since the raw value is itself
    diagnostic (report it as 0 in a headline table if a non-negative number
    is required for readability, but keep the raw value in the underlying
    data).

    Args:
        groups: mapping from group label to a sequence of numeric outcomes.
            Requires >= 2 groups and df_within = N - g >= 1.

    Returns:
        An `ICCResult`.
    """
    g = len(groups)
    if g < 2:
        raise ValueError("icc_one_way needs at least 2 groups")
    sizes = {k: len(v) for k, v in groups.items()}
    if any(n < 1 for n in sizes.values()):
        raise ValueError("every group needs at least 1 observation")
    n_total = sum(sizes.values())
    df_between = g - 1
    df_within = n_total - g
    if df_within < 1:
        raise ValueError("need at least one more observation than groups (df_within >= 1)")

    all_values = [x for v in groups.values() for x in v]
    grand_mean = fmean(all_values)

    group_means = {k: fmean(v) for k, v in groups.items()}
    ss_between = sum(sizes[k] * (group_means[k] - grand_mean) ** 2 for k in groups)
    ss_within = sum(sum((x - group_means[k]) ** 2 for x in v) for k, v in groups.items())

    ms_between = ss_between / df_between
    ms_within = ss_within / df_within

    # Unbalanced-design "n0" correction; reduces to the common group size
    # when the design is balanced. Standard variance-components formula
    # (Searle, Casella & McCulloch).
    sum_n2 = sum(n * n for n in sizes.values())
    n0 = (n_total - sum_n2 / n_total) / df_between

    denom = ms_between + (n0 - 1) * ms_within
    icc = (ms_between - ms_within) / denom if denom != 0 else 0.0

    return ICCResult(
        icc=icc,
        ms_between=ms_between,
        ms_within=ms_within,
        df_between=df_between,
        df_within=df_within,
        n_groups=g,
        n_total=n_total,
    )


def design_effect(icc: float, cluster_size: float) -> float:
    """DEFF = 1 + (cluster_size - 1) * icc.

    If trials are ever clustered (e.g. several trials reuse one
    procedurally-generated boundary instance instead of each drawing a
    fresh one — docs/EVALUATION.md Part 4.1 recommends against this
    precisely because of this inflation), the *effective* sample size for
    CI purposes shrinks by this factor. With the default fresh-instance-
    per-trial protocol, cluster_size=1 and DEFF=1 (no correction needed).
    """
    return 1 + (cluster_size - 1) * icc


def effective_sample_size(n: int, icc: float, cluster_size: float) -> float:
    """n / design_effect(icc, cluster_size)."""
    return n / design_effect(icc, cluster_size)


def required_n_for_margin(margin: float, p: float = 0.5, confidence: float = 0.95) -> int:
    """Planning-stage sample size for a target CI half-width ("margin").

    n = z^2 * p*(1-p) / margin^2, rounded up. Uses the simpler Wald form
    (rather than inverting Wilson) because this is a *planning* estimate,
    not the interval actually reported — see docs/EVALUATION.md Part 2.1 for
    how this arithmetic drives the 8-16 / >=32 trial-count tiers. p=0.5 is
    the conservative (maximum-variance) default; pass a tighter guess (e.g.
    p=0.85 for an easy tier expected near ceiling) for a smaller, still
    honest, planning number.
    """
    if not 0 < p < 1:
        raise ValueError("p must be in (0, 1)")
    if margin <= 0:
        raise ValueError("margin must be > 0")
    z = _z_for_confidence(confidence)
    return math.ceil((z * z) * p * (1 - p) / (margin * margin))


def cohens_kappa(rater_a: Sequence[str], rater_b: Sequence[str]) -> float:
    """Cohen's kappa for inter-rater agreement on categorical codes — e.g.
    two humans independently applying the failure taxonomy to the same
    audit subsample of traces (docs/EVALUATION.md Part 3.3).

    kappa = (p_o - p_e) / (1 - p_e)
    p_o = observed agreement proportion
    p_e = chance-expected agreement, from each rater's marginal frequencies

    Args:
        rater_a, rater_b: equal-length sequences of category labels (e.g.
            `FailureCode.value` strings), one pair per coded trace.

    Returns:
        kappa, roughly in [-1, 1]; 1 = perfect agreement, 0 = chance level.
    """
    if len(rater_a) != len(rater_b):
        raise ValueError("rater_a and rater_b must be the same length")
    n = len(rater_a)
    if n == 0:
        raise ValueError("need at least one coded item")

    categories = sorted(set(rater_a) | set(rater_b))
    observed_agree = sum(a == b for a, b in zip(rater_a, rater_b)) / n

    freq_a = {c: sum(x == c for x in rater_a) / n for c in categories}
    freq_b = {c: sum(x == c for x in rater_b) / n for c in categories}
    chance_agree = sum(freq_a[c] * freq_b[c] for c in categories)

    if chance_agree >= 1.0:
        return 1.0  # degenerate: only one category ever used, by construction
    return (observed_agree - chance_agree) / (1 - chance_agree)
