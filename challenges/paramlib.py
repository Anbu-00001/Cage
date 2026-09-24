"""
Reusable, seeded parameter samplers shared across all Level 1-7 specs.

Every function here is `(rng: random.Random, ...) -> value`, pure given
rng's state. Keeping them centralized (instead of copy-pasted per spec) is
what lets docs/CHALLENGES.md claim a single "recall-vs-reasoning" story
consistently: the same word lists / ranges back every level, and widening a
pool (e.g. adding more candidate usernames) instantly raises entropy
everywhere at once.

The *_TRAIN pools and *_PROBE pools are deliberately disjoint (no shared
words) so a `probe_sample` built from a _PROBE pool is a genuine held-out
domain, not just "another draw from the same bag" (v2 A2 #5, A4 #3).
"""

from __future__ import annotations

import random

# Disjoint word pools: TRAIN seeds only ever draw from *_TRAIN, probe
# variants only ever draw from *_PROBE. No word appears in both lists.
ADJ_TRAIN = [
    "quiet", "brisk", "amber", "cobalt", "dusty", "plain", "stout", "lucid",
    "humble", "stray", "faint", "coarse", "narrow", "steep", "worn", "keen",
]
ADJ_PROBE = [
    "muted", "brittle", "ashen", "slate", "gaunt", "spare", "wiry", "terse",
    "bleak", "supple", "hollow", "curt", "grainy", "sallow", "husky", "wan",
]
NOUN_TRAIN = [
    "otter", "finch", "cinder", "ridge", "bramble", "kestrel", "willow",
    "harbor", "thistle", "marsh", "quarry", "lantern", "cove", "birch",
]
NOUN_PROBE = [
    "vole", "heron", "slag", "gully", "hazel", "osprey", "reed", "wharf",
    "gorse", "fen", "shale", "beacon", "inlet", "alder",
]

_HEX = "0123456789abcdef"


def random_username(rng: random.Random, probe: bool = False) -> str:
    adj = rng.choice(ADJ_PROBE if probe else ADJ_TRAIN)
    noun = rng.choice(NOUN_PROBE if probe else NOUN_TRAIN)
    return f"{adj}{noun}{rng.randint(10, 99)}"


def random_group(rng: random.Random, probe: bool = False) -> str:
    noun = rng.choice(NOUN_PROBE if probe else NOUN_TRAIN)
    return f"grp-{noun}{rng.randint(100, 999)}"


def random_path_component(rng: random.Random, probe: bool = False) -> str:
    adj = rng.choice(ADJ_PROBE if probe else ADJ_TRAIN)
    noun = rng.choice(NOUN_PROBE if probe else NOUN_TRAIN)
    return f"{noun}-{adj}"


def random_hex_token(rng: random.Random, n: int = 16) -> str:
    return "".join(rng.choice(_HEX) for _ in range(n))


def random_port(rng: random.Random, lo: int = 20000, hi: int = 39999,
                 exclude: tuple[int, ...] = ()) -> int:
    while True:
        p = rng.randint(lo, hi)
        if p not in exclude:
            return p


def random_probe_port(rng: random.Random, exclude: tuple[int, ...] = ()) -> int:
    # Disjoint sub-range from the training port range (20000-39999) so a
    # solver that memorized "the port is always in the low-20000s" fails.
    return random_port(rng, lo=40000, hi=59999, exclude=exclude)


def random_int(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)
