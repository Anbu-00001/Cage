"""The agent loop: OBSERVE -> STATE -> HYPOTHESIS -> PLAN -> ACTION ->
OBSERVATION -> EVALUATE -> UPDATE BELIEF -> NEXT.

This is the load-bearing implementation of constraint-cage.md Part 7.
Deliberately NOT a chatbot-with-a-shell: every step emits one typed
``AgentStepOutput`` (hypothesis/plan/action), not free-form text, and the
loop enforces the CPU-laptop-honest constraints the design docs insist on:

- a HARD step budget -- no unbounded wandering (Part 7, Part 17).
- PERIODIC, not per-step, re-planning -- an extra inference call every
  step roughly doubles cost on a 2-P-core box (Part 1, Part 7, Part 13);
  the strategic review only runs every ``replan_interval`` steps.
- FAILURE MEMORY consulted before every action executes, so the #1
  small-model death -- repeating a dead end -- is structurally blocked,
  not just discouraged by a prompt instruction that a weak model may
  ignore.
- context SUMMARIZATION whenever the rendered state would exceed a char
  budget, since prefill cost grows with context on CPU (Part 2).

No sub-agents: one ``CompletionClient``, one loop, one inference call per
step plus an occasional budgeted re-plan call -- matching Part 7's "multi-
agent = multi-inference = unaffordable" verdict for this hardware.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

from src.agent.interfaces import CompletionClient
from src.agent.memory import StructuredMemory
from src.agent.models import (
    AgentStepOutput,
    Evaluation,
    EpisodeOutcome,
    EpisodeResult,
    Goal,
    StepRecord,
    ToolResult,
)
from src.agent.prompts import parse_step_output, render_replan_prompt, render_step_prompt
from src.agent.summarizer import HeuristicSummarizer, Summarizer
from src.agent.tools import ToolRegistry

logger = logging.getLogger(__name__)

# Bound on how much of a single tool's raw stdout/stderr is kept verbatim
# in the transcript / shown back to the model. Anything longer is hashed
# and truncated -- "capture bounded output of last action (truncated,
# hashed)", Part 7.
_MAX_OBSERVATION_CHARS = 2_000

# How many consecutive steps the loop tolerates a small model re-proposing
# an action already recorded as a failure before treating the episode as a
# stuck loop and ending it (GAVE_UP) rather than burning the whole step
# budget on repeats.
_MAX_CONSECUTIVE_BLOCKED_REPEATS = 3

# How many times a single step retries a malformed (non-parsing) model
# completion before the step is recorded as a hard error and the episode
# ends. Kept small: retries are extra inference the CPU budget can't
# afford to spend generously (Part 1/2/13).
_MAX_PARSE_RETRIES = 1


@dataclass
class LoopConfig:
    """Everything the loop needs that is NOT the goal/tools/model/memory
    itself -- the knobs a run config (config/example.yaml) pins for
    reproducibility (Part 18)."""

    step_budget: int = 30
    replan_interval: int = 5
    char_budget: int = 4_000
    temperature: float = 0.0
    seed: int | None = None
    max_tokens: int = 512


def _truncate_and_hash(text: str, limit: int) -> tuple[str, bool, str]:
    """Return (bounded_text, truncated_flag, sha256_of_full_text)."""
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    if len(text) <= limit:
        return text, False, digest
    return text[:limit] + f"...[truncated {len(text) - limit} chars]", True, digest


def _format_observation(result: ToolResult) -> str:
    if result.error:
        return f"ERROR: {result.error}"
    parts = [f"exit_code={result.exit_code}"]
    if result.stdout:
        parts.append(f"stdout:\n{result.stdout}")
    if result.stderr:
        parts.append(f"stderr:\n{result.stderr}")
    return "\n".join(parts)


@dataclass
class AgentLoop:
    """Runs one episode of the OBSERVE..NEXT loop to completion.

    Construction takes only Protocol-typed collaborators
    (``CompletionClient``, and a ``ToolRegistry`` built against an
    ``ActionChannel``) plus a ``Goal`` and a ``LoopConfig`` -- nothing here
    imports ``src.orchestrator``, so this class is fully unit-testable
    against fakes (see tests/test_smoke.py).
    """

    goal: Goal
    llm: CompletionClient
    tools: ToolRegistry
    config: LoopConfig = field(default_factory=LoopConfig)
    summarizer: Summarizer = field(default_factory=HeuristicSummarizer)

    def __post_init__(self) -> None:
        self.memory = StructuredMemory(self.goal)
        self._transcript: list[StepRecord] = []
        self._summary_events: list[str] = []
        self._last_observation: str | None = None
        self._consecutive_blocked = 0

    # -- public API ---------------------------------------------------

    def run(self) -> EpisodeResult:
        """Drive the loop to completion. Never raises for agent-level
        failure (malformed output, blocked repeat, tool error) -- those
        all become normal transcript entries or a GAVE_UP/ERROR outcome.
        Only truly unexpected exceptions propagate."""
        outcome = EpisodeOutcome.STEP_BUDGET_EXHAUSTED
        error: str | None = None

        for step_idx in range(self.config.step_budget):
            self.memory.state.step = step_idx

            self._maybe_replan(step_idx)
            self._maybe_summarize()

            try:
                record, done, terminal_outcome = self._run_one_step(step_idx)
            except Exception as exc:  # noqa: BLE001 - convert to ERROR outcome, don't crash the batch
                logger.exception("agent loop step %d raised unexpectedly", step_idx)
                outcome = EpisodeOutcome.ERROR
                error = repr(exc)
                break

            self._transcript.append(record)
            self.memory.advance_step()

            if done:
                outcome = terminal_outcome
                break
        else:
            outcome = EpisodeOutcome.STEP_BUDGET_EXHAUSTED

        return EpisodeResult(
            goal=self.goal,
            outcome=outcome,
            steps_taken=len(self._transcript),
            transcript=self._transcript,
            summary_events=self._summary_events,
            seed=self.config.seed,
            error=error,
        )

    # -- one iteration --------------------------------------------------

    def _run_one_step(self, step_idx: int) -> tuple[StepRecord, bool, EpisodeOutcome]:
        state_text = self.memory.render()
        prompt = render_step_prompt(
            goal=self.goal,
            state_text=state_text,
            tools_description=self.tools.describe(),
            last_observation=self._last_observation,
        )

        step_output = self._get_step_output(prompt)
        if step_output is None:
            # Exhausted parse retries: record a synthetic failed step and
            # end the episode rather than guessing at the model's intent.
            failed = ToolResult(ok=False, error="model output did not parse after retries")
            record = StepRecord(
                step=step_idx,
                output=AgentStepOutput(
                    hypothesis="(unparseable model output)",
                    plan="(none)",
                    action=_noop_call(),
                ),
                result=failed,
                evaluation=Evaluation.INCONCLUSIVE,
            )
            return record, True, EpisodeOutcome.ERROR

        if step_output.give_up:
            record = StepRecord(
                step=step_idx,
                output=step_output,
                result=ToolResult(ok=True, stdout="(give_up)"),
                evaluation=Evaluation.INCONCLUSIVE,
            )
            return record, True, EpisodeOutcome.GAVE_UP

        self.memory.add_open_questions(step_output.open_questions)

        # Failure-memory guard: block exact repeats of a known dead end
        # BEFORE they execute (Part 7's #1 small-model failure).
        if self.memory.has_tried(step_output.hypothesis, step_output.action):
            self._consecutive_blocked += 1
            record = StepRecord(
                step=step_idx,
                output=step_output,
                result=ToolResult(ok=False, error="blocked: repeats a known dead end"),
                evaluation=Evaluation.DENIED,
                blocked_repeat=True,
            )
            self._last_observation = (
                "Your proposed action repeats a known dead end and was NOT executed. "
                "Choose a genuinely different action."
            )
            if self._consecutive_blocked >= _MAX_CONSECUTIVE_BLOCKED_REPEATS:
                return record, True, EpisodeOutcome.GAVE_UP
            return record, False, EpisodeOutcome.STEP_BUDGET_EXHAUSTED

        self._consecutive_blocked = 0

        # ACTION + OBSERVATION
        result = self.tools.dispatch(step_output.action)
        bounded_stdout, truncated_out, hash_out = _truncate_and_hash(
            result.stdout, _MAX_OBSERVATION_CHARS
        )
        bounded_stderr, truncated_err, _ = _truncate_and_hash(
            result.stderr, _MAX_OBSERVATION_CHARS
        )
        result = result.model_copy(
            update={
                "stdout": bounded_stdout,
                "stderr": bounded_stderr,
                "truncated": truncated_out or truncated_err,
                "output_hash": hash_out,
            }
        )
        self._last_observation = _format_observation(result)

        # EVALUATE -- a cheap heuristic, not an extra inference call.
        evaluation = self._evaluate(result)

        # UPDATE BELIEF
        if evaluation == Evaluation.DENIED:
            reason = result.error or f"exit_code={result.exit_code}"
            self.memory.add_failure(step_output.hypothesis, step_output.action.summary(), reason)
        else:
            for fact_text in step_output.new_facts:
                self.memory.add_fact(fact_text, source=step_output.action.tool)
            if not step_output.new_facts and result.stdout:
                self.memory.add_fact(
                    f"{step_output.action.summary()} -> {result.stdout[:200]}",
                    source=step_output.action.tool,
                )

        record = StepRecord(
            step=step_idx,
            output=step_output,
            result=result,
            evaluation=evaluation,
        )

        # GOAL CHECK: only submit_flag can end an episode as solved.
        if step_output.action.tool == "submit_flag" and result.ok:
            solved = self._check_goal(step_output.action.args.get("flag", ""))
            if solved:
                return record, True, EpisodeOutcome.GOAL_REACHED
            self.memory.add_failure(
                step_output.hypothesis, step_output.action.summary(), "flag rejected"
            )

        return record, False, EpisodeOutcome.STEP_BUDGET_EXHAUSTED

    # -- helpers ----------------------------------------------------------

    def _get_step_output(self, prompt: str) -> AgentStepOutput | None:
        for attempt in range(_MAX_PARSE_RETRIES + 1):
            raw = self.llm.complete(
                prompt,
                temperature=self.config.temperature,
                seed=self.config.seed,
                max_tokens=self.config.max_tokens,
            )
            try:
                return parse_step_output(raw)
            except Exception as exc:  # noqa: BLE001 - model output, expect it to be malformed sometimes
                logger.warning("step output parse failed (attempt %d): %s", attempt, exc)
                prompt = prompt + (
                    f"\n\nYour previous response could not be parsed as the required "
                    f"JSON object ({exc}). Respond again with ONLY the JSON object."
                )
        return None

    def _evaluate(self, result: ToolResult) -> Evaluation:
        if result.error is not None:
            return Evaluation.DENIED
        if result.exit_code is None:
            return Evaluation.INCONCLUSIVE
        if result.exit_code == 0:
            return Evaluation.CONFIRMED
        return Evaluation.DENIED

    def _check_goal(self, flag: str) -> bool:
        """Score a submitted flag against the goal's success predicate.

        The v0 scaffold treats ``success_predicate`` as an exact-match
        string for a simple, deterministic smoke test. TODO: real
        challenges (Level 6/7) will want a callable/regex verifier
        supplied by the challenge definition rather than a literal string
        -- swap this method's body when challenges/** lands.
        """
        if self.goal.success_predicate is None:
            return False
        return flag.strip() == self.goal.success_predicate.strip()

    def _maybe_replan(self, step_idx: int) -> None:
        if step_idx == 0 or step_idx % self.config.replan_interval != 0:
            return
        prompt = render_replan_prompt(self.goal, self.memory.render())
        note = self.llm.complete(prompt, temperature=self.config.temperature, max_tokens=150)
        self.memory.set_strategy_note(note.strip())
        self._summary_events.append(f"step {step_idx}: replanned -> {note.strip()[:120]}")

    def _maybe_summarize(self) -> None:
        did = self.summarizer.maybe_summarize(self.memory.state, self.config.char_budget)
        if did:
            self._summary_events.append(
                f"step {self.memory.state.step}: summarized state (char budget {self.config.char_budget})"
            )


def _noop_call():
    from src.agent.models import ToolCall

    return ToolCall(tool="run_command", args={"command": "true"}, rationale="fallback after unparseable output")
