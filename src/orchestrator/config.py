"""The versioned run configuration schema.

Part 18 of the design doc is explicit about what must be pinned for
reproducibility: model checkpoint + quant + hash, llama.cpp version/
threads/ctx/sampling, agent code + prompt templates, VM image hash + seed,
host state. This module is the typed schema that ``config/example.yaml``
is validated against, and that ``run.sh`` / ``src.orchestrator.cli`` load
before starting an episode.

Nothing in here talks to a file system or network beyond ``load_config``'s
YAML read -- it is pure data + validation, matching pydantic-settings-style
config-as-code rather than scattered argparse defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class ModelConfig(BaseModel):
    """Everything llama-server needs, pinned (Part 18: "GGUF file hash").

    ``path`` and ``sha256`` are intentionally optional with no default --
    forcing the config author to either supply a real model or explicitly
    acknowledge (by leaving them unset) that this run uses the fake
    client. See ``orchestrator.llm_client.build_completion_client``.
    """

    path: str | None = Field(
        default=None, description="Path to a local GGUF file, e.g. models/qwen2.5-3b-instruct-q4_k_m.gguf"
    )
    sha256: str | None = Field(
        default=None, description="SHA-256 of the GGUF file, for reproducibility (Part 18)."
    )
    quant: str = Field(default="Q4_K_M", description="Quantization scheme, e.g. Q4_K_M.")
    server_url: str = Field(
        default="http://127.0.0.1:8080", description="Base URL of a running llama-server instance."
    )
    ctx: int = Field(default=4096, ge=512, description="Context window, tokens.")
    threads: int = Field(
        default=4,
        ge=1,
        description="llama-server -t / --threads. Design doc REC: pin to the 2 P-cores' "
        "4 hardware threads for decode; do not spread onto E-cores (Part 1).",
    )
    n_predict: int = Field(default=512, description="Max tokens generated per completion call.")


class SamplingConfig(BaseModel):
    """Sampling params. Default temperature 0 -- Part 17: "fix sampling
    (temp 0 or fixed seed) when the question is capability, not
    creativity", which is the default posture for this benchmark."""

    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    top_k: int = Field(default=1, ge=0)
    repeat_penalty: float = Field(default=1.1, ge=0.0)
    seed: int = Field(default=42)


class VMConfig(BaseModel):
    """The cage. Defaults match the design doc's recommended VM shape
    (Part 5/24): 2 vCPU on E-cores, 1.5-3 GB RAM, Alpine, qcow2 CoW,
    isolated NAT, vsock control channel."""

    image_path: str = Field(default="vm/images/alpine-cage-base.qcow2")
    snapshot_name: str = Field(default="golden")
    vcpus: int = Field(default=2, ge=1, le=4, description="Design doc: never 8+ (oversubscription).")
    ram_mb: int = Field(default=2048, ge=512)
    channel: Literal["ssh", "vsock", "local_mock"] = Field(
        default="local_mock",
        description="local_mock = no VM required, for dev/tests. ssh/vsock "
        "are the real Architecture-C transports (Part 3/5), both stubbed "
        "pending libvirt wiring -- see src/orchestrator/channel.py.",
    )
    ssh_host: str = Field(default="127.0.0.1")
    ssh_port: int = Field(default=2222)
    ssh_user: str = Field(default="researcher")
    ssh_key_path: str | None = Field(default=None)
    vsock_cid: int | None = Field(default=None)
    vsock_port: int = Field(default=9000)


class TelemetryConfig(BaseModel):
    enabled: bool = Field(default=True)
    hz: float = Field(default=1.0, gt=0.0)
    sink: Literal["ndjson", "sqlite"] = Field(default="ndjson")
    output_path: str = Field(default="runs/telemetry.ndjson")


class LoopSettingsConfig(BaseModel):
    step_budget: int = Field(default=30, ge=1)
    replan_interval: int = Field(default=5, ge=1)
    char_budget: int = Field(default=4000, ge=200)
    # Optional scaffolding lever: highlight a flag-shaped token in an
    # observation and point the agent at submit_flag (targets the
    # found_not_submitted stall). Off by default -> baseline behaviour.
    submit_nudge: bool = Field(default=False)


class RunConfig(BaseModel):
    """The top-level, versioned config -- one file fully determines one
    episode given a seed, per Part 18's reproducibility bar: `run.sh
    --seed 42 --config c.yaml` -> a byte-comparable transcript."""

    name: str = Field(default="example")
    seed: int = Field(default=42)
    model: ModelConfig = Field(default_factory=ModelConfig)
    sampling: SamplingConfig = Field(default_factory=SamplingConfig)
    vm: VMConfig = Field(default_factory=VMConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    loop: LoopSettingsConfig = Field(default_factory=LoopSettingsConfig)
    transcript_dir: str = Field(default="runs/transcripts")

    @field_validator("seed")
    @classmethod
    def _seed_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("seed must be >= 0")
        return v


def load_config(path: str | Path) -> RunConfig:
    """Load and validate a YAML run config. Raises pydantic.ValidationError
    (via RunConfig) on a malformed file -- fail loud, before an episode
    starts, rather than mid-run."""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    return RunConfig.model_validate(data)
