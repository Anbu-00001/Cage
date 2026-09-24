#!/usr/bin/env bash
# verify_isolation.sh -- audit that the cage domain cannot touch the host/LAN.
#
# The safety story rests on the guest being reachable ONLY through the narrow
# vsock channel (constraint-cage.md Part 19). This is the Part 7 hardening gate:
# a STATIC audit of the defined domain XML that fails loudly if any forbidden
# device is present. Run it before every first boot; it needs no root beyond
# what `virsh dumpxml` needs.
#
# Usage:
#   vm/scripts/verify_isolation.sh [NAME]         # audit a defined domain
#   vm/scripts/verify_isolation.sh --file X.xml   # audit a rendered file
set -euo pipefail

if [ "${1:-}" = "--file" ]; then
    XML="$(cat "${2:?need a file}")"
else
    NAME="${1:-cage-guest}"
    command -v virsh >/dev/null 2>&1 || { echo "virsh not found" >&2; exit 1; }
    XML="$(virsh dumpxml "$NAME")"
fi

fail=0
# Each check: a forbidden pattern that MUST NOT appear, and why.
check_absent() {
    local pattern="$1" why="$2"
    if printf '%s' "$XML" | grep -qE "$pattern"; then
        echo "FAIL  found <$pattern> -- $why"
        fail=1
    else
        echo "ok    no $pattern"
    fi
}
check_present() {
    local pattern="$1" why="$2"
    if printf '%s' "$XML" | grep -qE "$pattern"; then
        echo "ok    $pattern present"
    else
        echo "FAIL  missing $pattern -- $why"
        fail=1
    fi
}

echo "== isolation audit =="
check_absent  "<interface"   "a NIC/LAN bridge would let the agent see your network"
check_absent  "<filesystem"  "9p/virtiofs is a direct host-path bridge"
check_absent  "<hostdev"     "USB/GPU passthrough is an escape surface"
check_absent  "type='spicevmc'|<graphics" "clipboard/display channels cross the boundary"
check_present "<vsock"       "the narrow logged action channel must exist"
check_present "cache='none'" "overlay disk should not share host page cache carelessly"

echo "== runtime checks (do these once the guest is up) =="
cat <<'EOF'
  1. From the guest (over the vsock daemon), confirm NO route off-box:
       ip route            # expect: no default route / no NIC
       ping -c1 <host-LAN-ip>   # expect: unreachable
  2. From the host, confirm the only path in is vsock:
       sudo virsh domiflist cage-guest   # expect: empty (no interfaces)
  3. Confirm libvirt applied sVirt/AppArmor confinement:
       sudo virsh dumpxml cage-guest | grep -i seclabel   # expect an apparmor/selinux label
EOF

if [ "$fail" -ne 0 ]; then
    echo "ISOLATION AUDIT FAILED -- do not boot until fixed." >&2
    exit 1
fi
echo "isolation audit PASSED (static). Complete the runtime checks above."
