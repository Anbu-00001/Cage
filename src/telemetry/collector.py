"""The 1 Hz collector loop.

Ties the best-effort sources (sources.py) into one ``TelemetrySample`` per
tick and writes it to a ``Sink`` (sink.py). Every source failure is
captured into ``sample.sample_errors`` rather than raised, so a multi-hour
unattended eval batch (Part 17) survives a missing sensor, an unreadable
RAPL file, or turbostat lacking root -- exactly the "low-overhead sampling
... without gaps" bar Part 11 sets.

[EST] At 1 Hz, this collector's own CPU/RAM footprint should be a small
fraction of one E-core -- `sensors -j` and reading a few sysfs files are
each low-single-digit milliseconds -- but this has NOT been measured on
the target laptop; verify with `scripts/validate_env.sh` plus a profiled
dry run before trusting it not to steal cycles from inference (Part 1's
"reserve E-cores for VM + agent + telemetry").
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

from src.telemetry.models import TelemetrySample
from src.telemetry.sink import Sink
from src.telemetry.sources import (
    LogTokRateReader,
    RaplPowerReader,
    read_mem_swap,
    read_psi,
    read_sensors_temps,
    read_turbostat_snapshot,
)

logger = logging.getLogger("cage.telemetry")


@dataclass
class TelemetryCollector:
    """Samples every configured source once per ``sample()`` call.

    ``use_turbostat`` defaults to False because it usually requires root
    (see sources.read_turbostat_snapshot); enable explicitly once the
    collector process has the right privilege, otherwise every tick pays
    for a doomed subprocess call.
    """

    rapl_reader: RaplPowerReader = field(default_factory=RaplPowerReader)
    tokrate_reader: LogTokRateReader | None = None
    use_turbostat: bool = False

    def sample(self) -> TelemetrySample:
        errors: list[str] = []

        pkg_watt, pkg_joules_delta, rapl_err = self.rapl_reader.read_delta()
        if rapl_err:
            errors.append(rapl_err)

        pkg_temp_c, core_temps_c, sensors_err = read_sensors_temps()
        if sensors_err:
            errors.append(sensors_err)

        core_freq_mhz: dict[str, float] = {}
        if self.use_turbostat:
            core_freq_mhz, turbostat_err = read_turbostat_snapshot()
            if turbostat_err:
                errors.append(turbostat_err)

        psi_cpu, psi_cpu_err = read_psi("cpu")
        psi_mem, psi_mem_err = read_psi("memory")
        psi_io, psi_io_err = read_psi("io")
        for err in (psi_cpu_err, psi_mem_err, psi_io_err):
            if err:
                errors.append(err)

        ram_used_mb, ram_available_mb, swap_used_mb, mem_err = read_mem_swap()
        if mem_err:
            errors.append(mem_err)

        tokens_per_sec = None
        if self.tokrate_reader is not None:
            tokens_per_sec, tok_err = self.tokrate_reader.read_latest()
            if tok_err:
                errors.append(tok_err)

        load_avg_1m: float | None = None
        try:
            load_avg_1m = os.getloadavg()[0]
        except OSError as exc:
            errors.append(f"loadavg: {exc}")

        return TelemetrySample(
            pkg_watt=pkg_watt,
            pkg_joules_delta=pkg_joules_delta,
            pkg_temp_c=pkg_temp_c,
            core_temps_c=core_temps_c,
            core_freq_mhz=core_freq_mhz,
            load_avg_1m=load_avg_1m,
            psi_cpu_some_avg10=psi_cpu,
            psi_mem_some_avg10=psi_mem,
            psi_io_some_avg10=psi_io,
            ram_used_mb=ram_used_mb,
            ram_available_mb=ram_available_mb,
            swap_used_mb=swap_used_mb,
            tokens_per_sec=tokens_per_sec,
            sample_errors=errors,
        )

    def run(
        self,
        sink: Sink,
        hz: float = 1.0,
        duration_s: float | None = None,
        stop_flag: "list[bool] | None" = None,
    ) -> int:
        """Block, sampling at ``hz`` until ``duration_s`` elapses or
        ``stop_flag[0]`` becomes True (a simple cooperative stop mechanism
        that avoids pulling in threading primitives for a straight-line
        loop). Returns the number of samples written."""
        interval = 1.0 / hz
        start = time.monotonic()
        count = 0
        try:
            while True:
                tick_start = time.monotonic()
                sample = self.sample()
                sink.write(sample)
                count += 1
                if sample.sample_errors:
                    logger.debug("telemetry sample %d had %d source errors", count, len(sample.sample_errors))

                if duration_s is not None and (time.monotonic() - start) >= duration_s:
                    break
                if stop_flag is not None and stop_flag and stop_flag[0]:
                    break

                elapsed = time.monotonic() - tick_start
                time.sleep(max(0.0, interval - elapsed))
        finally:
            sink.close()
        return count
