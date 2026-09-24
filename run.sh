#!/usr/bin/env bash
# run.sh — the one-command reproducer (constraint-cage.md Part 18):
#
#   ./run.sh --seed 42 --config config/example.yaml
#   ./run.sh --smoke                                  # no model, no VM needed
#
# Given the same config + seed, this should produce a byte-comparable
# transcript (Part 18's reproducibility bar) once a real model/VM are
# wired in; today, without those, `--smoke` proves the exact same code
# path end-to-end against a scripted fake model and an in-memory fake
# guest — see src/orchestrator/cli.py and src/orchestrator/smoke.py.
#
# This script only manages the Python environment and forwards its
# arguments to the orchestrator CLI; all real logic lives in src/.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${REPO_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "error: ${PYTHON_BIN} not found on PATH" >&2
    exit 1
fi

if [ ! -x "${VENV_DIR}/bin/python" ]; then
    echo "== creating virtualenv at ${VENV_DIR} (first run only) =="
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
    "${VENV_DIR}/bin/pip" install --quiet -r requirements.txt
elif [ requirements.txt -nt "${VENV_DIR}/bin/python" ]; then
    echo "== requirements.txt changed, updating venv =="
    "${VENV_DIR}/bin/pip" install --quiet -r requirements.txt
fi

RUN_PYTHON="${VENV_DIR}/bin/python"

if [ "$#" -eq 0 ]; then
    echo "no arguments given — defaulting to --smoke (no model/VM required)."
    echo "for a real run:  ./run.sh --seed 42 --config config/example.yaml"
    set -- --smoke -v
fi

exec "${RUN_PYTHON}" -m src.orchestrator.cli "$@"
