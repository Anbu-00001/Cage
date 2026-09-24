#!/usr/bin/env bash
# validate_env.sh — read-only environment diagnostics.
#
# Wraps the exact command list from constraint-cage.md Part 23 and
# constraint-cage-v2.md D2 ("Command-level validation (measure before you
# trust me)"). Every command here is READ-ONLY: no writes, no config
# changes, no package installs. Where a command needs root (dmidecode,
# turbostat), the script tries it and clearly labels the output as
# skipped/degraded rather than failing the whole run — this is meant to
# be safe to run on a laptop you care about, repeatedly, with or without
# sudo available.
#
# Usage:
#   ./scripts/validate_env.sh                 # everything readable without sudo
#   sudo ./scripts/validate_env.sh             # also unlocks dmidecode/turbostat
#   ./scripts/validate_env.sh > env_report.txt  # save for the run's provenance record (Part 18)
#
# Output is intentionally verbose and grep-able; each section header names
# the design-doc question it answers.

set -uo pipefail

_have() { command -v "$1" >/dev/null 2>&1; }

_section() {
    echo
    echo "=================================================================="
    echo "== $1"
    echo "=================================================================="
}

_run() {
    # Runs a command, printing what failed instead of aborting the script.
    echo "\$ $*"
    if ! "$@" 2>&1; then
        echo "[skipped/failed: $* — likely missing binary or permission]"
    fi
    echo
}

echo "Constraint Cage — environment validation"
echo "host: $(hostname 2>/dev/null || echo unknown)   date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ "$(id -u)" -eq 0 ]; then
    echo "running as: root (dmidecode/turbostat sections will work)"
else
    echo "running as: non-root (dmidecode/turbostat sections will be skipped or degraded — re-run with sudo for those)"
fi

_section "CPU topology — confirm 2P+8E, AVX2/no-AVX-512 (Part 1)"
_run lscpu
if _have lscpu; then _run lscpu --all --extended; fi
_run grep -m1 flags /proc/cpuinfo

_section "★ Memory channels — the single most important measurement (Part 2)"
echo "1 populated channel ⇒ roughly HALVE every tok/s [EST] figure in the design docs."
if _have dmidecode; then
    _run dmidecode -t memory
else
    echo "[dmidecode not installed — sudo apt install dmidecode]"
fi
if _have lshw; then _run lshw -short -C memory; fi

_section "RAM & swap headroom (Part 4)"
_run free -h
_run grep -E 'MemTotal|MemAvailable' /proc/meminfo
if _have swapon; then _run swapon --show; fi
_run cat /proc/sys/vm/swappiness
if _have zramctl; then _run zramctl; fi

_section "Storage — type & speed for snapshot/reset cost (Part 5)"
_run lsblk -o NAME,SIZE,ROTA,TYPE,MOUNTPOINT
if _have nvme; then _run nvme list; fi
_run df -h /

_section "GPU — confirm there is nothing to offload to (Part 1)"
_run bash -c "lspci | grep -Ei 'vga|3d|display'"
if [ -d /dev/dri ]; then _run ls /dev/dri; else echo "no /dev/dri"; fi

_section "Virtualization / KVM stack (Part 5)"
if [ -e /dev/kvm ]; then _run ls -l /dev/kvm; else echo "/dev/kvm does not exist — VT-x/VT-d likely disabled in firmware"; fi
_run bash -c "egrep -c '(vmx|svm)' /proc/cpuinfo"
if _have kvm-ok; then _run kvm-ok; else echo "[kvm-ok not installed — sudo apt install cpu-checker]"; fi
if _have systemctl; then _run systemctl status libvirtd --no-pager; fi
if _have qemu-system-x86_64; then _run qemu-system-x86_64 --version; fi
if _have virsh; then _run virsh version; fi

_section "Thermals & power baseline (Part 11) — run BEFORE any sustained load"
if _have sensors; then _run sensors; else echo "[lm-sensors not installed — sudo apt install lm-sensors && sudo sensors-detect]"; fi
if _have turbostat; then
    echo "\$ turbostat --interval 1 --num_iterations 3  (short sample; run.sh's telemetry collector runs this continuously)"
    if ! timeout 5 turbostat --interval 1 --num_iterations 3 2>&1; then
        echo "[turbostat failed — needs root/CAP_SYS_RAWIO; re-run with sudo]"
    fi
    echo
else
    echo "[turbostat not installed — usually ships with linux-tools-common / linux-tools-\$(uname -r)]"
fi
if compgen -G "/sys/class/powercap/intel-rapl*" > /dev/null; then
    _run ls /sys/class/powercap/intel-rapl*
else
    echo "[no /sys/class/powercap/intel-rapl* paths found — RAPL unavailable, joules/solve telemetry will be null]"
fi

_section "Kernel, containers, network (Part 19 baseline)"
_run uname -a
_run cat /etc/os-release
if _have docker; then _run docker --version; fi
if _have podman; then _run podman --version; fi
_run ip -br addr
_run ip -br link

_section "Summary — the three numbers Part 23/D2 says collapse most [EST] into [FACT]"
cat <<'EOF'
1. Memory channels (dmidecode -t memory, above) — single vs dual.
2. Measured tok/s for a 3B and 7B Q4 model at 4k ctx, WITH the VM running
   (not produced by this script — run `llama-bench`, see
   scripts/build_llama_cpp.sh).
3. Sustained P-core clock + PkgWatt after ~10 min of load (turbostat,
   above only gives a cold snapshot — re-run turbostat continuously
   during a llama-bench run for the real number).

Record all three in docs/ARCHITECTURE.md / the run's provenance notes once
measured, and convert the corresponding [EST] tags to [FACT].
EOF
