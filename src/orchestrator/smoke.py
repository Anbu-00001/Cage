"""The fixture data behind the no-model, no-VM smoke run.

Shared by ``src.orchestrator.cli`` (``--smoke``) and ``tests/test_smoke.py``
(via pytest) so there is exactly one definition of "what the fake agent
says" and "what the fake guest returns" -- not two copies that can drift.

The scripted trace below is a small but *real* exercise of the loop: it
deliberately includes one wrong guess that fails (denied -> recorded to
failure memory) followed by an exact repeat of that same wrong guess
(blocked by failure memory without touching the channel again), before the
correct path is found and the goal is submitted -- see the inline comments
for the step-by-step story. It pairs with ``episode.make_smoke_goal()``,
whose success predicate is the literal string ``"hunter2"``.
"""

from __future__ import annotations

from src.agent.models import ToolResult


def smoke_channel_responses() -> dict[str, ToolResult]:
    """Exact-match command -> result fixture for ``LocalMockChannel``,
    covering exactly the guest-shell commands the scripted model in
    :func:`smoke_model_script` will issue (see src/agent/tools.py for how
    each typed tool renders its shell command)."""
    return {
        "ls -la -- '.'": ToolResult(
            ok=True,
            exit_code=0,
            stdout=(
                "total 8\n"
                "-rw-r--r-- 1 researcher researcher   42 Jan  1 00:00 README.txt\n"
                "-rw-r--r-- 1 researcher researcher   10 Jan  1 00:00 decoy.txt\n"
                "-rw-r--r-- 1 researcher researcher    7 Jan  1 00:00 secret.txt\n"
            ),
        ),
        "head -c 4096 -- 'wrong.txt'": ToolResult(
            ok=False,
            exit_code=1,
            stderr="head: cannot open 'wrong.txt' for reading: No such file or directory\n",
        ),
        "head -c 4096 -- 'secret.txt'": ToolResult(ok=True, exit_code=0, stdout="hunter2"),
    }


def smoke_model_script() -> list[str]:
    """Five scripted raw completions -> five ``AgentStepOutput``s: list the
    directory, guess wrong, repeat the exact same wrong guess (exercising
    the failure-memory block), read the real file, submit the flag."""
    return [
        # Step 0 -- OBSERVE (nothing yet) -> enumerate the filesystem.
        # Wrapped in a ```json fence to prove parse_step_output() strips
        # markdown fencing, which small local models reliably emit despite
        # being told not to.
        """```json
{
  "hypothesis": "The secret lives in a file somewhere under the current directory.",
  "plan": "List the current directory to see what files exist.",
  "action": {"tool": "list_dir", "args": {"path": "."}, "rationale": "enumerate before guessing"},
  "new_facts": [],
  "open_questions": ["which file actually holds the secret?"],
  "give_up": false
}
```""",
        # Step 1 -- saw README.txt/decoy.txt/secret.txt, but (small-model
        # realism) guesses a plausible-sounding filename that doesn't
        # exist rather than the obviously-named one. This fails.
        """{
  "hypothesis": "wrong.txt might hold the secret value.",
  "plan": "Read wrong.txt.",
  "action": {"tool": "read_file", "args": {"path": "wrong.txt"}, "rationale": "check a likely-named file"},
  "new_facts": ["directory listing shows README.txt, decoy.txt, secret.txt"],
  "open_questions": [],
  "give_up": false
}""",
        # Step 2 -- deliberately re-proposes the EXACT same (hypothesis,
        # action) pair as step 1. The loop's failure-memory guard must
        # block this before it reaches the channel at all.
        """{
  "hypothesis": "wrong.txt might hold the secret value.",
  "plan": "Read wrong.txt.",
  "action": {"tool": "read_file", "args": {"path": "wrong.txt"}, "rationale": "check a likely-named file"},
  "new_facts": [],
  "open_questions": [],
  "give_up": false
}""",
        # Step 3 -- corrects course to the obviously-named file.
        """{
  "hypothesis": "secret.txt is named for exactly what we're looking for.",
  "plan": "Read secret.txt.",
  "action": {"tool": "read_file", "args": {"path": "secret.txt"}, "rationale": "try the obviously-named file"},
  "new_facts": [],
  "open_questions": [],
  "give_up": false
}""",
        # Step 4 -- submit the discovered value as the flag.
        """{
  "hypothesis": "secret.txt's contents are the flag.",
  "plan": "Submit the flag.",
  "action": {"tool": "submit_flag", "args": {"flag": "hunter2"}, "rationale": "goal satisfied"},
  "new_facts": ["secret.txt contains the flag value"],
  "open_questions": [],
  "give_up": false
}""",
    ]
