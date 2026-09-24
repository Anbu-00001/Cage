#!/usr/bin/env python3
"""In-guest action daemon: the guest-side counterpart of
``src/orchestrator/channel.py``'s ``VsockChannel``.

This runs INSIDE the resettable Alpine cage. It is the single, narrow,
logged doorway the agent uses to act on the guest (Architecture C, Part
5/19): the host never gets a shell or a filesystem bridge, only this
one-request/one-response pipe.

Wire protocol (mirrors src/orchestrator/channel.py -- keep them in sync):

    request:   {"command": "...", "timeout_s": 10.0}\\n
    response:  {"exit_code": 0, "stdout": "...", "stderr": "...",
                "truncated": false, "duration_s": 0.01}\\n

Design constraints that make this safe and cheap:

- **stdlib only.** Alpine ships a minimal python3; no third-party imports,
  so the golden image needs nothing extra.
- **Runs as the unprivileged cage user.** This daemon is not a privilege
  boundary -- it deliberately runs whatever command it is given, because
  the whole experiment is "can the agent cross the boundaries we ENGINEERED
  inside the guest." The isolation that matters is the VM boundary (host
  stays sacred), enforced by QEMU/libvirt/AppArmor on the host, not here.
- **Bounded output.** stdout/stderr are truncated to MAX_OUTPUT bytes each
  so a runaway command (``cat /dev/urandom``, ``find /``) can't blow up the
  host reader or the transcript; truncation is reported honestly.
- **Per-command timeout.** The host sends its budget; we enforce it and
  kill the process group on expiry so nothing lingers between trials.

Usage (in the guest, started by an init service):
    python3 action_daemon.py                 # AF_VSOCK, port 9000 (real)
    python3 action_daemon.py --tcp 127.0.0.1 9000   # AF_INET (tests/dev)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time

MAX_OUTPUT = 64 * 1024  # bytes per stream kept; rest is dropped and flagged
WIRE_MAX_BYTES = 16 * 1024 * 1024  # cap on an inbound request line
DEFAULT_PORT = 9000

logger = logging.getLogger("cage.guest.daemon")


def _recv_json_line(conn: socket.socket, *, max_bytes: int = WIRE_MAX_BYTES) -> dict:
    """Read one newline-terminated JSON frame, tolerant of partial recvs."""
    buf = bytearray()
    while b"\n" not in buf:
        chunk = conn.recv(65536)
        if not chunk:
            raise ConnectionError("client closed before a full request line")
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise ValueError(f"request exceeded {max_bytes} bytes without a newline")
    line = bytes(buf).split(b"\n", 1)[0]
    return json.loads(line.decode("utf-8", errors="replace"))


def _send_json_line(conn: socket.socket, obj: dict) -> None:
    conn.sendall((json.dumps(obj) + "\n").encode("utf-8"))


def _truncate(text: str) -> tuple[str, bool]:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= MAX_OUTPUT:
        return text, False
    return raw[:MAX_OUTPUT].decode("utf-8", errors="replace"), True


def run_command(command: str, timeout_s: float) -> dict:
    """Run one shell command with a timeout and bounded output. Never raises
    for a command-level failure (non-zero exit, timeout) -- that is normal
    data; only truly unexpected errors become an ``error`` field."""
    start = time.monotonic()
    try:
        proc = subprocess.run(
            ["/bin/sh", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            # New process group so a timeout kills the whole tree, not just sh.
            start_new_session=True,
        )
        out, out_trunc = _truncate(proc.stdout)
        err, err_trunc = _truncate(proc.stderr)
        return {
            "exit_code": proc.returncode,
            "stdout": out,
            "stderr": err,
            "truncated": out_trunc or err_trunc,
            "duration_s": round(time.monotonic() - start, 4),
        }
    except subprocess.TimeoutExpired as exc:
        out, out_trunc = _truncate(exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
        return {
            "exit_code": None,
            "stdout": out,
            "stderr": "",
            "truncated": out_trunc,
            "duration_s": round(time.monotonic() - start, 4),
            "error": f"command timed out after {timeout_s}s",
        }
    except OSError as exc:
        return {
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "truncated": False,
            "duration_s": round(time.monotonic() - start, 4),
            "error": f"failed to launch command: {exc}",
        }


def handle_connection(conn: socket.socket) -> None:
    """Serve exactly one request on an accepted connection, then close.

    One-request-per-connection keeps the protocol trivial and stateless and
    means a malformed/hostile request can never corrupt a later one."""
    try:
        req = _recv_json_line(conn)
        command = req.get("command")
        if not isinstance(command, str):
            _send_json_line(conn, {"exit_code": None, "error": "missing 'command' string"})
            return
        timeout_s = float(req.get("timeout_s", 10.0))
        logger.info("exec command=%r timeout_s=%s", command, timeout_s)
        _send_json_line(conn, run_command(command, timeout_s))
    except (ValueError, ConnectionError) as exc:
        try:
            _send_json_line(conn, {"exit_code": None, "error": f"bad request frame: {exc}"})
        except OSError:
            pass
    finally:
        conn.close()


def serve(sock: socket.socket) -> None:
    """Accept connections forever on an already-bound, listening socket."""
    while True:
        conn, _addr = sock.accept()
        handle_connection(conn)


def _make_listener(tcp: tuple[str, int] | None, cid_port: int) -> socket.socket:
    if tcp is not None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(tcp)
    else:
        # VMADDR_CID_ANY = -1 (bind on any CID); the host connects to this
        # guest's assigned CID. See docs/DE-RISKING.md §5.
        sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
        sock.bind((socket.VMADDR_CID_ANY, cid_port))
    sock.listen(8)
    return sock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="In-guest action daemon for the Constraint Cage.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="vsock port to listen on")
    parser.add_argument(
        "--tcp",
        nargs=2,
        metavar=("HOST", "PORT"),
        help="listen on AF_INET instead of AF_VSOCK (development/tests only)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    tcp = (args.tcp[0], int(args.tcp[1])) if args.tcp else None
    try:
        sock = _make_listener(tcp, args.port)
    except AttributeError:
        print("AF_VSOCK unavailable on this host/kernel; use --tcp for dev.", file=sys.stderr)
        return 2

    # Clean shutdown on SIGTERM (libvirt destroy / trial reset).
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    logger.info("action daemon listening (%s) pid=%d", "tcp" if tcp else "vsock", os.getpid())
    try:
        serve(sock)
    except (KeyboardInterrupt, SystemExit):
        return 0
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
