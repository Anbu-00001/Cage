"""Individual, best-effort telemetry sources.

Each ``read_*`` function/class talks to exactly one signal named in Part
11/23 of the design doc and NEVER raises: on any failure (missing binary,
missing permission, missing sysfs path) it returns ``None``/``{}`` plus a
short string appended to the caller's error list. That "fail soft, always
emit a sample" behaviour is what makes 1 Hz sampling safe to run
unattended for a multi-hour eval batch (Part 17) without one flaky sensor
killing the whole run.

[OPEN] None of the numbers this module reads have been validated against
this specific laptop yet -- that is exactly Part 23/D2's job (see
scripts/validate_env.sh). This module only implements *how* to read them.
"""

from __future__ import annotations

import glob
import json
import re
import subprocess
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# RAPL package energy -> average watts between two samples
# ---------------------------------------------------------------------------


class RaplPowerReader:
    """Converts monotonically-increasing RAPL energy counters
    (``/sys/class/powercap/intel-rapl:*/energy_uj``) into an average-watts
    figure between consecutive reads.

    [FACT] RAPL energy files are cumulative microjoule counters that wrap
    around at a hardware-specific max (commonly ~262 J on client parts)
    per Part 11/23's ``ls /sys/class/powercap/intel-rapl*``. This reader
    detects a wrap (new reading < old reading) and simply drops that one
    delta rather than reporting a bogus negative/huge wattage.

    Requires read access to the RAPL sysfs files; on stock Ubuntu this
    may need a udev rule or running as root -- [OPEN], verify with
    ``scripts/validate_env.sh`` on the target machine.
    """

    def __init__(self, rapl_path: str = "/sys/class/powercap/intel-rapl:0/energy_uj") -> None:
        self.rapl_path = rapl_path
        self._last_uj: int | None = None
        self._last_ts: float | None = None

    def read_delta(self) -> tuple[float | None, float | None, str | None]:
        """Returns (avg_watts_since_last_call, joules_since_last_call, error)."""
        try:
            raw = Path(self.rapl_path).read_text().strip()
            uj = int(raw)
        except (FileNotFoundError, PermissionError, ValueError) as exc:
            return None, None, f"rapl: {exc}"

        now = time.monotonic()
        if self._last_uj is None or self._last_ts is None:
            self._last_uj, self._last_ts = uj, now
            return None, None, None  # first sample: no delta yet

        dt = now - self._last_ts
        if uj < self._last_uj or dt <= 0:
            # counter wrapped, or clock oddity -- drop this delta, resync.
            self._last_uj, self._last_ts = uj, now
            return None, None, "rapl: counter wrap or non-positive dt, resynced"

        delta_j = (uj - self._last_uj) / 1_000_000.0
        watts = delta_j / dt
        self._last_uj, self._last_ts = uj, now
        return watts, delta_j, None

    @staticmethod
    def discover_domains() -> list[str]:
        """List available RAPL domain energy files, for diagnostics."""
        return sorted(glob.glob("/sys/class/powercap/intel-rapl:*/energy_uj"))


# ---------------------------------------------------------------------------
# Temperatures (lm-sensors)
# ---------------------------------------------------------------------------


def read_sensors_temps() -> tuple[float | None, dict[str, float], str | None]:
    """Runs ``sensors -j`` and extracts a package temp + per-core temps.

    [EST] `sensors -j` typically completes in a few ms -- cheap enough for
    1 Hz sampling without materially stealing cycles from inference.
    Returns (pkg_temp_c, {label: temp_c}, error).
    """
    try:
        proc = subprocess.run(["sensors", "-j"], capture_output=True, text=True, timeout=2.0)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return None, {}, f"sensors: {exc}"
    if proc.returncode != 0:
        return None, {}, f"sensors: exit {proc.returncode}: {proc.stderr.strip()[:200]}"

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return None, {}, f"sensors: bad JSON: {exc}"

    pkg_temp: float | None = None
    core_temps: dict[str, float] = {}
    for chip_readings in data.values():
        if not isinstance(chip_readings, dict):
            continue
        for label, fields in chip_readings.items():
            if not isinstance(fields, dict):
                continue
            for key, value in fields.items():
                if not key.endswith("_input") or not isinstance(value, (int, float)):
                    continue
                if "package" in label.lower() and pkg_temp is None:
                    pkg_temp = float(value)
                elif "core" in label.lower():
                    core_temps[label] = float(value)
    return pkg_temp, core_temps, None


# ---------------------------------------------------------------------------
# Per-core frequency (turbostat) -- best-effort, usually needs root
# ---------------------------------------------------------------------------


def read_turbostat_snapshot(timeout_s: float = 2.0) -> tuple[dict[str, float], str | None]:
    """Runs one short ``turbostat`` snapshot and parses per-core Bzy_MHz.

    [OPEN] turbostat normally requires root (or CAP_SYS_ADMIN +
    CAP_SYS_RAWIO); this call is expected to fail with a permissions error
    on an unprivileged collector process and is here in "runnable-shaped"
    form for when the collector IS run with the needed capability (Part
    11/23 lists it as a required diagnostic, not something this module
    can grant itself). On failure, returns ({}, error) rather than raising.
    """
    try:
        proc = subprocess.run(
            ["turbostat", "--num_iterations", "1", "--interval", "1"],
            capture_output=True,
            text=True,
            timeout=timeout_s + 2.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {}, f"turbostat: {exc}"
    if proc.returncode != 0:
        return {}, f"turbostat: exit {proc.returncode}: {proc.stderr.strip()[:200]} (likely needs root)"

    freqs: dict[str, float] = {}
    header: list[str] | None = None
    for line in proc.stdout.splitlines():
        cols = line.split()
        if not cols:
            continue
        if header is None and "Bzy_MHz" in cols:
            header = cols
            continue
        if header is None or len(cols) != len(header):
            continue
        if "Bzy_MHz" in header:
            idx = header.index("Bzy_MHz")
            cpu_label = cols[header.index("CPU")] if "CPU" in header else str(len(freqs))
            try:
                freqs[f"cpu{cpu_label}"] = float(cols[idx])
            except ValueError:
                continue
    return freqs, None


# ---------------------------------------------------------------------------
# PSI -- /proc/pressure/{cpu,memory,io}
# ---------------------------------------------------------------------------

_PSI_AVG10_RE = re.compile(r"avg10=([\d.]+)")


def read_psi(resource: str) -> tuple[float | None, str | None]:
    """Reads the 'some avg10=' figure from /proc/pressure/<resource>.

    [FACT] PSI is a Linux kernel feature (CONFIG_PSI); present on Ubuntu
    24.04's default kernel. Returns (avg10_percent, error).
    """
    path = f"/proc/pressure/{resource}"
    try:
        text = Path(path).read_text()
    except (FileNotFoundError, PermissionError) as exc:
        return None, f"psi[{resource}]: {exc}"
    for line in text.splitlines():
        if line.startswith("some"):
            match = _PSI_AVG10_RE.search(line)
            if match:
                return float(match.group(1)), None
    return None, f"psi[{resource}]: 'some' line not found"


# ---------------------------------------------------------------------------
# RAM / swap
# ---------------------------------------------------------------------------


def read_mem_swap() -> tuple[float | None, float | None, float | None, str | None]:
    """Parses /proc/meminfo. Returns (ram_used_mb, ram_available_mb, swap_used_mb, error)."""
    try:
        text = Path("/proc/meminfo").read_text()
    except (FileNotFoundError, PermissionError) as exc:
        return None, None, None, f"meminfo: {exc}"

    values: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split(":")
        if len(parts) != 2:
            continue
        key = parts[0].strip()
        num_match = re.search(r"(\d+)", parts[1])
        if num_match:
            values[key] = int(num_match.group(1))  # kB

    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    swap_total = values.get("SwapTotal")
    swap_free = values.get("SwapFree")

    ram_used_mb = (total - available) / 1024.0 if total is not None and available is not None else None
    ram_available_mb = available / 1024.0 if available is not None else None
    swap_used_mb = (
        (swap_total - swap_free) / 1024.0 if swap_total is not None and swap_free is not None else None
    )
    return ram_used_mb, ram_available_mb, swap_used_mb, None


# ---------------------------------------------------------------------------
# tokens/sec -- parsed from a llama.cpp server log file
# ---------------------------------------------------------------------------

# llama-server / llama.cpp CLI print a line shaped roughly like:
#   "eval time = 1234.56 ms / 78 runs (15.82 ms per token, 63.21 tokens per second)"
_TOK_S_RE = re.compile(r"([\d.]+)\s*tokens per second")


class LogTokRateReader:
    """Tails a llama.cpp server/CLI log file for the most recent tok/s
    figure it printed. [OPEN] exact log line format is pinned to whatever
    llama.cpp commit is in use (Part 18: "llama.cpp version/commit... in a
    config file") -- verify the regex still matches after any upgrade.
    """

    def __init__(self, log_path: str) -> None:
        self.log_path = log_path
        self._offset = 0

    def read_latest(self) -> tuple[float | None, str | None]:
        path = Path(self.log_path)
        if not path.exists():
            return None, f"tokrate: no log at {self.log_path}"
        try:
            with path.open("r", errors="replace") as fh:
                fh.seek(self._offset)
                new_text = fh.read()
                self._offset = fh.tell()
        except OSError as exc:
            return None, f"tokrate: {exc}"

        matches = _TOK_S_RE.findall(new_text)
        if not matches:
            return None, None  # no new tok/s lines since last read; not an error
        return float(matches[-1]), None
