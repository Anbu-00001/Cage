"""The host<->guest action channel abstraction.

Architecture C (Part 3/5/24 of the design doc) is explicit that the guest
is reached only through a "narrow, logged" pipe -- SSH or virtio-vsock --
never a filesystem bridge, clipboard, or USB/GPU passthrough. This module
defines that pipe as one small interface
(``src.agent.interfaces.ActionChannel``: a single ``execute()`` method) and
provides three implementations:

``LocalMockChannel``  In-memory, deterministic, no subprocess/VM/network
                      at all. What the smoke test and unit tests use.
``SSHChannel``        Real transport stub over the ``ssh`` CLI. Runnable
                      against an actual guest once one exists; every
                      guest-specific assumption (host key policy, key
                      path, user) is a config field, not a hardcoded
                      value.
``VsockChannel``      Real transport stub over ``AF_VSOCK`` with a minimal
                      newline-delimited JSON wire protocol. Needs a
                      matching listener inside the guest (owned by the
                      VM/challenge lane, not this one) before it can
                      actually be exercised -- marked TODO accordingly.

All three log every command + result (Part 19: "a narrow, logged channel")
via the stdlib ``logging`` module at INFO level, so the boundary the whole
safety story rests on ("the host is sacred, the channel is the only way
across it") has an audit trail for free.
"""

from __future__ import annotations

import json
import logging
import socket
import subprocess
import time
from dataclasses import dataclass, field

from src.agent.models import ToolResult

logger = logging.getLogger("cage.channel")


def _log_and_return(command: str, result: ToolResult, transport: str) -> ToolResult:
    logger.info(
        "[%s] command=%r exit_code=%s ok=%s duration_s=%.3f",
        transport,
        command,
        result.exit_code,
        result.ok,
        result.duration_s,
    )
    return result


# -- wire protocol (shared shape with vm/guest/action_daemon.py) --------------
# One request line then one response line, each a UTF-8 JSON object terminated
# by '\n'. Stream sockets (both AF_VSOCK and, in tests, AF_INET) do NOT preserve
# message boundaries: a single recv() can return a partial line or several lines
# glued together. The original single-recv read was therefore a latent bug that
# would truncate any guest output larger than one segment. Both sides must read
# until the newline. WIRE_MAX_BYTES caps the read so a chatty or hostile guest
# cannot make the host reader allocate without bound.
WIRE_MAX_BYTES = 16 * 1024 * 1024


def send_json_line(sock: socket.socket, obj: dict) -> None:
    """Send one JSON object as a single newline-terminated frame."""
    sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))


def recv_json_line(sock: socket.socket, *, max_bytes: int = WIRE_MAX_BYTES) -> dict:
    """Read one newline-terminated JSON frame, tolerant of partial recvs."""
    buf = bytearray()
    while b"\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("channel closed before a full line was received")
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise ValueError(f"frame exceeded {max_bytes} bytes without a newline")
    line = bytes(buf).split(b"\n", 1)[0]
    return json.loads(line.decode("utf-8", errors="replace"))


def parse_action_response(data: dict, *, duration_s: float) -> ToolResult:
    """Turn a guest daemon's response object into a ``ToolResult``. Shared by
    the real channel and the wire-protocol tests so both agree on the mapping."""
    return ToolResult(
        ok=data.get("exit_code", 1) == 0,
        exit_code=data.get("exit_code"),
        stdout=data.get("stdout", ""),
        stderr=data.get("stderr", ""),
        error=data.get("error"),
        duration_s=duration_s,
    )


@dataclass
class LocalMockChannel:
    """A fully in-memory, deterministic fake of the guest, for tests and
    the no-VM smoke run.

    ``responses`` maps an EXACT command string to the ``ToolResult`` it
    should produce -- this is not a shell emulator, it's a fixture. Any
    command not present in ``responses`` returns ``default_response``
    (by default, a clean "command not found"-shaped failure), which keeps
    unexpected tool calls from silently succeeding in a test.
    """

    responses: dict[str, ToolResult] = field(default_factory=dict)
    default_response: ToolResult = field(
        default_factory=lambda: ToolResult(ok=False, exit_code=127, error="command not found (mock channel)")
    )

    def execute(self, command: str, timeout_s: float = 10.0) -> ToolResult:
        start = time.monotonic()
        result = self.responses.get(command, self.default_response)
        result = result.model_copy(update={"duration_s": time.monotonic() - start})
        return _log_and_return(command, result, "local_mock")


@dataclass
class SSHChannel:
    """Runs one command per call over ``ssh``, non-interactively.

    TODO(hardening, before pointing this at a real cage):
      - pin ``StrictHostKeyChecking``/``known_hosts`` per Part 19 (no
        blind ``UserKnownHostsFile=/dev/null`` in anything beyond a
        throwaway lab guest);
      - the guest should only ever hold a *planted fake* credential /
        key, never a host secret (Part 19: "no real credentials, keys, or
        secrets near the guest");
      - consider a persistent ``ControlMaster`` socket to avoid paying a
        full SSH handshake per tool call, which would otherwise dominate
        per-step latency on a 2-P-core host.
    """

    host: str
    port: int = 22
    user: str = "researcher"
    key_path: str | None = None

    def execute(self, command: str, timeout_s: float = 10.0) -> ToolResult:
        ssh_cmd = [
            "ssh",
            "-p",
            str(self.port),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            # TODO: replace with a pinned known_hosts entry for the golden
            # image once it exists (see module docstring).
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]
        if self.key_path:
            ssh_cmd += ["-i", self.key_path]
        ssh_cmd += [f"{self.user}@{self.host}", command]

        start = time.monotonic()
        try:
            proc = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            result = ToolResult(
                ok=proc.returncode == 0,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_s=time.monotonic() - start,
            )
        except subprocess.TimeoutExpired:
            result = ToolResult(
                ok=False,
                error=f"ssh command timed out after {timeout_s}s",
                duration_s=time.monotonic() - start,
            )
        except OSError as exc:
            result = ToolResult(ok=False, error=f"ssh invocation failed: {exc}", duration_s=time.monotonic() - start)
        return _log_and_return(command, result, "ssh")


@dataclass
class VsockChannel:
    """Sends one command per call over ``AF_VSOCK`` using a minimal
    newline-delimited JSON wire protocol:

        request:  {"command": "...", "timeout_s": 10.0}\\n
        response: {"exit_code": 0, "stdout": "...", "stderr": "..."}\\n

    The guest-side counterpart now lives at ``vm/guest/action_daemon.py``:
    a tiny stdlib-only listener that speaks exactly this protocol. Bring
    the guest up (see vm/scripts/), start the daemon on ``(cid, port)``,
    and this channel talks to it. If the daemon isn't running, ``execute``
    fails with a connection error -- the correct, honest behaviour rather
    than silently pretending to succeed.

    vsock is preferred over SSH for the "real" transport per Part 5: it
    never touches a network stack at all (isolation by construction, not
    by firewall rule), and it avoids paying an SSH handshake per tool call
    on a 2-P-core host.
    """

    cid: int
    port: int = 9000
    recv_bufsize: int = 65536

    def execute(self, command: str, timeout_s: float = 10.0) -> ToolResult:
        start = time.monotonic()
        sock: socket.socket | None = None
        try:
            sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
            # Give the guest a little slack beyond the command's own budget so
            # a command that runs right up to timeout_s still gets its result
            # back rather than tripping a transport timeout.
            sock.settimeout(timeout_s + 5.0)
            sock.connect((self.cid, self.port))
            send_json_line(sock, {"command": command, "timeout_s": timeout_s})
            data = recv_json_line(sock)
            result = parse_action_response(data, duration_s=time.monotonic() - start)
        except AttributeError:
            # socket.AF_VSOCK does not exist on non-Linux platforms.
            result = ToolResult(
                ok=False,
                error="AF_VSOCK not available on this platform",
                duration_s=time.monotonic() - start,
            )
        except (OSError, ValueError) as exc:
            # OSError: connection refused/timeout (guest daemon not running).
            # ValueError: malformed/oversized response frame (JSONDecodeError
            # is a ValueError subclass). Both are transport-level, surfaced
            # as an errored ToolResult, never a raise into the agent loop.
            result = ToolResult(
                ok=False,
                error=f"vsock transport/protocol error (is the guest daemon running?): {exc}",
                duration_s=time.monotonic() - start,
            )
        finally:
            if sock is not None:
                sock.close()
        return _log_and_return(command, result, "vsock")


def build_channel(kind: str, **kwargs):
    """Factory mirroring ``VMConfig.channel``. Kept separate from
    ``RunConfig`` so tests can build a channel directly without YAML."""
    if kind == "local_mock":
        return LocalMockChannel(**kwargs)
    if kind == "ssh":
        return SSHChannel(**kwargs)
    if kind == "vsock":
        return VsockChannel(**kwargs)
    raise ValueError(f"unknown channel kind: {kind!r}")
