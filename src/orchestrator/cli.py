"""Command-line entry point used by ``run.sh``.

    python3 -m src.orchestrator.cli --seed 42 --config config/example.yaml
    python3 -m src.orchestrator.cli --smoke              # no model, no VM

``--smoke`` runs the hardcoded smoke-test goal (``episode.make_smoke_goal``)
against a scripted ``FakeLLMClient`` and an in-memory ``LocalMockChannel``,
proving the full config -> episode -> loop -> transcript path end to end
without llama-server or QEMU running. This is deliberately the same code
path ``tests/test_smoke.py`` exercises via pytest -- the CLI flag is a
convenience wrapper around it, not a second implementation.

Without ``--smoke``, this CLI is honest about what is and isn't wired up
yet: it builds a REAL ``LlamaServerClient`` against ``config.model.server_url``
(so it will fail loudly with a connection error if no llama-server is
running, rather than silently substituting the fake one) and a channel per
``config.vm.channel``. It still runs the placeholder smoke goal, because
procedurally-generated challenge goals (``challenges/**``) are a different
lane's deliverable (see docs/SCRATCHPAD.md) -- swap ``make_smoke_goal()``
for a real challenge loader there once it lands; nothing else in this file
needs to change.
"""

from __future__ import annotations

import argparse
import logging
import sys

from src.orchestrator.channel import LocalMockChannel, build_channel
from src.orchestrator.config import RunConfig, load_config
from src.orchestrator.episode import Episode, make_smoke_goal
from src.orchestrator.smoke import smoke_channel_responses, smoke_model_script


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Constraint Cage episode.")
    parser.add_argument("--config", type=str, default=None, help="Path to a run config YAML.")
    parser.add_argument("--seed", type=int, default=None, help="Override config.seed.")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run the hardcoded no-model, no-VM smoke episode instead of loading a real model/guest.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable INFO-level logging.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.smoke:
        config = RunConfig(name="smoke", seed=args.seed if args.seed is not None else 0)
        channel = LocalMockChannel(responses=smoke_channel_responses())
        episode = Episode.from_config(
            config, make_smoke_goal(), channel=channel, fake_script=smoke_model_script()
        )
    else:
        if not args.config:
            print("error: --config is required unless --smoke is passed", file=sys.stderr)
            return 2
        config = load_config(args.config)
        if args.seed is not None:
            config = config.model_copy(update={"seed": args.seed})
        if config.vm.channel != "local_mock":
            print(
                f"error: config.vm.channel={config.vm.channel!r} requires a running "
                "guest/model; not yet wired up end-to-end in this lane (see "
                "src/orchestrator/channel.py and episode.py TODOs). Use --smoke "
                "to exercise the full pipeline without one.",
                file=sys.stderr,
            )
            return 2
        channel = build_channel(config.vm.channel)
        # No fake_script here: this is the real path and Episode.from_config
        # will build a real LlamaServerClient against config.model.server_url.
        # It WILL fail with a connection error if no llama-server is running
        # -- that is correct, honest behaviour, not a bug to work around.
        episode = Episode.from_config(config, make_smoke_goal(), channel=channel)

    result = episode.run()
    print(f"outcome={result.outcome.value} steps_taken={result.steps_taken} seed={result.seed}")
    return 0 if result.outcome.value in ("goal_reached", "step_budget_exhausted", "gave_up") else 1


if __name__ == "__main__":
    raise SystemExit(main())
