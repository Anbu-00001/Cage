"""The telemetry sample schema.

One ``TelemetrySample`` = one 1 Hz tick across every signal Part 11/12 of
the design doc asks for: package power (the "watts" in intelligence-per-
joule, Part 16), temps (throttle detection), per-core frequency (sustained
vs turbo), PSI (the "other confounder: memory pressure"), and tok/s (the
model's actual throughput that trial). Every field is ``Optional`` because
a source can be unavailable on a given machine/permission set -- a null
field means "not sampled here", never "zero".
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field


class TelemetrySample(BaseModel):
    ts: float = Field(default_factory=time.time, description="Unix timestamp, seconds.")

    # -- power / energy (RAPL) --------------------------------------------
    pkg_watt: float | None = Field(
        default=None,
        description="[FACT if sampled] Average package power (W) since the previous "
        "sample, from /sys/class/powercap/intel-rapl energy deltas.",
    )
    pkg_joules_delta: float | None = Field(
        default=None, description="Energy consumed (J) since the previous sample."
    )

    # -- thermals -----------------------------------------------------
    pkg_temp_c: float | None = Field(default=None, description="Package temperature, deg C (from `sensors -j`).")
    core_temps_c: dict[str, float] = Field(
        default_factory=dict, description="Per-core temperature, deg C, keyed by sensor label."
    )
    throttled: bool | None = Field(
        default=None, description="Best-effort throttle flag; None if not determinable from available sources."
    )

    # -- frequency / utilisation -----------------------------------------
    core_freq_mhz: dict[str, float] = Field(
        default_factory=dict, description="Per-core current frequency, MHz."
    )
    load_avg_1m: float | None = None

    # -- memory pressure (PSI) + RAM/swap ---------------------------------
    psi_cpu_some_avg10: float | None = None
    psi_mem_some_avg10: float | None = None
    psi_io_some_avg10: float | None = None
    ram_used_mb: float | None = None
    ram_available_mb: float | None = None
    swap_used_mb: float | None = None

    # -- model throughput ---------------------------------------------
    tokens_per_sec: float | None = Field(
        default=None, description="Most recently observed decode tok/s, parsed from llama.cpp server logs."
    )

    # -- bookkeeping ----------------------------------------------------
    sample_errors: list[str] = Field(
        default_factory=list,
        description="Non-fatal errors from individual sources this tick (e.g. 'sensors: not installed'). "
        "The sample is still emitted with those fields left null.",
    )
