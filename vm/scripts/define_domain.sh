#!/usr/bin/env bash
# define_domain.sh -- render vm/domain.xml.template and define the cage guest.
#
# Renders the @@TOKEN@@s (E-core ids, OVMF paths, overlay, cid) and runs
# `virsh define`. Needs root + libvirt; it CHECKS and instructs rather than
# assuming. Run vm/scripts/build_golden_image.sh and reset_overlay.sh first.
#
# Usage:
#   sudo vm/scripts/define_domain.sh [NAME] [OVERLAY] [CID] [MEM_MB]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
TEMPLATE="$REPO/vm/domain.xml.template"

NAME="${1:-cage-guest}"
OVERLAY="${2:-$REPO/vm/images/trial.qcow2}"
CID="${3:-3}"
MEM_MB="${4:-2048}"
RENDERED="$REPO/vm/${NAME}.xml"

_need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 ($2)" >&2; exit 1; }; }
_need virsh "apt install libvirt-clients libvirt-daemon-system"
[ -f "$TEMPLATE" ] || { echo "missing template: $TEMPLATE" >&2; exit 1; }
[ -f "$OVERLAY" ]  || { echo "missing overlay: $OVERLAY (run reset_overlay.sh first)" >&2; exit 1; }
# libvirt-qemu resolves the disk path from its own CWD (/), so it MUST be absolute.
OVERLAY="$(realpath "$OVERLAY")"

# --- E-core ids: the lower-max-MHz cluster (P-cores stay free for inference) ---
# Heuristic: sort CPUs by MAXMHZ ascending, take the bottom 2 as E-cores. VERIFY
# against `lscpu --all --extended` on this unit before trusting for a real run.
ECORES="$(lscpu --all --extended=CPU,MAXMHZ 2>/dev/null | awk 'NR>1{print $2, $1}' \
          | sort -n | awk '{print $2}' | head -2 | paste -sd, -)"
ECORE0="${ECORES%%,*}"; ECORE1="${ECORES##*,}"
ECORE0="${ECORE0:-8}"; ECORE1="${ECORE1:-9}"   # fall back to plausible E-core ids
echo "pinning vCPUs to E-cores: $ECORE0,$ECORE1 (verify with: lscpu --all --extended)"

# --- OVMF (UEFI) firmware: Ubuntu 24.04 uses the *_4M.fd variants ---
find_ovmf() { for f in "$@"; do [ -f "$f" ] && { echo "$f"; return; }; done; }
# OVMF only matters if the template uses UEFI; the current template boots legacy
# BIOS (alpine-make-vm-image builds BIOS images), so these are optional.
OVMF_CODE="$(find_ovmf /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd)"
OVMF_VARS="$(find_ovmf /usr/share/OVMF/OVMF_VARS_4M.fd /usr/share/OVMF/OVMF_VARS.fd)"
NVRAM="/var/lib/libvirt/qemu/nvram/${NAME}_VARS.fd"

sed -e "s|@@NAME@@|$NAME|g" \
    -e "s|@@MEM_KIB@@|$((MEM_MB*1024))|g" \
    -e "s|@@ECORE0@@|$ECORE0|g" -e "s|@@ECORE1@@|$ECORE1|g" \
    -e "s|@@OVMF_CODE@@|$OVMF_CODE|g" -e "s|@@OVMF_VARS@@|$OVMF_VARS|g" \
    -e "s|@@NVRAM@@|$NVRAM|g" \
    -e "s|@@OVERLAY_PATH@@|$OVERLAY|g" -e "s|@@CID@@|$CID|g" \
    "$TEMPLATE" > "$RENDERED"
echo "rendered domain -> $RENDERED"

virsh define "$RENDERED"
echo "defined domain '$NAME'. Verify isolation BEFORE first boot:"
echo "  vm/scripts/verify_isolation.sh $NAME"
echo "then: sudo virsh start $NAME   (serial console: sudo virsh console $NAME)"
