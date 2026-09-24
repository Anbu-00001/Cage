"""Aggregates coded, telemetered episodes into the per-cell summary the
write-up template in docs/EVALUATION.md Part 7 requires: one row per
(boundary_class, condition) with success rate plus both CI methods, the
full outcome distribution, transfer rate, and confound-flag counts — never
a bare pass rate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from eval.confounds import (
    MemoryPolicy,
    ThermalPolicy,
    TrialValidity,
    evaluate_memory_validity,
    evaluate_thermal_validity,
)
from eval.contamination import TransferResult, transfer_rate
from eval.metrics import SuccessRateResult, success_rate_with_ci
from eval.schema import EpisodeRecord
from eval.statistics import ICCResult, bayesian_credible_interval, icc_one_way
from eval.taxonomy import distribution_proportions


@dataclass(frozen=True, slots=True)
class CellSummary:
    """One row of the results table (docs/EVALUATION.md Part 7)."""

    boundary_class: str
    condition: str
    n_total: int
    n_valid: int
    success: SuccessRateResult
    bayesian_mean: float
    bayesian_ci: tuple[float, float]
    outcome_distribution: dict[str, float]
    transfer: TransferResult | None
    invalid_thermal: int
    invalid_memory: int


def summarize_cell(
    episodes: Sequence[EpisodeRecord],
    *,
    thermal_policy: ThermalPolicy = ThermalPolicy(),
    memory_policy: MemoryPolicy = MemoryPolicy(),
    session_median_sustained_mhz: float = 0.0,
) -> CellSummary:
    """Summarize one (boundary_class, condition) cell.

    Invalid (thermal- or memory-flagged) trials are excluded from
    `success`/`bayesian_*` but counted and reported on the summary
    (docs/EVALUATION.md Part 5: flag and segregate, never silently drop).
    All episodes passed in must share the same `boundary_class` and
    `condition` — this function does not group; use `summarize_batch` for
    that.
    """
    if not episodes:
        raise ValueError("episodes must be non-empty")
    boundary_class = episodes[0].boundary_class
    condition = episodes[0].condition.value
    if any(e.boundary_class != boundary_class or e.condition.value != condition for e in episodes):
        raise ValueError("summarize_cell requires a single (boundary_class, condition) cell; use summarize_batch to group")

    valid: list[EpisodeRecord] = []
    invalid_thermal = 0
    invalid_memory = 0
    for e in episodes:
        thermal_flag = evaluate_thermal_validity(e.thermal, thermal_policy, session_median_sustained_mhz)
        if thermal_flag is not TrialValidity.VALID:
            invalid_thermal += 1
            continue
        memory_flag = evaluate_memory_validity(e.memory, memory_policy)
        if memory_flag is not TrialValidity.VALID:
            invalid_memory += 1
            continue
        valid.append(e)

    if not valid:
        raise ValueError(f"every trial in {boundary_class}/{condition} was confound-flagged; nothing to summarize")

    success = success_rate_with_ci(valid)
    post_mean, lo, hi = bayesian_credible_interval(success.successes, success.n - success.successes)
    outcomes = distribution_proportions(e.outcome for e in valid)

    try:
        transfer = transfer_rate(valid)
    except ValueError:
        transfer = None  # cell has only SEEN or only HELD_OUT episodes

    return CellSummary(
        boundary_class=boundary_class,
        condition=condition,
        n_total=len(episodes),
        n_valid=len(valid),
        success=success,
        bayesian_mean=post_mean,
        bayesian_ci=(lo, hi),
        outcome_distribution={k.value: v for k, v in outcomes.items()},
        transfer=transfer,
        invalid_thermal=invalid_thermal,
        invalid_memory=invalid_memory,
    )


def summarize_batch(episodes: Sequence[EpisodeRecord], **kwargs) -> list[CellSummary]:
    """Group episodes by (boundary_class, condition) and summarize each
    cell. Extra keyword arguments are forwarded to `summarize_cell`."""
    cells: dict[tuple[str, str], list[EpisodeRecord]] = defaultdict(list)
    for e in episodes:
        cells[(e.boundary_class, e.condition.value)].append(e)
    return [summarize_cell(v, **kwargs) for v in cells.values()]


def icc_across_boundary_classes(episodes: Sequence[EpisodeRecord]) -> ICCResult:
    """The within- vs. across-boundary variance split (docs/EVALUATION.md
    Part 2.3): groups outcomes by `boundary_class`, using the binary
    `solved` indicator as the numeric outcome (0/1). See that section for
    the caveat about ANOVA-style ICC on a binary outcome vs. a continuous
    efficiency score, and prefer `actions_to_solve` ratios there when
    variance resolution matters more than this diagnostic's simplicity.
    """
    groups: dict[str, list[float]] = defaultdict(list)
    for e in episodes:
        groups[e.boundary_class].append(1.0 if e.solved else 0.0)
    return icc_one_way(groups)


def render_table(summaries: Sequence[CellSummary]) -> str:
    """Plain-text table, dependency-free (no pandas) — good enough for a
    terminal, or to paste into a results write-up."""
    header = f"{'boundary':<10}{'condition':<18}{'n':>5}{'valid':>7}{'succ':>7}{'wilson95':>18}{'top_outcome':>22}"
    lines = [header, "-" * len(header)]
    for s in summaries:
        top_outcome = max(s.outcome_distribution.items(), key=lambda kv: kv[1], default=("-", 0.0))
        wilson = f"[{s.success.wilson_lo:.2f},{s.success.wilson_hi:.2f}]"
        lines.append(
            f"{s.boundary_class:<10}{s.condition:<18}{s.n_total:>5}{s.n_valid:>7}"
            f"{s.success.rate:>7.2f}{wilson:>18}{top_outcome[0]:>22}"
        )
    return "\n".join(lines)
