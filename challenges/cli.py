"""
Tiny demo/smoke-test entrypoint for the challenge generator.

    python3 -m challenges.cli --list
    python3 -m challenges.cli --spec L6-setuid-path-trust-v1 --seed 42
    python3 -m challenges.cli --spec L6-setuid-path-trust-v1 --seed 42 --probe

Not part of the eval harness (that lives under eval/, another agent's lane)
— this exists only to prove the schema + generator + specs actually resolve
end-to-end, and as a quick way for a human to eyeball one instance while
authoring a new spec.
"""

from __future__ import annotations

import argparse
import sys

from .specs import REGISTRY


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="list all registered spec_ids")
    ap.add_argument("--spec", help="spec_id to generate an instance for")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--probe", action="store_true", help="generate the held-out probe variant")
    args = ap.parse_args(argv)

    if args.list or not args.spec:
        for gen in REGISTRY.all():
            s = gen.spec
            print(f"{s.spec_id:32s} level={s.level.name:28s} boundary={s.boundary_class.value}")
        if not args.spec:
            return 0

    gen = REGISTRY.by_id(args.spec)
    instance = gen.generate(args.seed, probe=args.probe)

    print(f"# spec_id={instance.spec_id} seed={instance.seed} probe={instance.is_probe}")
    print(f"# resolved_params={instance.resolved_params}")
    print("\n# --- provisioning ---")
    for i, step in enumerate(instance.provisioning_script, 1):
        print(f"\n## step {i}\n{step}")
    print("\n# --- intended solution ---")
    for i, step in enumerate(instance.intended_solution, 1):
        print(f"{i}. {step}")
    print("\n# --- success check ---")
    print(instance.success_check)
    return 0


if __name__ == "__main__":
    sys.exit(main())
