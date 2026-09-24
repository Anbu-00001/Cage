"""1 Hz host telemetry collector (constraint-cage.md Part 11/12).

Samples RAPL package energy, temperatures, per-core frequency, PSI
(pressure stall information), RAM/swap, and (best-effort) llama.cpp
tokens/sec, and writes them as newline-delimited JSON or SQLite rows.

Every individual source in ``sources.py`` is best-effort and independently
fails soft: a laptop without ``lm-sensors`` installed, or a user without
RAPL read permissions, still gets a usable (partially-null) sample rather
than a crashed collector -- this is explicitly a **stub** per the task
brief, wired to the real ``/sys`` and CLI-tool surfaces the design doc
names in Part 11/23, not a finished telemetry stack.
"""
