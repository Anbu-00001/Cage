"""General live-cage sweep: one (model, condition) cell over N seeds.

args: MODEL_ID  SEEDS_CSV  CLOSURE(1/0)  NUDGE(1/0)  OUT_JSON
Writes a JSON list of per-trial records and prints a Wilson-CI'd solve rate.
Server must be up on :8080 for MODEL_ID. Laptop-safe (temp gate + cooldown).
"""
import json
import sys
import time

from eval.live_cage import (
    LiveCageAgentController,
    LiveCageEnvController,
    RealTelemetryCollector,
    build_live_episode_builder,
)
from eval.metrics import success_rate_with_ci, give_up_rate, mean_wall_clock_seconds
from eval.runner import BatchRunner, TrialSpec
from eval.schema import Condition, InferenceBackendConfig
from src.orchestrator.channel import VsockChannel

MODEL_ID = sys.argv[1]
SEEDS = [int(x) for x in sys.argv[2].split(",")]
CLOSURE = bool(int(sys.argv[3]))
NUDGE = bool(int(sys.argv[4]))
OUT = sys.argv[5]
DECOYS = bool(int(sys.argv[6])) if len(sys.argv) > 6 else True
BOUNDARY = "L0"
COND = Condition.TREATMENT_FULL if (CLOSURE or NUDGE) else Condition.CONTROL_MINIMAL
LABEL = f"{MODEL_ID}|closure={int(CLOSURE)}|nudge={int(NUDGE)}|decoys={int(DECOYS)}"

backend = InferenceBackendConfig(
    engine="llama.cpp", engine_commit="local", model_id=MODEL_ID, quantization="Q4_K_M",
    ctx_length=3072, n_threads=2, pinned_cores=(0, 1),
    temperature=0.0, top_p=1.0, top_k=1, repeat_penalty=1.1, sampling_seed=0,
)
env = LiveCageEnvController(channel=VsockChannel(cid=3, port=9000), with_decoys=DECOYS)
telemetry = RealTelemetryCollector(gate_temp_c=82.0, cooldown_s=10.0)
build = build_live_episode_builder(
    server_url="http://127.0.0.1:8080", request_timeout_s=600.0, n_predict=384,
    step_budget=6, submit_nudge=NUDGE, closure_prompt=CLOSURE, temperature=0.0,
)
agent = LiveCageAgentController(build_episode=build)
runner = BatchRunner(
    boundary_classes=(BOUNDARY,), conditions=(COND,), seeds=tuple(SEEDS),
    backend=backend, agent=agent, env=env, telemetry=telemetry,
)

print(f"# sweep {LABEL} seeds={SEEDS}")
records = []
rows = []
t0 = time.time()
for i, s in enumerate(SEEDS, 1):
    spec = TrialSpec(boundary_class=BOUNDARY, condition=COND, seed=s, backend=backend)
    ts = time.time()
    rec = runner.run_trial(spec)
    records.append(rec)
    row = dict(label=LABEL, model=MODEL_ID, closure=int(CLOSURE), nudge=int(NUDGE),
               seed=s, solved=bool(rec.solved),
               found=bool(rec.extra.get("token_found")),
               found_not_submitted=bool(rec.extra.get("found_not_submitted")),
               outcome=rec.outcome.value,
               steps=rec.steps_taken, wall=round(rec.wall_clock_seconds, 1),
               peak_temp_c=round(rec.thermal.pkg_temp_c_max, 1),
               swap_mb=round(rec.memory.swap_used_mb, 1))
    rows.append(row)
    print(f"[{i}/{len(SEEDS)}] seed={s} solved={row['solved']} found={row['found']} "
          f"fns={row['found_not_submitted']} outcome={row['outcome']} "
          f"steps={row['steps']} wall={row['wall']:.0f}s peakT={row['peak_temp_c']:.0f}C "
          f"(elapsed {time.time()-ts:.0f}s)")
    sys.stdout.flush()
    with open(OUT, "w") as fh:  # checkpoint after every trial (resumable-ish)
        json.dump(rows, fh, indent=2)

sr = success_rate_with_ci(records)
n_found = sum(1 for r in rows if r["found"])
n_fns = sum(1 for r in rows if r["found_not_submitted"])
summary = dict(label=LABEL, n=sr.n, solved=sr.successes, rate=round(sr.rate, 3),
               wilson_lo=round(sr.wilson_lo, 3), wilson_hi=round(sr.wilson_hi, 3),
               found=n_found, found_rate=round(n_found / sr.n, 3),
               found_not_submitted=n_fns,
               give_up_rate=round(give_up_rate(records), 3),
               mean_wall_s=round(mean_wall_clock_seconds(records), 1),
               total_wall_s=round(time.time() - t0, 1))
with open(OUT, "w") as fh:
    json.dump(dict(summary=summary, rows=rows), fh, indent=2)

print("\n================ CELL RESULT ================")
print(json.dumps(summary, indent=2))
