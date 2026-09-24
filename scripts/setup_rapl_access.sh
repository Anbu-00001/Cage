#!/usr/bin/env bash
# setup_rapl_access.sh — make Intel RAPL energy counters readable by non-root.
#
# WRITES to the system (installs a udev rule) — unlike validate_env.sh, which
# is read-only. Run once, with sudo. Idempotent.
#
# Why this is needed: since the PLATYPUS side-channel (CVE-2020-8694), Linux
# makes /sys/class/powercap/intel-rapl:*/energy_uj root-readable only, so the
# joules/solve and solves/watt-hour metrics (the project's energy leg) fail
# with "permission denied" for the run user. See docs/DE-RISKING.md §2.
#
# Threat note: this re-exposes coarse package-energy readings to local users.
# On a dedicated single-user research laptop that is an acceptable trade for
# being able to measure energy; do NOT ship this rule to a multi-tenant box.
#
# Usage:
#   sudo ./scripts/setup_rapl_access.sh          # install the rule and apply now
#   sudo ./scripts/setup_rapl_access.sh --revert # remove the rule
set -euo pipefail

RULE=/etc/udev/rules.d/70-rapl.rules
# Apply to the virtual powercap tree; the plain intel-rapl class path is
# finicky because the sysfs files are virtual (see DE-RISKING.md §2).
RULE_BODY='SUBSYSTEM=="powercap", ACTION=="add", RUN+="/bin/chmod -R a+r /sys/devices/virtual/powercap"'

if [ "$(id -u)" -ne 0 ]; then
    echo "error: run with sudo (this modifies /etc/udev)." >&2
    exit 1
fi

if [ "${1:-}" = "--revert" ]; then
    rm -f "$RULE"
    echo "removed $RULE (change takes effect on next boot / udev reload)."
    exit 0
fi

echo "$RULE_BODY" > "$RULE"
echo "wrote $RULE"

# Apply immediately for this boot without waiting for a reboot.
chmod -R a+r /sys/devices/virtual/powercap 2>/dev/null || true
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger --subsystem-match=powercap 2>/dev/null || true

probe=/sys/class/powercap/intel-rapl:0/energy_uj
if [ -e "$probe" ] && [ -r "$probe" ]; then
    echo "OK: $probe is now readable. Verify as your run user:"
    echo "    cat $probe"
else
    echo "note: rule installed but $probe not readable yet — a reboot or"
    echo "      'udevadm trigger' may be needed, or this CPU lacks a package domain."
fi
