"""
Deterministic seed -> instance generator.

`ChallengeGenerator.generate(seed)` is the ONE interface every level's spec
plugs into (the task calls for "a generator interface, Python, typed" — this
is it; there is exactly one implementation, parameterized by spec, not one
per level). Reproducibility contract (v1 Part 18, "store the seed, not the
instance"): the same (spec_id, seed) must always resolve to byte-identical
provisioning + success-check scripts, forever — that's what lets a trial
be replayed from a one-line config instead of a stored blob.
"""

from __future__ import annotations

import random
from typing import Iterable

from .schema import ChallengeInstance, ChallengeSpec, Level

# XORed into `seed` for probe generation. Keeps probe and training seeds
# from ever colliding for small integer seeds (the common case: 0..a few
# thousand) while remaining fully deterministic.
_PROBE_SALT = 0x50524F42  # ASCII "PROB"


def _resolve_template(template: str, params: dict) -> str:
    """Exact-token replace of @@name@@ -> str(value). Deliberately NOT
    str.format / string.Template — see schema.py's module docstring for why
    braces and `$` in the shell/C/awk payloads make those unsafe here."""
    out = template
    for k, v in params.items():
        out = out.replace(f"@@{k}@@", str(v))
    return out


class ChallengeGenerator:
    """Wraps one ChallengeSpec; turns a seed into a concrete, resolved
    ChallengeInstance. Stateless and side-effect-free — safe to call
    concurrently for many seeds (e.g. building N trials in a batch)."""

    def __init__(self, spec: ChallengeSpec):
        self.spec = spec

    def _resolve_params(self, rng: random.Random, probe: bool) -> dict:
        resolved: dict = {}
        for p in self.spec.params:
            sampler = p.probe_sample if (probe and p.probe_sample is not None) else p.sample
            # `resolved` (so far) is passed read-only so a later field (e.g. an
            # L7 stage's log body) can embed an earlier field's value (e.g. a
            # leaked token) explicitly, instead of relying on shared-RNG-
            # position coincidence between two independent samplers.
            resolved[p.name] = sampler(rng, dict(resolved))
        return resolved

    def generate(self, seed: int, probe: bool = False) -> ChallengeInstance:
        """seed -> ChallengeInstance. `probe=True` draws from each
        ParamSpec's `probe_sample` domain where one is defined (held-out,
        disjoint from the training domain) — this is the "held-out probe
        variant" the task asks each spec to expose, exercised by re-running
        the SAME spec_id with probe=True rather than hand-authoring a
        second spec file."""
        eff_seed = seed if not probe else (seed ^ _PROBE_SALT)
        rng = random.Random(eff_seed)
        params = self._resolve_params(rng, probe)

        provisioning = tuple(
            _resolve_template(step.template, params) for step in self.spec.provisioning
        )
        success_check = _resolve_template(self.spec.success.check_template, params)
        intended_solution = tuple(
            _resolve_template(step, params) for step in self.spec.intended_solution
        )

        return ChallengeInstance(
            spec_id=self.spec.spec_id,
            seed=seed,
            level=self.spec.level,
            resolved_params=params,
            provisioning_script=provisioning,
            success_check=success_check,
            intended_solution=intended_solution,
            is_probe=probe,
        )


class GeneratorRegistry:
    """Level -> [ChallengeGenerator]. `challenges/specs/__init__.py`
    populates one of these from the Python-native specs; a future YAML- or
    DB-backed loader (if ever needed) would populate the same registry type,
    so nothing downstream (the batch runner, the scripted solver) needs to
    know or care where a spec came from."""

    def __init__(self) -> None:
        self._by_level: dict[Level, list[ChallengeGenerator]] = {}
        self._by_id: dict[str, ChallengeGenerator] = {}

    def register(self, spec: ChallengeSpec) -> ChallengeGenerator:
        if spec.spec_id in self._by_id:
            raise ValueError(f"duplicate spec_id: {spec.spec_id}")
        gen = ChallengeGenerator(spec)
        self._by_level.setdefault(spec.level, []).append(gen)
        self._by_id[spec.spec_id] = gen
        return gen

    def for_level(self, level: Level) -> tuple[ChallengeGenerator, ...]:
        return tuple(self._by_level.get(level, ()))

    def by_id(self, spec_id: str) -> ChallengeGenerator:
        return self._by_id[spec_id]

    def all(self) -> Iterable[ChallengeGenerator]:
        return tuple(self._by_id.values())
