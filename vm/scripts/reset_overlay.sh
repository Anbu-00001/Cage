#!/usr/bin/env bash
# reset_overlay.sh — instant per-trial cage reset via qcow2 overlay discard.
#
# The design docs said "external qcow2 + libvirt snapshots", but libvirt has
# NO snapshot-revert for *external* snapshots, and internal snapshots are slow
# to create (docs/DE-RISKING.md §6). The right primitive for a resettable cage
# is a copy-on-write overlay over an immutable golden image:
#
#   golden.qcow2  (read-only base, never mutated, checksummed)
#        ^  backing file
#   trial.qcow2   (thin overlay the guest boots from; holds only dirty blocks)
#
# Reset = delete the overlay and recreate it. Sub-second, and provably clean
# because the golden image is never touched. This is the mechanism behind the
# reproducibility claim (Part 18) and the safety claim (guest is disposable).
#
# Usage:
#   vm/scripts/reset_overlay.sh GOLDEN OVERLAY
#   vm/scripts/reset_overlay.sh vm/images/golden.qcow2 vm/images/trial.qcow2
set -euo pipefail

GOLDEN="${1:?usage: reset_overlay.sh GOLDEN OVERLAY}"
OVERLAY="${2:?usage: reset_overlay.sh GOLDEN OVERLAY}"

if ! command -v qemu-img >/dev/null 2>&1; then
    echo "error: qemu-img not found (apt install qemu-utils)." >&2
    exit 1
fi
if [ ! -f "$GOLDEN" ]; then
    echo "error: golden image not found: $GOLDEN (build it with build_golden_image.sh)." >&2
    exit 1
fi
# Use an ABSOLUTE backing path: qemu-img resolves a relative -b path relative to
# the OVERLAY's directory (not $PWD), which doubles a path like vm/images/... .
GOLDEN="$(realpath "$GOLDEN")"

# Integrity: the golden image must never change between trials. Record/compare
# its checksum so a silently-mutated base can't corrupt a whole batch of runs.
SUM_FILE="${GOLDEN}.sha256"
cur="$(sha256sum "$GOLDEN" | awk '{print $1}')"
if [ -f "$SUM_FILE" ]; then
    want="$(cat "$SUM_FILE")"
    if [ "$cur" != "$want" ]; then
        echo "error: golden image checksum changed! base was mutated." >&2
        echo "  expected $want" >&2
        echo "  actual   $cur" >&2
        echo "  refusing to reset — investigate before trusting any results." >&2
        exit 2
    fi
else
    echo "$cur" > "$SUM_FILE"
    echo "recorded golden checksum -> $SUM_FILE"
fi

# Discard the old overlay and recreate a fresh CoW layer over the golden base.
rm -f "$OVERLAY"
qemu-img create -q -f qcow2 -b "$GOLDEN" -F qcow2 "$OVERLAY"
echo "reset overlay: $OVERLAY  (backing: $GOLDEN)"
