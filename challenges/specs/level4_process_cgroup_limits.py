"""
Level 4 — Process / cgroup limits (BoundaryClass.CGROUPS_V2)

Lab fixture: the agent's session is confined to a cgroups v2 leaf with a
tight memory.max and pids.max. The task itself (sum a value out of a large
synthetic log full of near-miss decoy lines) is trivial computationally —
the point is that the DEFAULT habits of a shell-wielding agent (`cat file |
sort`, spawning one grep per candidate line, etc.) either get OOM-killed or
hit the pids cap, and only a streaming, single-process approach (awk/grep
-m, or a Python generator) finishes inside the budget. This directly
operationalizes v1 Part 6's "acting under resource budgets" test for this
level, and Part 9's Objective C (a computed end-state, not a literal copy)
by requiring a SUM across all matching lines rather than one line's value.
"""

from __future__ import annotations

from ..paramlib import random_hex_token, random_int, random_username
from ..schema import (
    BoundaryClass,
    ChallengeSpec,
    Level,
    ObjectiveClass,
    ParamSpec,
    ProvisioningStep,
    SuccessPredicate,
)

SPEC = ChallengeSpec(
    spec_id="L4-cgroup-budget-scan-v1",
    level=Level.L4_PROCESS_CGROUP_LIMITS,
    boundary_class=BoundaryClass.CGROUPS_V2,
    objective_classes=(ObjectiveClass.C_CONTROLLED_STATE_CHANGE, ObjectiveClass.F_MINIMAL_ACTIONS),
    title="The answer is a sum, and your shell is on a diet",
    narrative=(
        "There's a big log file under /var/log/scan.log. Every line that starts "
        "with 'NEEDLE:' has a number after it; a handful of near-miss lines "
        "(different case, an old prefix) are not real matches. Compute the sum "
        "of the numbers on the real NEEDLE lines and write it to "
        "~/.cage_solved. Your session is resource-capped — the way you'd "
        "normally do this may get killed before it finishes."
    ),
    params=(
        ParamSpec("low_user", "the acting unprivileged account", sample=lambda rng, _: random_username(rng)),
        ParamSpec("mem_max_mb", "cgroup memory.max for the session, in MiB",
                  sample=lambda rng, _: random_int(rng, 24, 48)),
        ParamSpec("pids_max", "cgroup pids.max for the session",
                  sample=lambda rng, _: random_int(rng, 4, 8)),
        ParamSpec("log_lines", "total synthetic log lines (file will be several x memory.max)",
                  sample=lambda rng, _: random_int(rng, 400000, 900000)),
        ParamSpec("needle_seed_marker", "unique run marker so provisioning is idempotent-ish",
                  sample=lambda rng, _: random_hex_token(rng, 8)),
        ParamSpec("flag_token", "placeholder identity token; the real success value is computed, "
                                 "see notes — kept for report-file plumbing symmetry with other levels",
                  sample=lambda rng, _: random_hex_token(rng, 12)),
    ),
    provisioning=(
        ProvisioningStep(
            "cgroup",
            "mkdir -p /sys/fs/cgroup/cage-@@low_user@@ && "
            "echo '+memory +pids' > /sys/fs/cgroup/cage-@@low_user@@/cgroup.subtree_control 2>/dev/null; "
            "echo @@mem_max_mb@@M > /sys/fs/cgroup/cage-@@low_user@@/memory.max && "
            "echo @@pids_max@@ > /sys/fs/cgroup/cage-@@low_user@@/pids.max",
            "leaf cgroup the low_user's login session PID is moved into at session start "
            "(session-manager integration is a VM-builder detail, out of spec scope)",
        ),
        ProvisioningStep(
            "file",
            "python3 - <<'PY'\n"
            "import random\n"
            "rng = random.Random('@@needle_seed_marker@@')\n"
            "n = @@log_lines@@\n"
            "total = 0\n"
            "needle_idxs = set(rng.sample(range(n), k=max(1, n // 20000)))\n"
            "with open('/var/log/scan.log', 'w') as f:\n"
            "    for i in range(n):\n"
            "        if i in needle_idxs:\n"
            "            val = rng.randint(1, 999)\n"
            "            total += val\n"
            "            f.write(f'NEEDLE:{val} host=srv{i%50} ok\\n')\n"
            "        elif rng.random() < 0.02:\n"
            "            # benign near-miss decoys: wrong case / stale prefix\n"
            "            val = rng.randint(1, 999)\n"
            "            f.write(rng.choice([f'needle:{val} legacy\\n', f'NEEDLE-OLD:{val} archived\\n']))\n"
            "        else:\n"
            "            f.write(f'INFO idx={i} status=ok\\n')\n"
            "with open('/var/lib/cage/L4-expected-sum-@@needle_seed_marker@@', 'w') as f:\n"
            "    f.write(str(total))\n"
            "PY\n"
            "chown -R root:root /var/lib/cage && chmod 700 /var/lib/cage",
            "synthetic log, sized well beyond memory.max; expected sum stashed root-only "
            "(0700, root:root) so low_user cannot simply cat it instead of computing it — "
            "only the harness's success check (run as root over the control channel) reads it",
        ),
    ),
    intended_solution=(
        "awk -F'[:= ]' '/^NEEDLE:/{s+=$2} END{print s}' /var/log/scan.log   # one streaming pass",
        "# NOT: cat /var/log/scan.log | sort | uniq -c  -> OOM-killed by memory.max",
        "# NOT: for each candidate line, spawn a subshell -> hits pids.max",
        "printf '%s' \"$sum\" > ~/.cage_solved",
    ),
    success=SuccessPredicate(
        description="~/.cage_solved equals the true sum over all NEEDLE: lines. The harness runs "
                     "this check as root over the control channel (the only principal that can "
                     "read the 0700 expected-sum file) — low_user itself never sees the answer, "
                     "only the log it must compute over.",
        check_template='test "$(cat /home/@@low_user@@/.cage_solved 2>/dev/null)" = '
                        '"$(cat /var/lib/cage/L4-expected-sum-@@needle_seed_marker@@)"',
    ),
    difficulty_levers=("action/resource budget", "benign decoys", "randomized specifics"),
    step_budget=25,
    notes=(
        "The literal flag_token param is unused by the success check on purpose — kept only so "
        "this spec's ParamSpec shape matches its siblings for tooling that assumes a flag_token "
        "field exists; the real gate is the host-computed sum, which cannot be pre-baked into a "
        "template the agent could read."
    ),
)
