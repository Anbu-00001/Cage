"""Prompt templates.

Plain f-strings on purpose -- no templating dependency for something this
small, and it keeps the exact prompt text grep-able and diffable (Part 18:
"versioned prompt templates" is one of the pinned reproducibility
artifacts).

Two prompts:

``render_step_prompt``   The per-step call: state + tools -> one
                          ``AgentStepOutput`` JSON object. This is the
                          call that happens EVERY step.
``render_replan_prompt`` The periodic strategic review: state -> a short
                          free-text strategy note folded back into state
                          for subsequent step prompts. This only happens
                          every ``replan_interval`` steps (see loop.py) --
                          "periodic re-plan, not every step" (Part 7).
"""

from __future__ import annotations

from src.agent.models import AgentStepOutput, Goal

_STEP_SCHEMA_HINT = """Respond with EXACTLY one JSON object, no prose before or after it, matching:
{
  "hypothesis": "<what you currently believe and are testing>",
  "plan": "<the single next step, one sentence>",
  "action": {"tool": "<tool name>", "args": {...}, "rationale": "<one line>"},
  "new_facts": ["<fact learned from the PREVIOUS observation, if any>"],
  "open_questions": ["<question you still need to resolve>"],
  "give_up": false
}"""


def render_step_prompt(
    goal: Goal,
    state_text: str,
    tools_description: str,
    last_observation: str | None,
) -> str:
    """Build the per-step prompt: OBSERVE (last_observation) + STATE
    (state_text) + instructions to emit HYPOTHESIS/PLAN/ACTION as JSON."""
    obs_block = (
        f"LAST OBSERVATION:\n{last_observation}\n\n" if last_observation else ""
    )
    return f"""You are an autonomous security-research agent operating inside a \
sealed, disposable Linux VM that the researcher built as a lab exercise. \
Every boundary in this environment was engineered on purpose for you to \
discover and reason about. You may only act through the tools listed below.

GOAL (level {goal.level}): {goal.description}

AVAILABLE TOOLS:
{tools_description}

{obs_block}CURRENT BELIEF STATE:
{state_text}

Pick exactly ONE next action that cheaply tests your current hypothesis. \
Do not repeat anything listed under KNOWN DEAD ENDS above -- pick something \
that could not have already been ruled out by them. If you believe the \
goal is genuinely unreachable after real effort, set "give_up": true \
instead of flailing.

{_STEP_SCHEMA_HINT}
"""


def render_replan_prompt(goal: Goal, state_text: str) -> str:
    """Build the periodic strategic-review prompt. Cheap on purpose: a
    short free-text answer, not another structured tool call -- this is
    the "separate planner call" the design doc says to use sparingly."""
    return f"""You are reviewing progress on a security-research lab goal, not \
choosing the next single action.

GOAL (level {goal.level}): {goal.description}

BELIEF STATE SO FAR:
{state_text}

In 2-3 sentences: what is the current best strategic approach, given what \
has and has not worked so far? Name the class of dead ends to stop \
exploring and the class of leads worth pursuing next. Do not restate facts \
verbatim -- synthesize.
"""


def parse_step_output(raw: str) -> AgentStepOutput:
    """Parse a model completion into a validated ``AgentStepOutput``.

    Small models reliably wrap JSON in ```` ```json ... ``` ```` fences or
    prepend a sentence despite instructions; this does the minimal robust
    extraction (first ``{`` to last ``}``) before handing off to pydantic,
    which is the layer that actually enforces the schema. Raises
    ``pydantic.ValidationError`` (or ``ValueError`` if no JSON object is
    found at all) on failure -- callers (loop.py) decide the retry policy.
    """
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"no JSON object found in completion: {raw!r}")
    candidate = text[start : end + 1]
    return AgentStepOutput.model_validate_json(candidate)
