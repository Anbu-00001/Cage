"""Host-side orchestration: talks to llama-server over HTTP (httpx),
manages one episode's lifecycle, and carries actions to the guest cage
over a narrow, logged channel abstraction (SSH/vsock, stubbed; see
channel.py for why both are TODO-marked rather than fully wired).

This package supplies the concrete implementations of the Protocols
defined in ``src.agent.interfaces`` -- ``src.agent`` never imports
anything from here, only the other way around.
"""
