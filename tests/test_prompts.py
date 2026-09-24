"""Tests for the step-prompt builder, focused on the CLOSURE CHECK ablation
toggle (docs/RESULTS.md §4.2) that the eval harness flips to measure the fix's
causal effect on solve rate."""

from __future__ import annotations

from src.agent.models import Goal
from src.agent.prompts import render_step_prompt


def _goal() -> Goal:
    return Goal(id="g", level=2, description="find the token", success_predicate="FLAG{x}")


def test_closure_block_present_by_default() -> None:
    p = render_step_prompt(_goal(), state_text="STEP: 0", tools_description="- t",
                           last_observation=None)
    assert "CLOSURE CHECK" in p
    assert "your single next action" in p.lower()
    assert "submit_flag" in p


def test_closure_block_absent_when_ablated() -> None:
    p = render_step_prompt(_goal(), state_text="STEP: 0", tools_description="- t",
                           last_observation=None, closure_prompt=False)
    assert "CLOSURE CHECK" not in p
    # baseline still gives the exploration instruction and the give-up escape
    assert "Pick exactly ONE next action" in p
    assert "give_up" in p


def test_both_variants_include_goal_and_tools() -> None:
    for closure in (True, False):
        p = render_step_prompt(_goal(), state_text="STEP: 0",
                               tools_description="- run_command", last_observation="obs",
                               closure_prompt=closure)
        assert "find the token" in p
        assert "run_command" in p
        assert "LAST OBSERVATION" in p
