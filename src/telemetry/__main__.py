"""Standalone telemetry collector runner.

    python3 -m src.telemetry --hz 1 --duration 10 --out runs/telemetry.ndjson

Useful on its own for Part 23-style baselining (capture a resource vector
while idle, or while `llama-bench` runs) independent of any agent episode.
"""

from __future__ import annotations

import argparse
import logging

from src.telemetry.collector import TelemetryCollector
from src.telemetry.sink import build_sink


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the 1 Hz telemetry collector standalone.")
    parser.add_argument("--hz", type=float, default=1.0)
    parser.add_argument("--duration", type=float, default=10.0, help="Seconds to sample for.")
    parser.add_argument("--out", type=str, default="runs/telemetry.ndjson")
    parser.add_argument("--sink", type=str, choices=["ndjson", "sqlite"], default="ndjson")
    parser.add_argument("--turbostat", action="store_true", help="Enable turbostat sampling (usually needs root).")
    parser.add_argument("--tokrate-log", type=str, default=None, help="Path to a llama.cpp log to parse tok/s from.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    from src.telemetry.sources import LogTokRateReader

    collector = TelemetryCollector(
        use_turbostat=args.turbostat,
        tokrate_reader=LogTokRateReader(args.tokrate_log) if args.tokrate_log else None,
    )
    sink = build_sink(args.sink, args.out)
    count = collector.run(sink, hz=args.hz, duration_s=args.duration)
    print(f"wrote {count} samples to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
