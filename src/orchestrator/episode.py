"""Episode lifecycle: wire together config -> LLM client -> channel ->
tool registry -> agent loop -> (optional) telemetry, run one episode, and
persist the transcript.

This is the piece that makes ``run.sh --seed 42 --config config/example.yaml``
mean something concrete (Part 18's reproducibility bar): given the same
config and seed, ``Episode.run()`` should produce a byte-comparable
transcript against a real, pinned model+VM -- and against the fake client
it is fully deterministic today, which is what the smoke test checks.

TODO(VM lifecycle): reverting the guest to its golden snapshot before the
episode and confirming the revert (Part 5: "external qcow2 + libvirt
snapshots... every trial forks and reverts") belongs here, via a small
``libvirt``/``virsh`` wrapper. Not implemented yet -- this lane owns the
agent/orchestrator/telemetry code, not the VM image or libvirt plumbing
(see docs/SCRATCHPAD.md fleet plan). ``Episode`` calls a ``reset_guest``
hook that defaults to a no-op so the rest of the pipeline is exercisable
today without a running VM.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.agent.interfaces import ActionChannel, CompletionClient
from src.agent.loop import AgentLoop, LoopConfig
from src.agent.models import EpisodeResult, Goal
from src.agent.tools import ToolRegistry
from src.orchestrator.config import RunConfig
from src.orchestrator.llm_client import FakeLLMClient, LlamaServerClient

logger = logging.getLogger("cage.episode")

ResetGuestHook = Callable[[RunConfig], None]


def _default_reset_guest(config: RunConfig) -> None:
    """No-op placeholder for the real snapshot-revert. Logged loudly so
    it's never silently mistaken for an actual reset in a run's logs."""
    logger.warning(
        "reset_guest is a no-op stub (channel=%s) -- guest state is NOT "
        "being reverted to a golden snapshot. Wire a real libvirt/virsh "
        "revert before trusting cross-episode isolation.",
        config.vm.channel,
    )


@dataclass
class Episode:
    """Runs exactly one episode against one ``Goal`` and persists its
    transcript. Construct via :meth:`from_config` in normal use;
    the bare constructor is what tests use to inject fakes directly.
    """

    goal: Goal
    llm: CompletionClient
    channel: ActionChannel
    config: RunConfig
    reset_guest: ResetGuestHook = _default_reset_guest

    @classmethod
    def from_config(
        cls,
        config: RunConfig,
        goal: Goal,
        *,
        channel: ActionChannel,
        fake_script: list[str] | None = None,
    ) -> "Episode":
        """Build an Episode from a validated ``RunConfig``. ``channel`` is
        always supplied by the caller (built via
        ``src.orchestrator.channel.build_channel(config.vm.channel, ...)``)
        rather than constructed here, because the channel's kwargs (ssh
        host/key, vsock cid) are deployment-specific, not just config-file
        fields on their own.
        """
        if fake_script is not None:
            llm: CompletionClient = FakeLLMClient(script=fake_script)
        else:
            llm = LlamaServerClient(base_url=config.model.server_url)
        return cls(goal=goal, llm=llm, channel=channel, config=config)

    def run(self) -> EpisodeResult:
        self.reset_guest(self.config)

        tools = ToolRegistry.default(self.channel)
        loop_config = LoopConfig(
            step_budget=self.config.loop.step_budget,
            replan_interval=self.config.loop.replan_interval,
            char_budget=self.config.loop.char_budget,
            temperature=self.config.sampling.temperature,
            # RunConfig.seed is THE run/reproducibility seed (what `--seed`
            # on the CLI controls, and what names the transcript file
            # below); sampling.seed is kept as a separate, documented
            # pinned artifact (Part 18) in case a future config wants LLM
            # sampling noise decoupled from episode/challenge-instance
            # seeding, but for this scaffold the run seed is authoritative.
            seed=self.config.seed,
            max_tokens=self.config.model.n_predict,
        )
        loop = AgentLoop(goal=self.goal, llm=self.llm, tools=tools, config=loop_config)
        result = loop.run()

        self._persist_transcript(result)
        return result

    def _persist_transcript(self, result: EpisodeResult) -> None:
        out_dir = Path(self.config.transcript_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{self.config.name}-seed{self.config.seed}.json"
        out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        logger.info("transcript written to %s (outcome=%s, steps=%d)", out_path, result.outcome, result.steps_taken)


def make_smoke_goal() -> Goal:
    """The tiny, hardcoded goal the smoke test / `run.sh --smoke` solve:
    a Level-0 "find and report a file's contents" task requiring exactly
    two tool calls (list_dir, then read_file) plus one submit_flag --
    small enough to script a deterministic FakeLLMClient against, big
    enough to exercise OBSERVE->...->NEXT, typed tools, and memory for
    real. See tests/test_smoke.py for the accompanying scripted model and
    mock channel.
    """
    return Goal(
        id="smoke-l0-read-secret",
        description=(
            "A file somewhere under the current directory holds a short "
            "secret value. Find it and submit its exact contents as the flag."
        ),
        level=0,
        success_predicate="hunter2",
    )
