"""The Constraint Cage — source package.

Sub-packages:
    agent        The OBSERVE -> ... -> NEXT reasoning loop, typed tools,
                 structured + failure memory. Pure "brain" logic; depends
                 only on structural Protocols (src.agent.interfaces), never
                 on a concrete transport or LLM backend.
    orchestrator Host-side plumbing: the llama-server HTTP client, the
                 host<->guest action channel (SSH/vsock, stubbed), episode
                 lifecycle, and run configuration.
    telemetry    1 Hz host resource/energy collector (RAPL, sensors,
                 turbostat, PSI, tok/s) writing newline-delimited JSON.

See docs/ARCHITECTURE.md for the component diagram and data flow.
"""
