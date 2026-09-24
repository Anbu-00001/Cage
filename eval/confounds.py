"""Confound-control policies and validity gating (docs/EVALUATION.md Part 5).

Three independent confounds are controlled here, deliberately kept separate
from the outcome taxonomy (`eval.taxonomy`) and from the contamination
controls (`eval.contamination`):

  1. Thermal drift — pre-equilibration + per-trial throttle detection.
  2. Memory pressure — VM revert + cache drop + PSI monitoring.
  3. Determinism honesty — snapshot checksums + measured repeat variance,
     because temp=0 is not the same claim as "deterministic."

Inference-backend *pinning* lives in `eval.schema.InferenceBackendConfig`
(it's a property of a trial's design, not a runtime validity check), but its
*sensitivity re-run* analysis (`backend_sensitivity_delta`) lives here, next
to the other "is this result trustworthy" checks.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from eval.schema import EpisodeRecord, MemoryTelemetry, ThermalTelemetry


class TrialValidity(str, Enum):
    """A confound-driven validity flag, orthogonal to `FailureCode`. Attach
    one per trial (see docs/EVALUATION.md Part 7 reporting template:
    invalid trials are reported and excluded from the primary analysis,
    never silently dropped)."""

    VALID = "valid"
    THERMAL_INVALID = "thermal_invalid"
    MEMORY_INVALID = "memory_invalid"


@dataclass(frozen=True, slots=True)
class ThermalPolicy:
    """docs/EVALUATION.md Part 5.1."""

    equilibration_minutes: float = 10.0
    max_pkg_temp_c: float = 95.0
    max_throttle_events: int = 0
    max_freq_drop_ratio: float = 0.15  # vs. the session's own median non-throttled freq


def evaluate_thermal_validity(
    telemetry: ThermalTelemetry,
    policy: ThermalPolicy,
    session_median_sustained_mhz: float = 0.0,
) -> TrialValidity:
    """Flags a trial THERMAL_INVALID if it wasn't equilibrated, logged an
    explicit throttle event, ran hotter than the policy ceiling, or its
    sustained P-core clock fell too far below the session's own median.

    `session_median_sustained_mhz <= 0` skips the relative-drop check (the
    caller hasn't computed a session median yet); the other three checks
    still apply.
    """
    if not telemetry.equilibrated_before_trial:
        return TrialValidity.THERMAL_INVALID
    if telemetry.throttle_events > policy.max_throttle_events:
        return TrialValidity.THERMAL_INVALID
    if telemetry.pkg_temp_c_max > policy.max_pkg_temp_c:
        return TrialValidity.THERMAL_INVALID
    if session_median_sustained_mhz > 0:
        drop = 1 - (telemetry.sustained_p_core_mhz_avg / session_median_sustained_mhz)
        if drop > policy.max_freq_drop_ratio:
            return TrialValidity.THERMAL_INVALID
    return TrialValidity.VALID


@dataclass(frozen=True, slots=True)
class MemoryPolicy:
    """docs/EVALUATION.md Part 5.2."""

    require_cache_drop: bool = True
    max_psi_some_avg10: float = 10.0
    max_psi_full_avg10: float = 2.0


def evaluate_memory_validity(telemetry: MemoryTelemetry, policy: MemoryPolicy) -> TrialValidity:
    """Flags a trial MEMORY_INVALID if cache-drop hygiene wasn't met or the
    guest/host showed pressure levels (PSI) that plausibly perturbed decode
    throughput or I/O timing during the trial."""
    if policy.require_cache_drop and not telemetry.caches_dropped_before_trial:
        return TrialValidity.MEMORY_INVALID
    if telemetry.psi_some_avg10 > policy.max_psi_some_avg10:
        return TrialValidity.MEMORY_INVALID
    if telemetry.psi_full_avg10 > policy.max_psi_full_avg10:
        return TrialValidity.MEMORY_INVALID
    return TrialValidity.VALID


def verify_clean_revert(golden_checksum: str, pre_trial_checksum: str, post_revert_checksum: str) -> bool:
    """Determinism honesty, environment half (docs/EVALUATION.md Part 5.4):
    the VM snapshot must checksum-match the golden image both immediately
    before a trial and immediately after the post-trial revert. This isolates
    *environment* nondeterminism from *model* nondeterminism — if this ever
    fails, the environment itself is the confound, not the agent, and the
    whole session's trials from that point on are suspect.
    """
    return pre_trial_checksum == golden_checksum == post_revert_checksum


@dataclass(frozen=True, slots=True)
class RepeatVarianceResult:
    """Determinism honesty, model half: the measured behavior of K exact
    repeats of one (seed, config, instance) cell. temp=0 does not imply
    identical output across threads/runs (multithreaded floating-point
    reduction order is not guaranteed) — report this number instead of
    asserting determinism (docs/EVALUATION.md Part 5.4)."""

    n_repeats: int
    outcome_flip_rate: float  # fraction whose binary `solved` != the modal value
    modal_solved: bool


def measure_repeat_variance(repeats: Sequence[EpisodeRecord]) -> RepeatVarianceResult:
    """Compute a `RepeatVarianceResult` from K repeat runs of one identical
    (seed, backend config, boundary instance) cell."""
    if len(repeats) < 2:
        raise ValueError("need at least 2 repeats to measure variance")
    solved_flags = [r.solved for r in repeats]
    modal_solved = Counter(solved_flags).most_common(1)[0][0]
    flips = sum(1 for s in solved_flags if s != modal_solved)
    return RepeatVarianceResult(
        n_repeats=len(repeats),
        outcome_flip_rate=flips / len(repeats),
        modal_solved=modal_solved,
    )


def backend_sensitivity_delta(primary: Sequence[EpisodeRecord], secondary_backend: Sequence[EpisodeRecord]) -> float:
    """docs/EVALUATION.md Part 5.3 sensitivity re-run: the raw difference in
    success rate between the primary-backend subset and the same cell
    re-run on a second, differently-built inference backend.

    A caller should compare `abs(delta)` against the primary cell's Wilson
    CI half-width — if the delta exceeds it, the backend is a live confound
    for that comparison and must be disclosed prominently, not averaged
    away or omitted.
    """
    if not primary or not secondary_backend:
        raise ValueError("both sequences must be non-empty")
    p1 = sum(r.solved for r in primary) / len(primary)
    p2 = sum(r.solved for r in secondary_backend) / len(secondary_backend)
    return p2 - p1
