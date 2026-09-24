"""Telemetry sinks: newline-delimited JSON (default) or SQLite.

Both satisfy the same tiny ``Sink`` protocol so ``TelemetryCollector``
never branches on sink type. NDJSON is the default because it is
trivially append-only and crash-safe (a killed process leaves a valid
prefix of complete lines); SQLite is offered for callers who want to query
telemetry alongside run metadata without a separate ETL step (Part 12's
"time-series store").
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Protocol

from src.telemetry.models import TelemetrySample


class Sink(Protocol):
    def write(self, sample: TelemetrySample) -> None: ...
    def close(self) -> None: ...


class NDJSONSink:
    """Appends one JSON object per line. Opens in append mode so a
    collector can be stopped and restarted mid-episode without losing
    prior samples."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def write(self, sample: TelemetrySample) -> None:
        self._fh.write(sample.model_dump_json())
        self._fh.write("\n")
        self._fh.flush()  # Part 11 REC: "flush to disk aggressively"

    def close(self) -> None:
        self._fh.close()


_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry (
    ts REAL NOT NULL,
    pkg_watt REAL,
    pkg_joules_delta REAL,
    pkg_temp_c REAL,
    throttled INTEGER,
    load_avg_1m REAL,
    psi_cpu_some_avg10 REAL,
    psi_mem_some_avg10 REAL,
    psi_io_some_avg10 REAL,
    ram_used_mb REAL,
    ram_available_mb REAL,
    swap_used_mb REAL,
    tokens_per_sec REAL,
    core_temps_json TEXT,
    core_freq_json TEXT,
    sample_errors_json TEXT
);
"""


class SQLiteSink:
    """Writes each sample as one row in a single ``telemetry`` table.
    Per-core dicts (temps, freqs) and the error list are stored as JSON
    text columns rather than normalized tables -- deliberately simple for
    a single-laptop, single-episode-at-a-time collector."""

    def __init__(self, path: str) -> None:
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(_SQLITE_SCHEMA)
        self._conn.commit()

    def write(self, sample: TelemetrySample) -> None:
        self._conn.execute(
            """
            INSERT INTO telemetry (
                ts, pkg_watt, pkg_joules_delta, pkg_temp_c, throttled, load_avg_1m,
                psi_cpu_some_avg10, psi_mem_some_avg10, psi_io_some_avg10,
                ram_used_mb, ram_available_mb, swap_used_mb, tokens_per_sec,
                core_temps_json, core_freq_json, sample_errors_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample.ts,
                sample.pkg_watt,
                sample.pkg_joules_delta,
                sample.pkg_temp_c,
                None if sample.throttled is None else int(sample.throttled),
                sample.load_avg_1m,
                sample.psi_cpu_some_avg10,
                sample.psi_mem_some_avg10,
                sample.psi_io_some_avg10,
                sample.ram_used_mb,
                sample.ram_available_mb,
                sample.swap_used_mb,
                sample.tokens_per_sec,
                json.dumps(sample.core_temps_c),
                json.dumps(sample.core_freq_mhz),
                json.dumps(sample.sample_errors),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def build_sink(kind: str, path: str) -> Sink:
    if kind == "ndjson":
        return NDJSONSink(path)
    if kind == "sqlite":
        return SQLiteSink(path)
    raise ValueError(f"unknown telemetry sink kind: {kind!r}")
