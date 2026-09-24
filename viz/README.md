# viz/ — The Trust-Boundary Ladder showcase

`index.html` is a single, self-contained, dependency-free web showcase for **The Trust-Boundary Ladder** ("Constraint Cage"): a self-playing animation of a tiny (3–4B, 4-bit-quantized), CPU-only agent sprite persisting up the graded L1→L7 ladder of engineered in-guest trust boundaries — probing, forming a hypothesis, bouncing off a boundary when it fails, writing that dead end into a visible **failure memory** so it stops repeating it, retrying a different approach, and occasionally crossing to the next rung (with L6/L7 needing a chain of hops). An ambient HUD shows illustrative telemetry — tokens/sec, CPU °C with a live thermal-throttle badge, joules-per-solve, step budget — and the project's pre-registered six-category failure taxonomy lighting up as outcomes occur.

## How to open it

Just open the file in a modern browser — no build step, no server:

```bash
xdg-open viz/index.html      # or: open viz/index.html  (macOS)
```

It auto-plays on load. Controls: **Pause/Play**, **Step**, **New seed** (builds a fresh procedural instance and restarts from L1), a **speed** toggle (0.6× / 1× / 1.8×), and a **light/dark** toggle. Hover any ladder rung or taxonomy code to read what it means in the Inspector. Google Fonts are loaded via CDN for polish but degrade gracefully to system fonts offline; everything else is inline.

## Approach: 2D canvas + DOM HUD (not three.js), and why

The story the project wanted is character-driven — "a guy jailbreaking and re-trying different approaches," where the drama is *persistence*: failing, learning, and retrying smarter. A hand-drawn, cartoonic **2D canvas** scene (blueprint + terminal-neon aesthetic) tells that far better than 3D: it gives tight, expressive control over the sprite's bounce-off-a-boundary recoil, dizzy/surprised/happy faces, the failure-memory panel filling up, and a smooth camera that climbs the ladder — while staying tiny (~65 KB, one file), fast, and cross-browser. three.js would add weight and a generic look without serving the "fun to watch" retry loop any better. The animated cage lives in `<canvas>`; the readable telemetry, ladder, taxonomy, and failure-memory panels are DOM/CSS so the numbers stay crisp and accessible. Motion respects `prefers-reduced-motion` and avoids harsh flashing.

## Honesty caveat

Everything on the page is an **illustrative simulation**, not real measurement. The sprite, the ladder physics, and every number (tokens/sec, °C, joules, taxonomy counts) are hand-tuned for the story — seeded so "New seed" genuinely changes the run, but not instrumented telemetry. This mirrors the project's own brand of honesty over hype: every "escape" depicted means crossing an **in-guest** boundary the researcher engineered on purpose inside one **disposable Alpine KVM guest** on their own laptop — never a hypervisor/VM escape, never a real or third-party system, only planted fake credentials, reset to a golden snapshot every trial. Real figures come from the actual harness (RAPL joules, `turbostat`, `llama-bench`) and are reported with confidence intervals in `docs/` — see `docs/EVALUATION.md` and `docs/CHALLENGES.md`.
