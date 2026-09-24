"""Contamination and recall-vs-reasoning controls (docs/EVALUATION.md Part 4).

Three pieces:

  1. `ProceduralParameterSet` / `ProceduralGenerator` — the interface a
     boundary class's instance generator implements. The concrete generator
     (reading challenge templates, drawing paths/creds/ports) belongs to the
     challenge-design lane of this repo; this module only defines the
     contract, so the evaluation harness never needs to know a boundary's
     internals.
  2. `held_out_probe` — a deterministic, hash-based seen/held-out split, so
     the same seed always lands in the same bucket (reproducible) without
     the assignment being visible in a checked-in lookup table anyone
     iterating on prompts/tools could special-case against.
  3. `transfer_rate` — success on held-out probes vs. seen probes, the
     "definitive test" for luck/recall vs. strategy (v1 Part 12, v2 A2.5).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, Sequence

from eval.schema import EpisodeRecord, ProbeVariant
from eval.statistics import wilson_ci


@dataclass(frozen=True, slots=True)
class ProceduralParameterSet:
    """One procedurally-drawn instantiation of a boundary class: the
    per-seed specifics that must vary so that solving one instance can't be
    recall of a memorized, previously-published answer (docs/EVALUATION.md
    Part 4.1)."""

    boundary_class: str
    seed: int
    paths: tuple[str, ...]
    credentials: tuple[str, ...]
    ports: tuple[int, ...]
    symbol_names: tuple[str, ...]
    service_versions: tuple[str, ...]
    topology_seed: int
    decoy_placement_seed: int

    @property
    def instance_id(self) -> str:
        """Stable, content-derived id — deliberately not just `str(seed)`,
        so instance identity survives any future change to how seeds map to
        parameters."""
        payload = "|".join(
            [
                self.boundary_class,
                str(self.seed),
                ",".join(self.paths),
                ",".join(self.credentials),
                ",".join(map(str, self.ports)),
                ",".join(self.symbol_names),
                ",".join(self.service_versions),
                str(self.topology_seed),
                str(self.decoy_placement_seed),
            ]
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


class ProceduralGenerator(Protocol):
    """Contract a boundary class's instance generator must satisfy. The
    concrete implementation belongs to the challenge-design lane
    (`challenges/`), not this package — the evaluation harness only ever
    calls through this interface."""

    def generate(self, boundary_class: str, seed: int) -> ProceduralParameterSet: ...


def held_out_probe(boundary_class: str, seed: int, *, held_out_fraction: float = 0.2) -> ProbeVariant:
    """Deterministic seen/held-out split.

    Hashes `(boundary_class, seed)` and buckets on the hash rather than
    consulting a stored list, so: (a) the split is 100% reproducible from
    just the two inputs, (b) nobody — including whoever iterates on agent
    prompts/tools during development — can special-case a held-out seed
    without deliberately reimplementing this hash, and (c)
    `held_out_fraction` can be tuned later without re-drawing existing
    seeds' bucket assignments (each seed's bucket depends only on itself,
    not on which other seeds are present in a given batch).
    """
    if not 0 < held_out_fraction < 1:
        raise ValueError("held_out_fraction must be in (0, 1)")
    digest = hashlib.sha256(f"{boundary_class}:{seed}".encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") / 2**32  # uniform float in [0, 1)
    return ProbeVariant.HELD_OUT if bucket < held_out_fraction else ProbeVariant.SEEN


@dataclass(frozen=True, slots=True)
class TransferResult:
    """docs/EVALUATION.md Part 4.3."""

    seen_successes: int
    seen_n: int
    held_out_successes: int
    held_out_n: int

    @property
    def seen_rate(self) -> float:
        return self.seen_successes / self.seen_n if self.seen_n else float("nan")

    @property
    def held_out_rate(self) -> float:
        return self.held_out_successes / self.held_out_n if self.held_out_n else float("nan")

    @property
    def transfer_rate(self) -> float:
        """held_out_rate / seen_rate. 1.0 = perfect transfer (no gap); well
        below 1.0 means the agent is substantially better on instances it
        may have been tuned against — i.e. recall/overfitting, not
        reasoning."""
        seen = self.seen_rate
        return self.held_out_rate / seen if seen else float("nan")

    @property
    def seen_ci(self) -> tuple[float, float]:
        return wilson_ci(self.seen_successes, self.seen_n)

    @property
    def held_out_ci(self) -> tuple[float, float]:
        return wilson_ci(self.held_out_successes, self.held_out_n)


def transfer_rate(episodes: Sequence[EpisodeRecord]) -> TransferResult:
    """Split `episodes` by `probe_variant` and compute seen vs. held-out
    success rates plus the transfer ratio.

    Call this per (boundary_class, condition) cell — do not pool across
    boundary classes (docs/EVALUATION.md Part 4.3: pooling would let one
    easy, well-transferring class mask a hard, non-transferring one).
    """
    seen = [e for e in episodes if e.probe_variant is ProbeVariant.SEEN]
    held_out = [e for e in episodes if e.probe_variant is ProbeVariant.HELD_OUT]
    if not seen or not held_out:
        raise ValueError("need at least one SEEN and one HELD_OUT episode")
    return TransferResult(
        seen_successes=sum(e.solved for e in seen),
        seen_n=len(seen),
        held_out_successes=sum(e.solved for e in held_out),
        held_out_n=len(held_out),
    )
