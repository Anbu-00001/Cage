"""Batch-runner design: builds an N-seeds x conditions x boundary-classes
trial matrix and executes it through injected interfaces
(docs/EVALUATION.md Part 1 experimental design, Part 2 trial-count tiers).

This module defines the *shape* of the harness and its integration points.
It deliberately does not import or depend on anything under `src/` — the
agent loop, VM orchestrator, and telemetry collectors are owned and
evolving in a different lane of this repo. Instead it defines the
`Protocol` interfaces a concrete implementation of each must satisfy, so
`eval/` stays importable and unit-testable on its own (see
`eval/tests/test_runner.py`, which exercises this module against
fully in-memory fakes), and real integration is "construct a `BatchRunner`
with the concrete `src/` classes," not "rewrite `eval/`."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from eval.confounds import MemoryPolicy, ThermalPolicy
from eval.contamination import held_out_probe
from eval.schema import Condition, EpisodeRecord, InferenceBackendConfig, MemoryTelemetry, ThermalTelemetry

# -- difficulty tiers (docs/EVALUATION.md Part 2.1) --
#
# Boundary classes L0-L3 are "easy tier": early cage levels, expected near a
# success-rate ceiling or floor, mainly a sanity check that scaffolding
# hasn't regressed. L4-L7 are "hard tier": the scientifically load-bearing
# comparisons (scaffolding ablations, model ablations, transfer rate) where
# CI width and ICC actually drive the write-up's conclusions.

EASY_TIER_BOUNDARY_CLASSES: tuple[str, ...] = ("L0", "L1", "L2", "L3")
HARD_TIER_BOUNDARY_CLASSES: tuple[str, ...] = ("L4", "L5", "L6", "L7")

TRIALS_PER_SEED_EASY = 12   # within the pre-registered 8-16 band
TRIALS_PER_SEED_HARD = 32   # the pre-registered floor for load-bearing comparisons


def trials_for_boundary_class(boundary_class: str) -> int:
    """Look up the pre-registered trial count for a boundary class's tier.

    Raises for an unrecognized class rather than silently defaulting to
    something — every boundary class must be explicitly tiered (added to
    `EASY_TIER_BOUNDARY_CLASSES` or `HARD_TIER_BOUNDARY_CLASSES` above)
    before it is run, which is itself a small forcing function to think
    about difficulty before collecting data.
    """
    if boundary_class in EASY_TIER_BOUNDARY_CLASSES:
        return TRIALS_PER_SEED_EASY
    if boundary_class in HARD_TIER_BOUNDARY_CLASSES:
        return TRIALS_PER_SEED_HARD
    raise ValueError(
        f"boundary_class {boundary_class!r} is not tiered; add it to "
        "EASY_TIER_BOUNDARY_CLASSES or HARD_TIER_BOUNDARY_CLASSES first"
    )


@dataclass(frozen=True, slots=True)
class TrialSpec:
    """One cell of the experiment matrix, fully specified and reproducible
    from its fields alone (docs/EVALUATION.md Part 8: one-command
    reproducer)."""

    boundary_class: str
    condition: Condition
    seed: int
    backend: InferenceBackendConfig


class AgentController(Protocol):
    """What the harness needs from the agent/orchestrator side (concrete
    implementation lives in `src/agent`, `src/orchestrator`)."""

    def run_episode(self, spec: TrialSpec, env: "EnvironmentController") -> EpisodeRecord:
        """Run exactly one trial end to end and return its fully-populated
        `EpisodeRecord`, including outcome coding (see `eval.taxonomy`)."""
        ...


class EnvironmentController(Protocol):
    """What the harness needs from the VM/target side (concrete
    implementation lives in `src/orchestrator`, wrapping libvirt/QEMU). A
    concrete implementation is expected to use an `eval.contamination.
    ProceduralGenerator` internally in `instantiate_boundary` to draw the
    per-seed parameters — this interface only needs the resulting instance
    id, not the generator itself."""

    def revert_to_golden(self) -> str:
        """Revert the guest to the golden snapshot; return its checksum."""
        ...

    def instantiate_boundary(self, boundary_class: str, seed: int) -> str:
        """Materialize a procedurally-parameterized boundary instance in the
        (already-reverted) guest; return the instance id."""
        ...

    def checksum(self) -> str:
        """Checksum the current guest disk state."""
        ...


class TelemetryCollector(Protocol):
    """What the harness needs from the resource/thermal telemetry side
    (concrete implementation lives in `src/telemetry`)."""

    def start(self) -> None:
        """Begin 1 Hz sampling for the trial about to run."""
        ...

    def stop(self) -> tuple[ThermalTelemetry, MemoryTelemetry]:
        """Stop sampling and return the trial's aggregated telemetry."""
        ...


@dataclass
class BatchRunner:
    """Builds and executes the trial matrix for one experiment
    (docs/EVALUATION.md Part 1.2: one-variable-at-a-time).

    Construct one `BatchRunner` per experiment (e.g. "scaffolding ablation
    on L6"), not one for the whole project — that is what keeps each run's
    held-constant list (docs/EVALUATION.md Part 1.3) actually constant:
    everything not explicitly varied across `conditions` here (boundary
    classes, backend, thermal/memory policy) stays fixed for the life of one
    `BatchRunner`.
    """

    boundary_classes: tuple[str, ...]
    conditions: tuple[Condition, ...]
    seeds: tuple[int, ...]
    backend: InferenceBackendConfig  # held constant across this batch
    agent: AgentController
    env: EnvironmentController
    telemetry: TelemetryCollector
    thermal_policy: ThermalPolicy = field(default_factory=ThermalPolicy)
    memory_policy: MemoryPolicy = field(default_factory=MemoryPolicy)

    def plan(self) -> list[TrialSpec]:
        """Cartesian product of boundary_classes x conditions x seeds, using
        each boundary class's pre-registered tier trial count to *cap* how
        many of `self.seeds` are actually used for that class — callers can
        pass one generous seed pool and rely on tiering to right-size it,
        rather than hand-computing per-class seed lists.
        """
        plan: list[TrialSpec] = []
        for boundary_class in self.boundary_classes:
            n = trials_for_boundary_class(boundary_class)
            if len(self.seeds) < n:
                raise ValueError(
                    f"{boundary_class!r} needs {n} seeds but only "
                    f"{len(self.seeds)} were supplied"
                )
            class_seeds = self.seeds[:n]
            for condition in self.conditions:
                for seed in class_seeds:
                    plan.append(
                        TrialSpec(
                            boundary_class=boundary_class,
                            condition=condition,
                            seed=seed,
                            backend=self.backend,
                        )
                    )
        return plan

    def run_trial(self, spec: TrialSpec) -> EpisodeRecord:
        """Execute one trial through the injected interfaces, in the
        confound-controlled order docs/EVALUATION.md Part 5 specifies:
        revert -> checksum -> instantiate a fresh procedurally-parameterized
        instance -> run the episode -> stop telemetry -> checksum again.

        This method defines the *order and contract*; it is not a
        reimplementation of `src/orchestrator` and does not itself decide
        trial validity — thermal/memory validity gating happens downstream,
        in `eval.report.summarize_cell`, so that invalid trials are still
        recorded (never silently dropped at collection time).
        """
        golden_checksum = self.env.revert_to_golden()
        pre_checksum = self.env.checksum()
        self.env.instantiate_boundary(spec.boundary_class, spec.seed)
        self.telemetry.start()
        record = self.agent.run_episode(spec, self.env)
        thermal, memory = self.telemetry.stop()
        post_checksum = self.env.checksum()

        # The harness's own TelemetryCollector — which sampled across the
        # full revert -> instantiate -> episode window — is authoritative
        # over whatever (if anything) the agent controller populated on the
        # record, since only the harness has system-wide visibility.
        record.thermal = thermal
        record.memory = memory
        record.extra["golden_checksum"] = golden_checksum
        record.extra["pre_trial_checksum"] = pre_checksum
        record.extra["post_trial_checksum"] = post_checksum
        record.extra["probe_variant_computed"] = held_out_probe(spec.boundary_class, spec.seed).value
        return record

    def run_batch(self) -> list[EpisodeRecord]:
        """Run every planned trial, in sequence.

        Laptop-honest by design: no parallel trial execution (the whole
        premise is 2 P-cores and one guest at a time — docs/EVALUATION.md
        Part 0). Statistical power comes from N and cheap seeds, not from
        concurrency; see docs/EVALUATION.md Part 2.1 for why the trial
        counts are sized the way they are given that constraint.
        """
        return [self.run_trial(spec) for spec in self.plan()]
