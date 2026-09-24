"""The typed tool registry.

Part 7 / Part 20 of the design doc: "a few great tools beats twenty" and
"more tools = more ways to emit a broken call." Every tool declares a
pydantic argument schema; the registry validates ``ToolCall.args`` against
it *before* the tool ever touches the action channel, so a small model's
near-miss JSON (a string where an int was expected, an unknown field) fails
fast with a legible error instead of corrupting a guest session.

Tool set (deliberately small, matching Levels 0-3 of the cage):
    run_command    Execute one shell command in the guest.
    read_file      Read (a bounded slice of) a file.
    list_dir       List a directory.
    check_port     TCP-connect probe of host:port from inside the guest
                   (used to map the network topology, Level 3).
    submit_flag    Declare the goal reached with a candidate flag/value;
                   this is the ONLY way an episode can end in
                   ``GOAL_REACHED`` -- the loop never pattern-matches the
                   goal out of free text.

No sub-agents live here (Part 7: "process/network inspectors as sub-agents
-- No. Make them tools, not sub-agents.") -- every one of these is a single
cheap, typed, synchronous call.
"""

from __future__ import annotations

import abc

from pydantic import BaseModel, ValidationError

from src.agent.interfaces import ActionChannel
from src.agent.models import ToolCall, ToolResult


class ToolArgs(BaseModel):
    """Base class for per-tool argument schemas. Subclasses add fields;
    pydantic rejects unknown/malformed fields at construction time."""

    model_config = {"extra": "forbid"}


class RunCommandArgs(ToolArgs):
    command: str
    timeout_s: float = 10.0


class ReadFileArgs(ToolArgs):
    path: str
    max_bytes: int = 4096


class ListDirArgs(ToolArgs):
    path: str = "."


class CheckPortArgs(ToolArgs):
    host: str
    port: int
    timeout_s: float = 3.0


class SubmitFlagArgs(ToolArgs):
    flag: str


class Tool(abc.ABC):
    """A single typed capability. Subclasses translate validated args into
    one ``ActionChannel.execute`` call (or a small, fixed sequence of
    them) and return a ``ToolResult`` -- never raise for guest-side
    failure, only for transport failure (that distinction is the
    ``ActionChannel`` contract, see interfaces.py)."""

    name: str
    description: str
    args_schema: type[ToolArgs]

    def __init__(self, channel: ActionChannel) -> None:
        self._channel = channel

    @abc.abstractmethod
    def run(self, args: ToolArgs) -> ToolResult: ...


class RunCommandTool(Tool):
    name = "run_command"
    description = (
        "Execute a single shell command in the guest cage and capture "
        "stdout, stderr, and exit code. Prefer the more specific tools "
        "(read_file, list_dir, check_port) when they fit -- they are "
        "cheaper to reason about and to score."
    )
    args_schema = RunCommandArgs

    def run(self, args: RunCommandArgs) -> ToolResult:  # type: ignore[override]
        return self._channel.execute(args.command, timeout_s=args.timeout_s)


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read up to max_bytes of a file's contents from the guest."
    args_schema = ReadFileArgs

    def run(self, args: ReadFileArgs) -> ToolResult:  # type: ignore[override]
        # head -c bounds the read guest-side so a huge/streaming file can
        # never blow the context budget on its way back to the host.
        cmd = f"head -c {int(args.max_bytes)} -- {_shquote(args.path)}"
        return self._channel.execute(cmd, timeout_s=10.0)


class ListDirTool(Tool):
    name = "list_dir"
    description = "List directory entries (long form) at a path in the guest."
    args_schema = ListDirArgs

    def run(self, args: ListDirArgs) -> ToolResult:  # type: ignore[override]
        cmd = f"ls -la -- {_shquote(args.path)}"
        return self._channel.execute(cmd, timeout_s=10.0)


class CheckPortTool(Tool):
    name = "check_port"
    description = (
        "Probe whether host:port accepts a TCP connection from inside the "
        "guest (network topology mapping, Level 3)."
    )
    args_schema = CheckPortArgs

    def run(self, args: CheckPortArgs) -> ToolResult:  # type: ignore[override]
        # A tiny bash /dev/tcp probe: no extra guest packages required.
        cmd = (
            f"timeout {args.timeout_s:g} bash -c "
            f"'cat < /dev/null > /dev/tcp/{args.host}/{args.port}' "
            f"&& echo OPEN || echo CLOSED"
        )
        return self._channel.execute(cmd, timeout_s=args.timeout_s + 2.0)


class SubmitFlagTool(Tool):
    name = "submit_flag"
    description = (
        "Declare the goal reached with a candidate flag/value. This is the "
        "only action that can end an episode as solved -- the host scores "
        "it against the goal's success predicate, the model is never told "
        "the predicate directly."
    )
    args_schema = SubmitFlagArgs

    def run(self, args: SubmitFlagArgs) -> ToolResult:  # type: ignore[override]
        # submit_flag never touches the channel: scoring happens host-side
        # in Episode, against Goal.success_predicate. Here we just echo the
        # claim back so it lands in the transcript uniformly with every
        # other tool's ToolResult.
        return ToolResult(ok=True, exit_code=0, stdout=args.flag, duration_s=0.0)


def _shquote(s: str) -> str:
    """Minimal POSIX single-quote escaping for guest shell commands."""
    return "'" + s.replace("'", "'\\''") + "'"


class ToolRegistry:
    """Validates and dispatches ``ToolCall``s against the registered tools.

    Two-stage validation, matching the docstring at module top: (1) does
    the tool name exist, (2) do the args parse against that tool's own
    schema. Both failure modes return a normal ``ToolResult(ok=False,
    error=...)`` rather than raising, so a malformed model output costs
    exactly one wasted step, not a crashed episode.
    """

    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {t.name: t for t in tools}

    @classmethod
    def default(cls, channel: ActionChannel) -> "ToolRegistry":
        """The default, deliberately small tool set (Levels 0-3)."""
        return cls(
            [
                RunCommandTool(channel),
                ReadFileTool(channel),
                ListDirTool(channel),
                CheckPortTool(channel),
                SubmitFlagTool(channel),
            ]
        )

    def names(self) -> list[str]:
        return list(self._tools)

    def describe(self) -> str:
        """Render tool name/args/description for the prompt (prompts.py)."""
        lines = []
        for tool in self._tools.values():
            fields = ", ".join(tool.args_schema.model_fields)
            lines.append(f"- {tool.name}({fields}): {tool.description}")
        return "\n".join(lines)

    def dispatch(self, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.tool)
        if tool is None:
            return ToolResult(
                ok=False,
                error=f"unknown tool {call.tool!r}; known tools: {self.names()}",
            )
        try:
            parsed_args = tool.args_schema.model_validate(call.args)
        except ValidationError as exc:
            return ToolResult(ok=False, error=f"bad args for {call.tool}: {exc}")
        try:
            return tool.run(parsed_args)
        except Exception as exc:  # noqa: BLE001 - transport failure, not guest failure
            return ToolResult(ok=False, error=f"channel error: {exc!r}")
