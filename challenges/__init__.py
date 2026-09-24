"""
Constraint Cage — challenge-spec skeleton.

    from challenges.specs import REGISTRY
    gen = REGISTRY.by_id("L6-setuid-path-trust-v1")
    instance = gen.generate(seed=42)               # training instance
    probe = gen.generate(seed=42, probe=True)       # held-out probe variant

See schema.py for the spec/instance dataclasses, generator.py for the
seed -> instance machinery, paramlib.py for shared parameter samplers, and
specs/level*.py for the one fully-worked example spec per Level 1-7.
Design rationale and the level-by-level write-up live in
../docs/CHALLENGES.md.
"""

from .generator import ChallengeGenerator, GeneratorRegistry
from .schema import (
    BoundaryClass,
    ChallengeInstance,
    ChallengeSpec,
    Level,
    ObjectiveClass,
    ParamSpec,
    ProvisioningStep,
    SuccessPredicate,
)

__all__ = [
    "BoundaryClass",
    "ChallengeGenerator",
    "ChallengeInstance",
    "ChallengeSpec",
    "GeneratorRegistry",
    "Level",
    "ObjectiveClass",
    "ParamSpec",
    "ProvisioningStep",
    "SuccessPredicate",
]
