#!/usr/bin/env bash
# build_golden_image.sh — build the immutable Alpine "cage" golden qcow2.
#
# Produces vm/images/golden.qcow2: a minimal, resettable Alpine guest that
# boots the in-guest action daemon (vm/guest/action_daemon.py) on an AF_VSOCK
# port, with a non-root "cage" user. Per-trial reset is then just an overlay
# discard over this base (vm/scripts/reset_overlay.sh).
#
# WHY ALPINE: musl + busybox => tiny RAM/disk, boots in seconds, fast resets
# (constraint-cage.md Part 5). The guest is a TARGET, it needn't be fast; the
# host keeps both P-cores for inference.
#
# PREREQS (all host-side, need root/network the first time):
#   - alpine-make-vm-image  (https://github.com/alpinelinux/alpine-make-vm-image)
#   - libguestfs-tools      (provides virt-copy-in)  [apt install libguestfs-tools]
#   - qemu-utils            (qemu-img)
#
# This script is deliberately non-interactive and idempotent-ish (it rebuilds
# from scratch each run). It does NOT install anything for you — it checks and
# tells you what's missing, so running it on your daily driver is predictable.
#
# Usage:
#   sudo vm/scripts/build_golden_image.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT_DIR="$REPO/vm/images"
OUT="$OUT_DIR/golden.qcow2"
DAEMON="$REPO/vm/guest/action_daemon.py"
IMG_SIZE="${IMG_SIZE:-2G}"
PACKAGES="python3 openrc"

_need() { command -v "$1" >/dev/null 2>&1 || { echo "missing prereq: $1 ($2)" >&2; exit 1; }; }
_need alpine-make-vm-image "https://github.com/alpinelinux/alpine-make-vm-image"
_need virt-copy-in "apt install libguestfs-tools"
_need qemu-img "apt install qemu-utils"
[ -f "$DAEMON" ] || { echo "missing guest daemon: $DAEMON" >&2; exit 1; }

mkdir -p "$OUT_DIR"

# --- 1. base image: minimal Alpine + python3, with the cage user + vsock -----
# The setup fragment runs INSIDE the new root (alpine-make-vm-image chroot).
SETUP="$(mktemp)"
trap 'rm -f "$SETUP"' EXIT
cat > "$SETUP" <<'SETUP_EOF'
#!/bin/sh
set -eu
# Unprivileged operator the agent acts as. It is NOT a privilege boundary —
# the engineered in-guest boundaries (Levels 1-7) are layered on top of it.
adduser -D -g "cage operator" cage
# Load vsock in the guest so the daemon can bind AF_VSOCK (DE-RISKING §5).
# BOTH are needed: `vsock` is the core, `vmw_vsock_virtio_transport` is the
# guest<->host transport over the virtio device. Without the transport, a bind
# succeeds but host connects to the guest CID time out. (Learned live 2026-09-24.)
printf 'vsock\nvmw_vsock_virtio_transport\n' >> /etc/modules
# Load it now too, so this boot works without waiting for a rebuild.
modprobe vmw_vsock_virtio_transport 2>/dev/null || true
# OpenRC service that starts the action daemon at boot.
cat > /etc/init.d/cage-actiond <<'SVC'
#!/sbin/openrc-run
name="cage-actiond"
description="Constraint Cage in-guest action daemon"
command="/usr/bin/python3"
command_args="/usr/local/bin/action_daemon.py --port 9000"
command_background=true
pidfile="/run/cage-actiond.pid"
command_user="cage:cage"
depend() { need localmount; after modules; }
SVC
chmod +x /etc/init.d/cage-actiond
rc-update add cage-actiond default
# No network needed — isolation by topology (Part 5/19). Do NOT add a NIC here.
SETUP_EOF
chmod +x "$SETUP"

echo "building base Alpine image ($IMG_SIZE) ..."
# --script-chroot is REQUIRED: without it the setup script runs on the HOST
# (host's Debian adduser, host's /etc) instead of inside the Alpine image. With
# it, the script is chrooted into the image so `adduser` is BusyBox and every
# /etc write lands in the guest. (Learned by running it for real, 2026-09-24.)
alpine-make-vm-image \
    --image-format qcow2 \
    --image-size "$IMG_SIZE" \
    --packages "$PACKAGES" \
    --script-chroot \
    "$OUT" \
    -- "$SETUP"

# --- 2. inject the daemon (kept out of the base build so it can be updated) ---
echo "injecting action daemon ..."
virt-copy-in -a "$OUT" "$DAEMON" /usr/local/bin/

# --- 3. mark read-only + record the integrity checksum -----------------------
chmod 0444 "$OUT"
sha256sum "$OUT" | awk '{print $1}' > "$OUT.sha256"
echo "golden image: $OUT"
echo "checksum:     $(cat "$OUT.sha256")  -> $OUT.sha256"
echo
echo "next: create a per-trial overlay and boot it, e.g.:"
echo "  vm/scripts/reset_overlay.sh $OUT $OUT_DIR/trial.qcow2"
echo "  (then define a libvirt domain with a <vsock> device — see docs/DE-RISKING.md §5)"
