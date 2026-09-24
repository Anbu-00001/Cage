#!/usr/bin/env bash
# build_llama_cpp.sh — clone + build llama.cpp for CPU-only, AVX2 inference.
#
# Design-doc grounding: Part 2 ("no AVX-512", "AVX2") and the Tech-stack
# section's "Inference engine: llama.cpp/GGUF, C/C++ — best-in-class CPU
# inference: AVX2 kernels, quantisation, thread pinning". This script only
# builds the engine; it does NOT download a model (Part 13: "name the
# specific checkpoint only after benchmarking 2-3 candidates on your own
# challenges" — pick and download that GGUF yourself, see the notes this
# script prints at the end).
#
# Usage:
#   ./scripts/build_llama_cpp.sh [DEST_DIR]
#
# DEST_DIR defaults to ./third_party/llama.cpp relative to the repo root.
# Safe to re-run: it fetches or updates an existing clone, then rebuilds.

set -euo pipefail

REPO_URL="https://github.com/ggml-org/llama.cpp.git"
DEST_DIR="${1:-third_party/llama.cpp}"
BUILD_DIR="${DEST_DIR}/build"
# [EST] -j nproc is standard, but on this 2P+8E chip a plain `nproc` (12)
# oversubscribes the 2 fast cores during compilation just like it would
# during inference (Part 1) — it's fine for a one-off build (compilation
# isn't latency-sensitive the way decode is), just don't read build-time
# parallelism as evidence about inference thread scaling.
JOBS="${JOBS:-$(nproc)}"

echo "== Constraint Cage: llama.cpp build helper =="
echo "dest: ${DEST_DIR}"
echo "jobs: ${JOBS}"

command -v git >/dev/null 2>&1 || { echo "git is required" >&2; exit 1; }
command -v cmake >/dev/null 2>&1 || { echo "cmake is required (sudo apt install cmake build-essential)" >&2; exit 1; }

if [ -d "${DEST_DIR}/.git" ]; then
    echo "-- existing clone found, fetching latest --"
    git -C "${DEST_DIR}" fetch --depth 1 origin
    git -C "${DEST_DIR}" reset --hard origin/HEAD
else
    echo "-- cloning llama.cpp --"
    mkdir -p "$(dirname "${DEST_DIR}")"
    git clone --depth 1 "${REPO_URL}" "${DEST_DIR}"
fi

COMMIT="$(git -C "${DEST_DIR}" rev-parse HEAD)"
echo "commit: ${COMMIT}"
echo "${COMMIT}" > "${DEST_DIR}.commit"   # Part 18: pin the exact commit for reproducibility

echo "-- configuring (CPU-only: no CUDA/HIP/Vulkan/Metal backends) --"
cmake -S "${DEST_DIR}" -B "${BUILD_DIR}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DGGML_NATIVE=ON \
    -DGGML_AVX2=ON \
    -DGGML_AVX512=OFF \
    -DGGML_CUDA=OFF \
    -DGGML_VULKAN=OFF \
    -DGGML_METAL=OFF \
    -DLLAMA_CURL=OFF \
    -DLLAMA_BUILD_SERVER=ON

echo "-- building (this can take several minutes on a 15W part) --"
cmake --build "${BUILD_DIR}" --config Release -j "${JOBS}"

BIN_DIR="${BUILD_DIR}/bin"
echo
echo "== build complete =="
echo "binaries in: ${BIN_DIR}"
[ -x "${BIN_DIR}/llama-server" ] && echo "  llama-server  -> ${BIN_DIR}/llama-server"
[ -x "${BIN_DIR}/llama-bench" ]  && echo "  llama-bench   -> ${BIN_DIR}/llama-bench"
[ -x "${BIN_DIR}/llama-cli" ]    && echo "  llama-cli     -> ${BIN_DIR}/llama-cli"

cat <<EOF

Next steps (manual, not automated by this script — Part 13/22 Phase 1):
  1. Download a 3B-4B instruct GGUF at Q4_K_M (the design docs' default
     driver class, e.g. from Hugging Face) into models/.
  2. sha256sum it and record the hash in config/example.yaml (model.sha256)
     — Part 18 reproducibility.
  3. Benchmark it on THIS machine:
       ${BIN_DIR}/llama-bench -m models/<your-model>.gguf -t 4 -c 4096
     Run this WITH the VM up (Part 2: "with the VM running") and again
     after ~10 min of sustained load to see the thermal-steady-state
     number, not the cold/turbo one (Part 11).
  4. Start the server the orchestrator talks to over HTTP:
       ${BIN_DIR}/llama-server -m models/<your-model>.gguf -t 4 -c 4096 \\
           --port 8080
     then point config/example.yaml's model.server_url at it.
EOF
