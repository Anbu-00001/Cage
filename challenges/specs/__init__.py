"""
Builds the one process-wide GeneratorRegistry from the Python-native specs
in this package. Import `REGISTRY` from here rather than constructing your
own — it's what the batch runner, the scripted solver, and `challenges.cli`
all share, so a spec registered twice (a spec_id typo colliding with an
existing one) fails loudly at import time instead of silently at trial time.
"""

from __future__ import annotations

from ..generator import GeneratorRegistry
from . import (
    level1_unprivileged_user,
    level2_filesystem_locks,
    level3_network_limits,
    level4_process_cgroup_limits,
    level5_capability_drops,
    level6_engineered_flaw,
    level7_multistage_chain,
)

_SPEC_MODULES = (
    level1_unprivileged_user,
    level2_filesystem_locks,
    level3_network_limits,
    level4_process_cgroup_limits,
    level5_capability_drops,
    level6_engineered_flaw,
    level7_multistage_chain,
)

REGISTRY = GeneratorRegistry()
for _mod in _SPEC_MODULES:
    REGISTRY.register(_mod.SPEC)
