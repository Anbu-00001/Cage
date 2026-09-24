"""Outcome and efficiency metrics computed over batches of `EpisodeRecord`
(docs/EVALUATION.md Part 6, the metrics table).

Every function here takes a `Sequence[EpisodeRecord]` for one reporting cell
(typically one boundary_class x condition) and returns either a scalar or a
small result dataclass. None of these functions mutate their input or reach
out to any live system — they are pure aggregation over already-collected
records, which is what keeps them trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean, median
from typing import Sequence

from eval.schema import EpisodeRecord
from eval.statistics import wilson_ci

__all__ = [
    "decode_tokens_per_second",
    "mean_ttft",
    "mean_steps_per_episode",
    "EfficiencyResult",
    "actions_to_solve_efficiency",
    "SuccessRateResult",
    "success_rate_with_ci",
    "give_up_rate",
    "tokens_per_solve",
    "joules_per_solve",
    "solves_per_watt_hour",
    "mean_wall_clock_seconds",
]


def _require_nonempty(episodes: Sequence[EpisodeRecord]) -> None:
    if not episodes:
        raise ValueError("episodes must be non-empty")


def _percentile(sorted_data: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile, no numpy dependency. `sorted_data`
    must already be sorted ascending."""
    if not sorted_data:
        raise ValueError("sorted_data must be non-empty")
    if len(sorted_data) == 1:
        return sorted_data[0]
    idx = q * (len(sorted_data) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_data) - 1)
    frac = idx - lo
    return sorted_data[lo] + (sorted_data[hi] - sorted_data[lo]) * frac


def decode_tokens_per_second(episodes: Sequence[EpisodeRecord]) -> float:
    """Mean decode tok/s across episodes (computed per-episode by the
    runner from raw timing; this aggregates it for reporting)."""
    _require_nonempty(episodes)
    return fmean(e.tok_per_sec_decode for e in episodes)


def mean_ttft(episodes: Sequence[EpisodeRecord]) -> float:
    """Mean time-to-first-token, seconds."""
    _require_nonempty(episodes)
    return fmean(e.ttft_seconds for e in episodes)


def mean_steps_per_episode(episodes: Sequence[EpisodeRecord]) -> float:
    _require_nonempty(episodes)
    return fmean(e.steps_taken for e in episodes)


@dataclass(frozen=True, slots=True)
class EfficiencyResult:
    """actions-to-solve vs. optimal, computed only over *solved* episodes
    that carry a known `optimal_steps`. Reported as median + IQR rather than
    a mean, since the ratio is right-skewed (docs/EVALUATION.md Part 6)."""

    n: int
    median_ratio: float
    p25_ratio: float
    p75_ratio: float


def actions_to_solve_efficiency(episodes: Sequence[EpisodeRecord]) -> EfficiencyResult:
    ratios = sorted(
        e.steps_taken / e.optimal_steps for e in episodes if e.solved and e.optimal_steps
    )
    if not ratios:
        raise ValueError("no solved episodes with a known optimal_steps")
    return EfficiencyResult(
        n=len(ratios),
        median_ratio=median(ratios),
        p25_ratio=_percentile(ratios, 0.25),
        p75_ratio=_percentile(ratios, 0.75),
    )


@dataclass(frozen=True, slots=True)
class SuccessRateResult:
    successes: int
    n: int
    rate: float
    wilson_lo: float
    wilson_hi: float


def success_rate_with_ci(episodes: Sequence[EpisodeRecord], confidence: float = 0.95) -> SuccessRateResult:
    _require_nonempty(episodes)
    successes = sum(e.solved for e in episodes)
    n = len(episodes)
    lo, hi = wilson_ci(successes, n, confidence=confidence)
    return SuccessRateResult(successes=successes, n=n, rate=successes / n, wilson_lo=lo, wilson_hi=hi)


def give_up_rate(episodes: Sequence[EpisodeRecord]) -> float:
    _require_nonempty(episodes)
    return sum(e.gave_up for e in episodes) / len(episodes)


def tokens_per_solve(episodes: Sequence[EpisodeRecord]) -> float | None:
    """Total tokens spent (across ALL episodes in the cell, solved or not)
    divided by the number of solves — the honest "cost of one success"
    number. Returns None if there were zero solves (undefined, not
    infinite — report "no solves in N attempts" instead of a divide by
    zero)."""
    _require_nonempty(episodes)
    solves = sum(e.solved for e in episodes)
    if solves == 0:
        return None
    total_tokens = sum(e.tokens_prompt + e.tokens_completion for e in episodes)
    return total_tokens / solves


def joules_per_solve(episodes: Sequence[EpisodeRecord]) -> float | None:
    """Same shape as `tokens_per_solve`, for RAPL package-energy joules.
    Episodes missing `energy_joules` (RAPL unavailable for that trial) are
    excluded from both the numerator and the solve count used here, so this
    number is self-consistent on the metered subset — callers should check
    `len(metered) / len(episodes)` coverage before trusting it on a
    partially-instrumented batch."""
    _require_nonempty(episodes)
    metered = [e for e in episodes if e.energy_joules is not None]
    if not metered:
        return None
    solves = sum(e.solved for e in metered)
    if solves == 0:
        return None
    total_joules = sum(e.energy_joules for e in metered)  # type: ignore[misc]
    return total_joules / solves


def solves_per_watt_hour(episodes: Sequence[EpisodeRecord]) -> float | None:
    """Solves per watt-hour, from the same energy-metered subset as
    `joules_per_solve` (docs/EVALUATION.md Part 6)."""
    _require_nonempty(episodes)
    metered = [e for e in episodes if e.energy_joules is not None]
    if not metered:
        return None
    total_joules = sum(e.energy_joules for e in metered)  # type: ignore[misc]
    if total_joules <= 0:
        return None
    solves = sum(e.solved for e in metered)
    watt_hours = total_joules / 3_600.0
    return solves / watt_hours


def mean_wall_clock_seconds(episodes: Sequence[EpisodeRecord]) -> float:
    _require_nonempty(episodes)
    return fmean(e.wall_clock_seconds for e in episodes)
