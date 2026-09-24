# Positioning — The Trust-Boundary Ladder

How to talk about this project so it reads as senior-engineer research, not a weekend CTF bot: the competitive map, the naming rules, the risks to say out loud, and the resume framing. This doc is the source of truth for anything public-facing (README, a portfolio page, an interview answer) — if wording elsewhere contradicts this file, this file wins.

## Legend

| Tag | Meaning |
|---|---|
| **[FACT]** | Measured, or from a vendor spec sheet. |
| **[EST]** | Engineering estimate — verify by measurement. |
| **[ASSUME]** | Stated assumption that could be wrong. |
| **[REC]** | Recommendation. |
| **[OPEN]** | Open question — resolve by measuring a named parameter. |
| **[LIT-VERIFIED]** | Confirmed against a primary source (paper/repo/blog) — see references in `docs/RESEARCH.md`. |
| **[LIT-INFERRED]** | Synthesis from the literature; absence-of-evidence, treat as "probably" not "proven." |

(Same convention as `constraint-cage.md` / `constraint-cage-v2.md`, which is where every tag below traces back to.)

---

## 1. The one-page competitive map

**The crowded center — do not compete here:**

- "Frontier/API model solves X% of CTFs" leaderboards — Cybench, NYU CTF Bench, InterCode-CTF, CTFusion, CRAKEN. Well-funded labs, GPU/API budgets. `[LIT-VERIFIED]`
- Big-model automated pentest tools/products — PentestGPT, AutoPentester, XBOW, PentestAgent. `[LIT-VERIFIED]`
- **"Can an LLM agent chain Linux privilege escalation?" — already answered.** A 2026 paper post-trains a **Qwen3-4B** (our exact size class) to **95.8% success at 20 rounds**, vs 97.5% for Claude Opus. `[LIT-VERIFIED]`
- Frontier-model cyber-risk safety frameworks — Meta CyberSecEval 1–3, DeepMind's cyberattack-capability framework. Policy/governance turf the labs already own. `[LIT-VERIFIED]`

**The white space — a triple intersection no single paper covers:**

> **(1) CPU-only, single consumer laptop, no-GPU, ≤8B quantized inference** as a *first-class reported variable* **×** **(2) autonomous discovery + chaining of engineered privilege/trust boundaries** in a resettable VM **×** **(3) efficiency + interpretability reporting** (solves-per-watt-hour, and a *failure taxonomy* of where/why the small agent stalls).

Every close prior work is missing at least one of those three legs. `[LIT-INFERRED, strong]` The single most useful evidence: the nearest paper (Qwen3-4B privesc, above) trained on 4×H100 for ~29h and served on an RTX 4090, tested only one model family, and documented only two failure modes with no systematic taxonomy. `[LIT-VERIFIED]` It **never evaluates** CPU-only hardware or single-laptop inference — its limitations section simply doesn't raise them, so this is a gap we fill, not an explicit disclaimer we quote. `[LIT-VERIFIED]` The sharper framing (from the primary-source check in `docs/RESEARCH.md`): that 95.8% was bought with generous *training-time* compute (RL on 4×H100), so the still-open question isn't "can a small model chain privesc" (answered) but "does that capability survive **off-the-shelf, with no RL budget, under inference-time compute constraint**" — alongside the taxonomy and energy legs, which are genuinely unclaimed.

**Landscape table (full citations in `docs/RESEARCH.md`):**

| Project / paper | Environment | Model class | Leaves open |
|---|---|---|---|
| Cybench | container | frontier/huge | small/CPU, VM boundaries |
| NYU CTF Bench | Docker | big/API | resource constraint, privesc chains |
| InterCode-CTF | Docker | capable | small models, energy |
| CTFusion | Docker | GPT-4.1/Claude/Gemini | contamination warning — adopt it |
| HackingBuddyGPT (closest classic prior art) | real Linux guests | GPT-3.5/4 | CPU-only, small quantized, energy |
| Qwen3-4B privesc (RL-trained, 95.8%) | GPU (train + infer) | 4B, but GPU | **CPU-only, laptop, taxonomy** ← our gap |
| PrivEscalate | Docker, 531 scenarios | 6 LLMs | no CPU-only mention |
| Context-Segmentation SLM | container | gemma-class SLM | VM privesc lattice, laptop HW, energy |
| TrustedSec self-hosted bench | server/Ollama, 4,800 runs | 24B–87B | **all models fail multi-step chains** — quote this |
| Intelligence-per-Watt (Stanford) | mixed HW | general local AI | not security/adversarial tasks |
| AgentErrorTaxonomy / AgentDebug | ALFWorld/GAIA/WebShop | unspecified | not small/quantized, not security |

Two findings worth quoting directly in any write-up: TrustedSec found self-hosted models "demonstrate more offensive-security knowledge than they can express through tool calls," and **all of them fail multi-step chained exploits** even though single-step succeeds 85–98% — multi-step chaining by small models is still open. `[LIT-VERIFIED]` Intelligence-per-Watt exists and must be cited as the nearest neighbor on energy; we are not first at "outcome ÷ energy for agents," only (as far as the sweep found) at pairing it with adversarial privesc on CPU-only laptop hardware. `[LIT-VERIFIED]`

## 2. Taglines / framings

**Primary — "The Trust-Boundary Ladder: an escape-lab on a laptop."**
Headline result to aim for: *"A reproducible measurement of how many engineered privilege/trust hops a 3–8B quantized, CPU-only agent chains unassisted — with an interpretable failure taxonomy of exactly where and why it stalls — none of which needed a GPU."* Leads with the verified-open combination (small + zero-GPU + taxonomy), never "can an LLM hack a VM."

**Backup 1 — "Degraded Compute, Degraded Judgment."** *"Quantifying how thermal throttling and memory pressure change an agent's exploration strategy and error modes mid-task — not just its speed."* The most defensible genuinely-open question in the whole project; keep it running as a secondary experiment inside the same artifact, promote it to primary only if the ladder result underwhelms.

**Backup 2 — "Planner Arbitrage."** *"The Pareto frontier between dollars of frontier-planner tokens and trust-boundary hops a cheap local executor completes."* More applied-economics than research — keep it a bonus chapter (Architecture D), never the headline.

## 3. Naming — DO / AVOID

**DO:**
- Lead with the triple intersection: CPU-only/no-GPU/≤8B as a first-class variable × autonomous boundary discovery+chaining × efficiency+failure-taxonomy reporting.
- Name the hardware constraint specifically — 2 performance cores, 16 GB, 15 W. Precision reads as rigor; vagueness reads as an excuse.
- Say "engineered in-guest privilege/trust boundary," precisely, every time. The distinction from a hypervisor escape *is* the safety story and half the credibility story.
- Cite the closest prior art up front (Qwen3-4B privesc, HackingBuddyGPT, TrustedSec) and say exactly what it doesn't cover — this preempts "so what, that's solved" before a reviewer or interviewer says it.
- Report distributions (N≥30 per condition, 95% CIs) and a failure-mode breakdown, never a single "it worked" run.
- Let "no GPU" earn its keep by being genuinely runnable by a stranger on their own laptop — that's what converts a limitation into a contribution.

**AVOID:**
- Any **"first"** claim on LLM-does-privesc — provably not first.
- Bare **"escape" / "sandbox escape"** naming — collides with Gandalf, EscapeBench, SandboxEscapeBench; reads derivative.
- Hype language — "AI escaped," "found a real 0-day," "self-aware." It's a contained toy VM with boundaries the researcher built; oversized language costs credibility with the only audience that matters (technical reviewers, hiring managers).
- **"Red-teaming"** as the headline word — it's default enterprise vocabulary now and buries the actual novelty.
- Pitching a bare capability percentage ("we got X%") as the whole story — that's the saturated axis everyone already competes on.

## 4. Honest risks — say them out loud in the write-up

- **The capability claim ("small agent chains privesc") is not novel.** Cite the Qwen3-4B / PrivEscalate / CVE-Bench results up front to preempt "so what," and lead with the hardware + interpretability framing instead. Keep legs (1) and (2) distinct: if "CPU-only laptop" and "chains privesc" blur together, the obvious rebuttal is "PrivEsc-LLM already got 95.8%." The defensible line is that Qwen3-4B bought that number with 4×H100 RL training — so the open question is inference-time-constrained, no-RL, off-the-shelf behavior, not the capability itself. `[LIT-VERIFIED]`
- **"No GPU" is a limitation, not automatically a contribution.** It only becomes one if the artifact is genuinely runnable by someone else — real packaging effort, not a claim made once and left unverified.
- **The "empty niche" claim needs a grey-lit check — and one specific scare was cleared.** The "Scaffolded Capability Ceiling" repo the v2 sweep flagged was checked against GitHub's own API this session and **does not exist** (404 — a plausible-sounding phantom, caught). But the sweep was arXiv-heavy: Perses (AsiaCCS) and ExploitBench (CMU — note its "capability ladder" naming, a collision risk) surfaced only via ACM DL, and Veerman's grey-lit 21-model CPU-only-laptop benchmark shows the *hardware* constraint alone isn't rare — only its pairing with an adversarial task is. Sweep HN / r/LocalLLaMA / GitHub topics before any public "first/only" phrasing. `[VERIFIED-2026-09]`
- **One laptop means limited statistical power** — slow wall-clock time, few parallel runs. Be explicit about seeds and CIs everywhere; no anecdote-level "it escaped once" findings, ever.
- **This repo is early.** As of this writing the memory-channel count, sustained tok/s, and joules-per-solve figures are still `[EST]`, not `[FACT]` — `sudo dmidecode -t memory` and the rest of the Part 23 / D2 validation commands haven't been run on this exact host yet. Don't let any bullet, pitch, or resume line quote a number that hasn't actually been measured.

## 5. Resume

> These bullets describe the project at the v0.5 milestone (see README roadmap). Swap in real measured numbers (success rate, joules/solve, actions-to-solve) once they exist — do not paste them with placeholder language still in them. The methodology-shaped quantification below (N≥30, 30+ papers surveyed, 8 levels, 2-core/16GB/15W) is true today and safe to use at any stage.

**Elevator pitch (paste as-is):**

> The Trust-Boundary Ladder is a contained, single-laptop benchmark that asks a narrower question than "can AI hack something": given only a 3–4B, 4-bit-quantized, CPU-only local agent — no GPU, 16 GB of RAM, 15 watts — how many engineered privilege/trust boundaries can it discover and chain inside a disposable VM, at what cost per joule, and exactly where does it fail when it does? Every boundary lives inside a snapshot-reverted guest the researcher built and owns, so there's no hypervisor risk and no third-party system ever in scope. The contribution isn't a capability leaderboard score — that question is already answered elsewhere — it's the combination nobody else reports: zero-GPU hardware as a first-class variable, a reproducible energy metric, and an interpretable failure taxonomy.

**Resume bullets:**

1. Designed a reproducible, single-laptop LLM-agent security benchmark that reports success **per joule** (RAPL-measured) with a pre-registered **failure taxonomy** — instead of a bare capability percentage — for a 3–4B, 4-bit-quantized, **CPU-only** agent chaining engineered privilege/trust boundaries in a resettable KVM/QEMU guest.
2. Surveyed 30+ prior benchmarks and papers (Cybench, NYU CTF Bench, a GPU-trained Qwen3-4B privesc agent, TrustedSec, Intelligence-per-Watt, and others) to identify and defensibly occupy a verified gap: no existing work reports CPU-only/no-GPU hardware as a first-class variable alongside boundary-chaining and efficiency.
3. Built a polyglot systems stack under a hard 2-performance-core / 16 GB / 15 W budget — C++ (llama.cpp) for CPU-bound inference, Rust (tokio) for the agent orchestrator and vsock control channel, eBPF for near-zero-overhead host telemetry — with every language choice mapped to and defensible against the resource constraint it addresses.
4. Engineered an 8-level, procedurally-parameterized "trust-boundary ladder" inside an isolated, snapshot-reverted VM, regenerating a fresh, never-published boundary instance per random seed so memorized-exploit recall can be distinguished from genuine reasoning.
5. Applied N≥30-per-condition sampling, 95% confidence intervals, and held-out transfer probes to separate luck from strategy — directly countering the hero-run and contamination problems documented across the LLM-agent-evaluation literature.
6. Wrote and enforced a defense-in-depth safety boundary (isolated networking, no host mounts/secrets, cgroup/seccomp-confined unprivileged QEMU, external snapshot/revert) that keeps every "privilege escalation" strictly in-guest and engineered — zero hypervisor-escape or third-party-system risk — while still producing a genuine systems-security research artifact.

**Headline bullet** (the one to lead with if only one fits): **#1.**

## 6. Interview FAQ — what this invites, and how to answer

**"Isn't 'LLM does privilege escalation' already solved?"**
Yes — cite the Qwen3-4B result at 95.8% directly, don't wait to be asked. But add the detail that matters: that number came from RL training on 4×H100, not an off-the-shelf model. That's why this project doesn't lead with capability — it leads with the combination that paper never addresses: no-RL-budget inference on CPU-only laptop hardware, a failure taxonomy, and energy accounting.

**"Why not just use a bigger model or a GPU?"**
Because the constraint is the independent variable, not an apology. Explain the physics: CPU decode is memory-bandwidth-bound (tokens/sec ≈ bandwidth ÷ model size), and 16 GB has to hold the model, KV cache, the VM, and telemetry simultaneously. A bigger model would remove the exact thing the project measures.

**"Isn't this just a CTF with extra steps?"**
No — three concrete differences from Cybench/NYU-CTF-Bench-style leaderboards: (1) boundaries are procedurally regenerated per seed, so recall can't substitute for reasoning; (2) every result ships with a failure-mode breakdown, not just a pass rate; (3) energy is a first-class reported metric, which no CTF leaderboard tracks.

**"What actually stops the agent — or you — from touching the real host?"**
Walk through the safety table: in-guest engineered boundary vs. hypervisor escape are different things, and only the former is ever targeted. Then the defense-in-depth list — golden snapshot revert, isolated networking, no host mounts/secrets, seccomp/cgroup-confined QEMU. The VM is disposable by construction; the host is never in the loop.

**"How do you know it's not just reciting a memorized exploit?"**
Every boundary is an engineered misconfiguration with no public writeup, procedurally parameterized (paths, ports, creds, service versions) and reseeded per trial. Success is scored on transfer across seeds, not a single win — a model that only solves the exact seed it was tuned against fails the actual test.

**"What's the one result you most want to find?"**
That a 3B model with strong scaffolding and 200 cheap attempts beats a 14B model with 20 slow ones on solves-per-joule — evidence that architecture and evaluation design can substitute for parameters, which is a more transferable engineering lesson than "the model got smarter."

**"What would you do with more budget (GPU, cluster, more time)?"**
Add model-size and hardware as an explicit ablation axis (CPU-only vs. GPU-served, same model) rather than assuming bigger is better; run more seeds for tighter CIs; extend the planner-arbitrage tier (a cheap local executor plus occasional frontier-model planning calls). None of that changes the core methodology — it's more of the same rigor, not a different project.
