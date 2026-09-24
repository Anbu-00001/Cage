"""End-to-end test of the host<->guest wire protocol.

Runs the REAL in-guest daemon (vm/guest/action_daemon.py) over an AF_INET
loopback socket and drives it with the REAL channel framing helpers from
src/orchestrator/channel.py. AF_VSOCK needs a running VM, but the framing,
truncation, timeout, and error paths are transport-independent, so testing
over TCP exercises exactly the code that will run over vsock.

The daemon is loaded by file path (not imported as a package) on purpose:
it ships standalone into the guest image and must not depend on the src.*
tree.
"""

from __future__ import annotations

import importlib.util
import pathlib
import socket
import threading
import time

import pytest

from src.orchestrator.channel import parse_action_response, recv_json_line, send_json_line

_DAEMON_PATH = pathlib.Path(__file__).resolve().parents[1] / "vm" / "guest" / "action_daemon.py"


def _load_daemon():
    spec = importlib.util.spec_from_file_location("action_daemon", _DAEMON_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def daemon_addr():
    """Start the real daemon's serve loop on an ephemeral loopback port."""
    daemon = _load_daemon()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    addr = sock.getsockname()
    t = threading.Thread(target=daemon.serve, args=(sock,), daemon=True)
    t.start()
    yield addr
    sock.close()


def _client_exec(addr, command: str, timeout_s: float = 10.0):
    """Mirror of VsockChannel.execute over AF_INET: one connection per call."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_s + 5.0)
    s.connect(addr)
    try:
        start = time.monotonic()
        send_json_line(s, {"command": command, "timeout_s": timeout_s})
        data = recv_json_line(s)
        return parse_action_response(data, duration_s=time.monotonic() - start)
    finally:
        s.close()


def test_simple_command_succeeds(daemon_addr):
    result = _client_exec(daemon_addr, "echo hello")
    assert result.ok is True
    assert result.exit_code == 0
    assert "hello" in result.stdout


def test_nonzero_exit_is_not_an_error(daemon_addr):
    result = _client_exec(daemon_addr, "false")
    assert result.ok is False
    assert result.exit_code == 1
    assert result.error is None  # a failed guest command is data, not a transport error


def test_large_output_spans_multiple_recvs_and_truncates(daemon_addr):
    # ~200 KB of output forces the response frame past a single recv() chunk,
    # which is exactly the bug the framing loop fixes. It also exceeds the
    # daemon's 64 KB per-stream cap, so it must come back truncated.
    result = _client_exec(daemon_addr, "python3 -c \"print('x' * 200000)\"")
    assert result.exit_code == 0
    assert len(result.stdout.encode()) <= 64 * 1024
    assert result.stdout.startswith("x")


def test_timeout_is_reported(daemon_addr):
    result = _client_exec(daemon_addr, "sleep 5", timeout_s=0.5)
    assert result.exit_code is None
    assert result.error is not None
    assert "timed out" in result.error


def test_missing_command_field_is_rejected(daemon_addr):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect(daemon_addr)
    try:
        send_json_line(s, {"timeout_s": 1.0})  # no "command"
        data = recv_json_line(s)
    finally:
        s.close()
    assert data.get("error") is not None
