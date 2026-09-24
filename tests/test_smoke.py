"""Smoke test: proves the plumbing end-to-end with NO model and NO VM.

Constructs the full config -> Episode -> AgentLoop -> tools -> memory
chain against a scripted ``FakeLLMClient`` and an in-memory
``LocalMockChannel`` (src/orchestrator/smoke.py), and checks that:

  1. the episode reaches GOAL_REACHED via the scripted trace,
  2. the deliberately-repeated wrong guess is blocked by failure memory
     instead of hitting the channel a second time (Part 7's "#1
     small-model failure" prevention),
  3. a malformed tool call is rejected by the tool registry cleanly
     (never raises out of the loop),
  4. the heuristic summarizer actually folds old state when over budget.

Two ways to run this:

    pytest tests/test_smoke.py -v
    python3 -m tests.test_smoke        # no pytest required

Both exercise the identical assertions; the ``__main__`` block below is a
thin manual runner so "python -m works with no model present" holds even
in an environment without pytest installed.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from src.agent.loop import LoopConfig
from src.agent.memory import StructuredMemory
from src.agent.models import EpisodeOutcome, Evaluation, Goal, ToolCall, ToolResult
from src.agent.summarizer import HeuristicSummarizer
from src.agent.tools import ToolRegistry
from src.orchestrator.channel import LocalMockChannel
from src.orchestrator.config import RunConfig
from src.orchestrator.episode import Episode, make_smoke_goal
from src.orchestrator.smoke import smoke_channel_responses, smoke_model_script


def _build_smoke_episode(transcript_dir: Path) -> Episode:
    config = RunConfig(name="smoke-test", seed=0, transcript_dir=str(transcript_dir))
    channel = LocalMockChannel(responses=smoke_channel_responses())
    return Episode.from_config(
        config, make_smoke_goal(), channel=channel, fake_script=smoke_model_script()
    )


def test_smoke_episode_reaches_goal(tmp_path: Path) -> None:
    episode = _build_smoke_episode(tmp_path)
    result = episode.run()

    assert result.outcome == EpisodeOutcome.GOAL_REACHED
    assert result.steps_taken == 5
    assert result.transcript[-1].output.action.tool == "submit_flag"
    assert result.transcript[-1].evaluation == Evaluation.CONFIRMED

    # the transcript was actually persisted (Part 18: full transcripts).
    out_file = tmp_path / "smoke-test-seed0.json"
    assert out_file.exists()
    assert '"outcome":"goal_reached"' in out_file.read_text().replace(" ", "").replace("\n", "")


def test_failure_memory_blocks_exact_repeat(tmp_path: Path) -> None:
    episode = _build_smoke_episode(tmp_path)
    result = episode.run()

    steps = result.transcript
    # step 1: wrong.txt read attempt executes and is denied.
    assert steps[1].evaluation == Evaluation.DENIED
    assert steps[1].blocked_repeat is False
    # step 2: the identical (hypothesis, action) pair is blocked BEFORE
    # ever reaching the channel again.
    assert steps[2].blocked_repeat is True
    assert steps[2].result.ok is False

    # exactly one FailureRecord was ever stored for that pair, not two --
    # the dedup signature in StructuredMemory.add_failure did its job.
    memory = StructuredMemory(episode.goal)
    memory.add_failure("wrong.txt might hold the secret value.", "read_file(path='wrong.txt')", "not found")
    dup = memory.add_failure(
        "wrong.txt might hold the secret value.", "read_file(path='wrong.txt')", "not found again"
    )
    assert dup is None
    assert len(memory.state.failures) == 1


def test_tool_registry_rejects_bad_args_without_raising() -> None:
    channel = LocalMockChannel(responses={})
    registry = ToolRegistry.default(channel)

    result = registry.dispatch(ToolCall(tool="read_file", args={"path": 123}))  # wrong type
    assert result.ok is False
    assert "bad args" in (result.error or "")

    result = registry.dispatch(ToolCall(tool="nonexistent_tool", args={}))
    assert result.ok is False
    assert "unknown tool" in (result.error or "")


def test_heuristic_summarizer_folds_old_state() -> None:
    goal = Goal(id="g", description="d", level=0)
    memory = StructuredMemory(goal)
    for i in range(20):
        memory.add_fact(f"fact number {i} " * 5, source="test")

    summarizer = HeuristicSummarizer(keep_recent_facts=3, keep_recent_failures=3)
    did_summarize = summarizer.maybe_summarize(memory.state, char_budget=200)

    assert did_summarize is True
    assert len(memory.state.facts) == 3  # only the most recent kept verbatim
    assert "fact number 0" in memory.state.summary  # older facts folded in


def _nudge_episode(transcript_dir: Path, *, submit_nudge: bool) -> Episode:
    """One-file episode whose read surfaces a flag-shaped token, used to
    exercise the optional submit-nudge scaffold (the found_not_submitted
    lever). The scripted model reads the file but -- realistically for the
    3B we observed -- does NOT submit; it re-reads instead. So the episode
    only reaches the flag if the nudge pushes it to submit_flag."""
    from src.orchestrator.config import LoopSettingsConfig

    config = RunConfig(
        name=f"nudge-{submit_nudge}",
        seed=0,
        transcript_dir=str(transcript_dir),
        loop=LoopSettingsConfig(step_budget=4, replan_interval=10, submit_nudge=submit_nudge),
    )
    channel = LocalMockChannel(
        responses={"head -c 4096 -- 'creds.txt'": ToolResult(
            ok=True, exit_code=0, stdout="SESSION_TOKEN=FLAG{found_it_9x}")}
    )
    read = (
        '{"hypothesis":"creds.txt may hold it.","plan":"read it.",'
        '"action":{"tool":"read_file","args":{"path":"creds.txt"},"rationale":"read"},'
        '"new_facts":[],"open_questions":[],"give_up":false}'
    )
    goal = Goal(id="nudge", level=1, description="find the token", success_predicate="FLAG{found_it_9x}")
    # Model only ever proposes reads (never submit_flag on its own): the
    # unproductive-repeat guard blocks re-reads, so absent the nudge it can
    # never reach the flag; with the nudge, step 1's prompt carries the
    # submit redirect.
    return Episode.from_config(config, goal, channel=channel, fake_script=[read] * 4)


def test_submit_nudge_fires_when_enabled(tmp_path: Path) -> None:
    episode = _nudge_episode(tmp_path, submit_nudge=True)
    episode.run()
    # The nudge is appended to the observation and thus shows up in the
    # NEXT step's rendered prompt (FakeLLMClient records every prompt).
    calls = getattr(episode.llm, "calls")
    assert any("submit_flag(flag=\"FLAG{found_it_9x}\")" in p for p in calls[1:]), \
        "submit-nudge text should reach a later prompt when the lever is on"


def test_submit_nudge_silent_when_disabled(tmp_path: Path) -> None:
    episode = _nudge_episode(tmp_path, submit_nudge=False)
    episode.run()
    calls = getattr(episode.llm, "calls")
    assert not any("submit it NOW" in p for p in calls), \
        "no nudge text should appear when the lever is off (baseline)"


def test_loop_config_defaults_match_design_doc_posture() -> None:
    # Part 7/17: hard step budget, periodic (not per-step) re-plan,
    # temperature 0 by default when measuring capability not creativity.
    config = LoopConfig()
    assert config.step_budget > 0
    assert config.replan_interval > 1
    assert config.temperature == 0.0


_TESTS = [
    test_smoke_episode_reaches_goal,
    test_failure_memory_blocks_exact_repeat,
    test_tool_registry_rejects_bad_args_without_raising,
    test_heuristic_summarizer_folds_old_state,
    test_submit_nudge_fires_when_enabled,
    test_submit_nudge_silent_when_disabled,
    test_loop_config_defaults_match_design_doc_posture,
]


def _run_without_pytest() -> int:
    """Manual runner so `python3 -m tests.test_smoke` needs no pytest and
    no model/VM -- pure plumbing proof, per the project brief."""
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for test_fn in _TESTS:
            name = test_fn.__name__
            try:
                if "tmp_path" in test_fn.__code__.co_varnames[: test_fn.__code__.co_argcount]:
                    test_fn(Path(tmp) / name)
                else:
                    test_fn()
                print(f"PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"ERROR {name}: {exc!r}")
    total = len(_TESTS)
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_without_pytest())
