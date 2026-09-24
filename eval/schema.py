"""The canonical Constraint Cage episode record — one dataclass definition of
"what one episode record looks like as JSON" (docs/EVALUATION.md Parts 6-7),
plus the small supporting dataclasses/enums it's built from.

Every batch-runner output, every statistic computed in this package, and
every released trace in the eventual public artifact (constraint-cage-v2.md
Part A5) should serialize through `EpisodeRecord`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from eval.taxonomy import FailureCode


class Condition(str, Enum):
    """The experimental condition a trial was run under (docs/EVALUATION.md
    Part 1.1). Exactly one per trial."""

    BASELINE_RANDOM = "baseline_random"      # random legal action each step — chance floor
    BASELINE_OPTIMAL = "baseline_optimal"    # scripted solver — best-possible ceiling
    CONTROL_MINIMAL = "control_minimal"      # model, no memory/planning scaffolding
    TREATMENT_FULL = "treatment_full"        # model, full scaffolding
    PLANNER_ARBITRAGE = "planner_arbitrage"  # optional Arch-D tier (v2 A3 backup 2)


class ProbeVariant(str, Enum):
    """Whether this trial's procedurally-generated boundary instance was one
    the agent/scaffolding developer ever saw during development (`SEEN`) or
    was reserved, untouched, for final evaluation only (`HELD_OUT`) — the
    contamination control in docs/EVALUATION.md Part 4.2."""

    SEEN = "seen"
    HELD_OUT = "held_out"


@dataclass(frozen=True, slots=True)
class InferenceBackendConfig:
    """The pinned inference stack for a trial (docs/EVALUATION.md Part 5.3).
    Every field here is a documented source of score variance in the
    literature this project's methodology is built against; treat a change
    to any field as a new experimental condition, not a footnote."""

    engine: str                     # e.g. "llama.cpp"
    engine_commit: str              # exact git commit / release tag
    model_id: str                   # e.g. "qwen2.5-3b-instruct"
    quantization: str               # e.g. "Q4_K_M"
    ctx_length: int
    n_threads: int
    pinned_cores: tuple[int, ...]   # physical core ids pinned via taskset/cgroup
    temperature: float
    top_p: float
    top_k: int
    repeat_penalty: float
    sampling_seed: int


@dataclass(frozen=True, slots=True)
class ThermalTelemetry:
    """Per-trial thermal summary, aggregated from 1 Hz samples
    (docs/EVALUATION.md Part 5.1)."""

    pkg_temp_c_max: float
    pkg_watt_avg: float
    sustained_p_core_mhz_avg: float
    throttle_events: int
    equilibrated_before_trial: bool


@dataclass(frozen=True, slots=True)
class MemoryTelemetry:
    """Per-trial memory-pressure summary (docs/EVALUATION.md Part 5.2)."""

    peak_rss_mb: float
    swap_used_mb: float
    psi_some_avg10: float
    psi_full_avg10: float
    caches_dropped_before_trial: bool


@dataclass(slots=True)
class EpisodeRecord:
    """One coded, telemetered attempt at one boundary instance, under one
    condition. This is the unit of analysis for every statistic in
    `eval.statistics` / `eval.metrics` / `eval.report`, and the unit that
    gets released in the traces+telemetry dataset (constraint-cage-v2.md
    Part A5)."""

    # -- identity --
    episode_id: str
    timestamp_utc: str
    seed: int
    boundary_class: str
    boundary_instance_id: str
    probe_variant: ProbeVariant
    condition: Condition
    backend: InferenceBackendConfig

    # -- outcome (Part 3 codebook) --
    outcome: FailureCode
    solved: bool
    gave_up: bool

    # -- efficiency --
    steps_taken: int
    optimal_steps: int | None
    tokens_prompt: int
    tokens_completion: int
    wall_clock_seconds: float
    tok_per_sec_decode: float
    ttft_seconds: float
    energy_joules: float | None

    # -- confound telemetry (Part 5) --
    thermal: ThermalTelemetry
    memory: MemoryTelemetry
    vm_snapshot_checksum_pre: str
    vm_snapshot_checksum_post_revert: str

    # -- provenance / auditability --
    trace_ref: str                          # path or content-hash to the full transcript
    coder_id: str | None = None
    coder_notes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to the canonical JSON form (enums as their `.value`)."""
        d = asdict(self)
        d["probe_variant"] = self.probe_variant.value
        d["condition"] = self.condition.value
        d["outcome"] = self.outcome.value
        return json.dumps(d, sort_keys=True, default=str)

    @classmethod
    def from_json(cls, raw: str) -> "EpisodeRecord":
        """Inverse of `to_json`. Reconstructs nested dataclasses and enums;
        `pinned_cores` is round-tripped through a JSON array and rebuilt as
        a tuple to match `InferenceBackendConfig`'s field type."""
        d = json.loads(raw)
        backend_d = dict(d["backend"])
        backend_d["pinned_cores"] = tuple(backend_d["pinned_cores"])
        d["backend"] = InferenceBackendConfig(**backend_d)
        d["thermal"] = ThermalTelemetry(**d["thermal"])
        d["memory"] = MemoryTelemetry(**d["memory"])
        d["probe_variant"] = ProbeVariant(d["probe_variant"])
        d["condition"] = Condition(d["condition"])
        d["outcome"] = FailureCode(d["outcome"])
        return cls(**d)


# A JSON Schema (draft 2020-12) description of `EpisodeRecord.to_json()`'s
# output, kept as a plain dict so validating a released trace file needs no
# dependency beyond an optional `jsonschema.validate(instance, EPISODE_JSON_SCHEMA)`
# — this repo does not require that package to be installed.
EPISODE_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ConstraintCageEpisodeRecord",
    "type": "object",
    "required": [
        "episode_id", "timestamp_utc", "seed", "boundary_class",
        "boundary_instance_id", "probe_variant", "condition", "backend",
        "outcome", "solved", "gave_up", "steps_taken", "optimal_steps",
        "tokens_prompt", "tokens_completion", "wall_clock_seconds",
        "tok_per_sec_decode", "ttft_seconds", "energy_joules", "thermal",
        "memory", "vm_snapshot_checksum_pre", "vm_snapshot_checksum_post_revert",
        "trace_ref",
    ],
    "properties": {
        "episode_id": {"type": "string"},
        "timestamp_utc": {"type": "string", "format": "date-time"},
        "seed": {"type": "integer"},
        "boundary_class": {"type": "string"},
        "boundary_instance_id": {"type": "string"},
        "probe_variant": {"enum": [v.value for v in ProbeVariant]},
        "condition": {"enum": [v.value for v in Condition]},
        "backend": {
            "type": "object",
            "required": [
                "engine", "engine_commit", "model_id", "quantization",
                "ctx_length", "n_threads", "pinned_cores", "temperature",
                "top_p", "top_k", "repeat_penalty", "sampling_seed",
            ],
        },
        "outcome": {"enum": [v.value for v in FailureCode]},
        "solved": {"type": "boolean"},
        "gave_up": {"type": "boolean"},
        "steps_taken": {"type": "integer", "minimum": 0},
        "optimal_steps": {"type": ["integer", "null"], "minimum": 0},
        "tokens_prompt": {"type": "integer", "minimum": 0},
        "tokens_completion": {"type": "integer", "minimum": 0},
        "wall_clock_seconds": {"type": "number", "minimum": 0},
        "tok_per_sec_decode": {"type": "number", "minimum": 0},
        "ttft_seconds": {"type": "number", "minimum": 0},
        "energy_joules": {"type": ["number", "null"], "minimum": 0},
        "thermal": {
            "type": "object",
            "required": [
                "pkg_temp_c_max", "pkg_watt_avg", "sustained_p_core_mhz_avg",
                "throttle_events", "equilibrated_before_trial",
            ],
        },
        "memory": {
            "type": "object",
            "required": [
                "peak_rss_mb", "swap_used_mb", "psi_some_avg10",
                "psi_full_avg10", "caches_dropped_before_trial",
            ],
        },
        "vm_snapshot_checksum_pre": {"type": "string"},
        "vm_snapshot_checksum_post_revert": {"type": "string"},
        "trace_ref": {"type": "string"},
        "coder_id": {"type": ["string", "null"]},
        "coder_notes": {"type": ["string", "null"]},
        "extra": {"type": "object"},
    },
    "additionalProperties": False,
}
