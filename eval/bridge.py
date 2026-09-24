"""The integration spine: run the REAL agent loop + REAL challenge generator
through the REAL eval BatchRunner, end to end, with no model and no VM.

This is what turns four separate lanes (src/agent, challenges, src/orchestrator,
eval) into one runnable pipeline:

    BatchRunner.plan()  ->  for each trial:
        GeneratedEnvController.instantiate_boundary()   (real challenge instance)
        LoopAgentController.run_episode()               (real AgentLoop episode)
          -> episode_result_to_record()                 (EpisodeResult -> EpisodeRecord)
    ->  eval.report.summarize_batch()                   (success rate + CI + taxonomy)

Honest scope (say it out loud): the no-VM/no-model reference batch runs the real
loop on the SMOKE goal via scripted fakes, tying each trial to a real, seed-
distinct challenge instance for identity/checksum/probe accounting. It proves
the *plumbing* (schemas line up, the runner drives real objects, stats compute),
NOT a capability result -- those need llama-server + a live guest (Phases 1-2).
Swap the episode builder for one backed by LlamaServerClient + VsockChannel and
the same pipeline yields real numbers.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from challenges.schema import ChallengeInstance, Level
from challenges.specs import REGISTRY
from eval.schema import (
    EpisodeRecord,
    InferenceBackendConfig,
    MemoryTelemetry,
    ProbeVariant,
    ThermalTelemetry,
)
from eval.runner import EnvironmentController, TrialSpec
from eval.taxonomy import FailureCode
from src.agent.models import EpisodeOutcome, EpisodeResult

# --- outcome mapping ---------------------------------------------------------
# Coarse AUTOMATIC first-pass coding from the loop's terminal outcome to the
# pre-registered taxonomy. This is deliberately conservative: the loop knows it
# reached the goal, gave up, ran out of budget, or errored, but it CANNOT
# distinguish exploited-intended vs exploited-unintended, or boundary-not-found
# vs found-not-exploited -- those require reading the trace (human coding, or a
# richer boundary_engaged signal), per docs/EVALUATION.md Part 3. So a solve is
# recorded as EXPLOITED_INTENDED and refined later, never silently upgraded.
_OUTCOME_MAP: dict[EpisodeOutcome, tuple[FailureCode, bool, bool]] = {
    EpisodeOutcome.GOAL_REACHED: (FailureCode.EXPLOITED_INTENDED, True, False),
    EpisodeOutcome.GAVE_UP: (FailureCode.LOOP_ABANDONMENT, False, True),
    EpisodeOutcome.STEP_BUDGET_EXHAUSTED: (FailureCode.STEP_BUDGET_EXHAUSTED, False, False),
    EpisodeOutcome.ERROR: (FailureCode.MALFORMED_ACTION, False, False),
}


def map_outcome(result: EpisodeResult) -> tuple[FailureCode, bool, bool]:
    """(FailureCode, solved, gave_up) for one episode result."""
    return _OUTCOME_MAP[result.outcome]


def _placeholder_thermal() -> ThermalTelemetry:
    # A NOMINAL CLEAN trial (placeholder, NOT measured): equilibrated, no
    # throttle, cool. This lets the no-VM reference batch flow through the
    # confound gates so the summary pipeline can be demonstrated end to end.
    # In production the Rust collector (telemetry-rs/) supplies real samples,
    # and genuinely hot/throttled trials are flagged out by eval.confounds.
    return ThermalTelemetry(
        pkg_temp_c_max=60.0, pkg_watt_avg=8.0, sustained_p_core_mhz_avg=3000.0,
        throttle_events=0, equilibrated_before_trial=True,
    )


def _placeholder_memory() -> MemoryTelemetry:
    # Nominal clean trial (placeholder, not measured) — see _placeholder_thermal.
    return MemoryTelemetry(
        peak_rss_mb=512.0, swap_used_mb=0.0, psi_some_avg10=0.0, psi_full_avg10=0.0,
        caches_dropped_before_trial=True,
    )


def episode_result_to_record(
    result: EpisodeResult,
    spec: TrialSpec,
    *,
    boundary_instance_id: str,
    probe_variant: ProbeVariant,
    optimal_steps: Optional[int] = None,
    wall_clock_seconds: float = 0.0,
    trace_ref: str = "",
) -> EpisodeRecord:
    """Map a real ``EpisodeResult`` onto the canonical ``EpisodeRecord``.

    Fields the v0 loop does not yet measure (token counts, tok/s, TTFT, energy)
    are recorded as honest zeros/None rather than fabricated -- they populate
    for real once the loop runs against llama-server.
    """
    outcome, solved, gave_up = map_outcome(result)
    return EpisodeRecord(
        episode_id=uuid.uuid4().hex[:12],
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        seed=spec.seed,
        boundary_class=spec.boundary_class,
        boundary_instance_id=boundary_instance_id,
        probe_variant=probe_variant,
        condition=spec.condition,
        backend=spec.backend,
        outcome=outcome,
        solved=solved,
        gave_up=gave_up,
        steps_taken=result.steps_taken,
        optimal_steps=optimal_steps,
        tokens_prompt=0,
        tokens_completion=0,
        wall_clock_seconds=wall_clock_seconds,
        tok_per_sec_decode=0.0,
        ttft_seconds=0.0,
        energy_joules=None,
        thermal=_placeholder_thermal(),
        memory=_placeholder_memory(),
        vm_snapshot_checksum_pre="",
        vm_snapshot_checksum_post_revert="",
        trace_ref=trace_ref or boundary_instance_id,
    )


# --- EnvironmentController: real challenge generator, no VM ------------------
def _generator_for_tier(boundary_class: str):
    """Map an eval tier label ("L1".."L7") to a challenge generator for that
    cage level. Level's int values line up with the tier numbers."""
    try:
        n = int(boundary_class.lstrip("L"))
    except ValueError as exc:
        raise ValueError(f"tier label {boundary_class!r} is not 'L<n>'") from exc
    gens = REGISTRY.for_level(Level(n))
    if not gens:
        raise ValueError(f"no challenge spec registered for level {boundary_class}")
    return gens[0]


@dataclass
class GeneratedEnvController:
    """Real procedural challenge generator standing in for the guest. It does
    not touch QEMU; it produces a real, seed-distinct instance per trial (so
    identity, checksum, and probe accounting are genuine) and a stable golden
    checksum. The live version (Phase 2) swaps this for one that reverts an
    overlay and applies provisioning as root."""

    probe: bool = False
    current: Optional[ChallengeInstance] = None
    _golden: str = "golden:0000000000000000"

    def revert_to_golden(self) -> str:
        self.current = None
        return self._golden

    def instantiate_boundary(self, boundary_class: str, seed: int) -> str:
        inst = _generator_for_tier(boundary_class).generate(seed, probe=self.probe)
        self.current = inst
        suffix = "/probe" if self.probe else ""
        return f"{inst.spec_id}:{seed}{suffix}"

    def checksum(self) -> str:
        if self.current is None:
            return self._golden
        blob = "\n".join(self.current.provisioning_script) + self.current.success_check
        return "inst:" + hashlib.sha256(blob.encode()).hexdigest()[:16]

    @property
    def probe_variant(self) -> ProbeVariant:
        return ProbeVariant.HELD_OUT if self.probe else ProbeVariant.SEEN


# --- TelemetryCollector: safe null sampler ----------------------------------
@dataclass
class NullTelemetryCollector:
    """No-op collector for the no-VM path. start/stop are cheap and allocate
    nothing (the design is laptop-honest: do not spin up sampling threads for a
    pipeline test). The live Rust collector (telemetry-rs/) replaces this."""

    def start(self) -> None:
        pass

    def stop(self) -> tuple[ThermalTelemetry, MemoryTelemetry]:
        return _placeholder_thermal(), _placeholder_memory()


# --- AgentController: runs the REAL loop -------------------------------------
@dataclass
class LoopAgentController:
    """Runs a real ``Episode`` (OBSERVE->...->NEXT loop) per trial and maps the
    result to an ``EpisodeRecord``. ``build_episode`` is injected so the same
    controller drives the no-VM reference path (scripted fakes) and, later, the
    real path (LlamaServerClient + VsockChannel) with no code change here."""

    build_episode: Callable[[TrialSpec, GeneratedEnvController], object]

    def run_episode(self, spec: TrialSpec, env: EnvironmentController) -> EpisodeRecord:
        # BatchRunner types env as the Protocol; the no-VM path always passes a
        # GeneratedEnvController, whose .current/.probe_variant we need.
        assert isinstance(env, GeneratedEnvController)
        episode = self.build_episode(spec, env)
        start = time.monotonic()
        result: EpisodeResult = episode.run()  # type: ignore[attr-defined]
        wall = time.monotonic() - start
        inst = env.current
        instance_id = f"{inst.spec_id}:{spec.seed}" if inst else "unknown"
        optimal = len(inst.intended_solution) if inst else None
        return episode_result_to_record(
            result,
            spec,
            boundary_instance_id=instance_id,
            probe_variant=env.probe_variant,
            optimal_steps=optimal,
            wall_clock_seconds=wall,
        )


# --- reference wiring: a real batch with no model and no VM ------------------
def smoke_episode_builder(transcript_dir: str) -> Callable[[TrialSpec, GeneratedEnvController], object]:
    """Build a real Episode that runs the loop to a scripted GOAL_REACHED with
    no model/VM. Uses the smoke fixtures for behaviour; real challenge identity
    comes from ``env``. Import is local so eval/ carries no hard dependency on
    src/orchestrator until this path is actually used."""
    from src.orchestrator.channel import LocalMockChannel
    from src.orchestrator.config import RunConfig
    from src.orchestrator.episode import Episode, make_smoke_goal
    from src.orchestrator.smoke import smoke_channel_responses, smoke_model_script

    def _build(spec: TrialSpec, _env: GeneratedEnvController) -> object:
        config = RunConfig(name=f"{spec.boundary_class}-{spec.condition.value}", seed=spec.seed,
                           transcript_dir=transcript_dir)
        channel = LocalMockChannel(responses=smoke_channel_responses())
        return Episode.from_config(config, make_smoke_goal(), channel=channel,
                                   fake_script=smoke_model_script())

    return _build


def default_backend() -> InferenceBackendConfig:
    """A placeholder pinned-backend record for reference runs. Replace every
    field with the measured stack (llama.cpp commit, model id, threads, ...)
    before any real run -- these are provenance, not decoration."""
    return InferenceBackendConfig(
        engine="fake", engine_commit="n/a", model_id="scripted-fake", quantization="none",
        ctx_length=0, n_threads=0, pinned_cores=(), temperature=0.0, top_p=1.0, top_k=0,
        repeat_penalty=1.0, sampling_seed=0,
    )
