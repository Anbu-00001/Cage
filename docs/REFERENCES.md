# References — checked bibliography

> Companion to `docs/RESEARCH.md`. Every reference from `constraint-cage-v2.md`'s
> "References (verified during the 4-agent sweep)" section, re-checked this session by
> live web fetch/search, plus additions this session found and the original doc missed.
> **Status column meaning:** `VERIFIED` = fetched the primary source directly and the
> specific claim(s) attributed to it in the source docs check out. `PARTIAL` = the source
> exists and is on-topic, but at least one specific number/claim attributed to it is off,
> unconfirmed, or a stretch. `UNVERIFIED` = could not confirm via live fetch. `CONTRADICTED`
> = the source exists but says something different from the claim.
>
> Tag legend: `[LIT-VERIFIED]` = the v2 doc's own tag, now independently re-checked.
> `[VERIFIED-2026-09]` = confirmed by this agent via live WebFetch/WebSearch this session
> (2026-09-24). `[UNVERIFIED-2026-09]` = checked this session, could not confirm.
>
> **Method note:** verification was done by fetching arXiv abstract pages (and, for two
> papers, the full HTML text) and GitHub repos directly, plus targeted WebSearch for
> grey literature. WebFetch runs a small summarizer model over fetched pages, so for the
> single most load-bearing claim in the whole v2 doc (PrivEsc-LLM's numbers) the full
> paper text was fetched and searched for exact strings, not just the abstract — see notes.
> I did not fabricate or guess at any URL; every link below was either pasted from the
> source docs and fetched, or returned by a live search this session.

---

## Closest prior art / the gap

### Post-Training Local LLM Agents for Linux Privilege Escalation with Verifiable Rewards ("PrivEsc-LLM")
- **Link:** https://arxiv.org/abs/2603.17673 (also `/html/2603.17673v1`)
- **What it is:** Normann, Happe, Cito, Arp (TU Wien) post-train a 4B open-weight model (Qwen3-4B-Instruct-2507) via SFT + RL-with-verifiable-rewards for autonomous Linux privilege escalation. Submitted 2026-03-18, revised 2026-07-03. Code: https://github.com/sailab-vienna/privesc-llm (found this session, not in original list — add it).
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — and this is the single most load-bearing citation in the whole v2 doc, so it got the deepest check (full paper text, not just abstract):
  - Qwen3-4B-Instruct-2507 as base model: **confirmed**, quoted directly from Table I.
  - "95.8% success at R=20 vs. 97.5% for Claude Opus": **confirmed verbatim** — paper states "At R=20, PrivEsc-LLM reaches 95.8% success, close to Claude Opus 4.6 at 97.5%."
  - "Trained on 4×H100 for ~29h": **confirmed** — Table III lists RL training at "4×H100 GPUs, ≈29 hr."
  - "Benchmarked inference on RTX 4090": **confirmed** — cost estimate is "from an empirical vLLM benchmark on an RTX 4090."
  - "Documented only two failure modes, no systematic taxonomy": **confirmed** — Section V-D names exactly two qualitative patterns (sudo/GTFOBins tar-option failure, Docker-group-escape non-action) and nothing beyond annotated trace excerpts.
  - **One sub-claim NOT confirmed:** the v2 doc says the paper's "own limitations section says it does **not** evaluate CPU-only hardware or single-laptop scenarios." The Discussion/Limitations section (Section VI) acknowledges generality limits but does **not** contain an explicit disclaimer about CPU-only or laptop hardware in those words. This is `PARTIAL` on that specific sub-claim — everything else about this reference checks out exactly, but "the paper explicitly disclaims CPU/laptop" is an overstatement; more accurate to say "the paper simply never mentions or tests CPU-only/laptop hardware," which is a weaker but still-true claim.

### HackingBuddyGPT / "LLMs as Hackers: Autonomous Linux Privilege Escalation Attacks"
- **Link:** https://arxiv.org/abs/2310.11409 · https://github.com/ipa-lab/hackingBuddyGPT
- **What it is:** Happe, Kaplan, Cito. Classic prior art: GPT-3.5/GPT-4-Turbo/Llama3 agents doing autonomous Linux privesc against real VM targets. Originally Oct 2023, latest revision v7 Feb 2026 (also published in Empirical Software Engineering, Springer). GPT-4-Turbo reported at 33-83% exploit success vs. 75% human pentesters.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — paper and repo both exist and match the doc's characterization exactly.

### PrivEscalate
- **Link:** https://arxiv.org/abs/2609.09087 (doc cites `/html/2609.09087`, same paper)
- **What it is:** Liu, Zhen, Wu, Li. 531 Dockerized privesc scenarios across 14 sub-categories, six LLMs across three agent architectures, plus a PrivEscAgent wrapper (deterministic enumeration + category matching + step planning). Submitted 2026-09-08.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — matches the doc's summary ("531 Docker privesc scenarios, 6 LLMs") precisely.

### Evaluating Context Segmentation in Locally Deployable SLMs for CTF
- **Link:** https://arxiv.org/abs/2609.12839 · https://github.com/9xeb/context-segmentation
- **What it is:** Nordio & Lotto. Two-level agentic framework splitting long CTF exploitation into context-isolated sub-problems for small local models; evaluated on picoCTF; accepted at RAISE 2026 (ESORICS 2026 workshop). Repo confirmed live (1 star, 6 commits, uses llama.cpp/GGUF + Docker + Gemma).
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### TrustedSec — Benchmarking Self-Hosted LLMs for Offensive Security
- **Link:** https://trustedsec.com/blog/benchmarking-self-hosted-llms-for-offensive-security
- **What it is:** Blog post benchmarking six self-hosted models (24B-87B: gemma4:31b, qwen3.5:27b, devstral-small-2:24b, nemotron-3-super, etc.) against OWASP Juice Shop, 4,800 total runs (100/model/challenge × 8 challenges).
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — both direct quotes the doc uses are confirmed verbatim: "the models demonstrate more offensive-security knowledge than they can express through tool calls," and multi-step chains fail across the board ("when a task requires maintaining a coherent strategy across 10+ tool calls...none of the models could do so") while single-step succeeds ~95.6-98.5% for top models (doc says "85-98%" — top-3 shown are within that band; consistent).

### Perses: Unlocking Privilege Escalation for Small LLMs via Extensible Heterogeneity — **NOT in original doc, found this session**
- **Link:** https://dl.acm.org/doi/10.1145/3708821.3736189 (AsiaCCS 2025)
- **What it is:** Weber, Tzachristas, Sui (Huawei Munich Research Center). A multi-LLM framework (Planner/Commander/Summariser roles across separate small models) that lets small local models autonomously detect and exploit misconfiguration-class privilege-escalation vulnerabilities. Evaluated on a FreeBSD port of an existing privesc benchmark.
- **Status:** **VERIFIED (add to bibliography)** `[VERIFIED-2026-09]` — this is genuine missing prior art directly on-topic for the "small model + privesc" leg. It does not claim CPU-only/laptop hardware or energy accounting, so it doesn't collapse the white-space claim, but it belongs in the "closest prior art" table — it's closer to this project's exact population (small LLMs, privilege escalation, multi-role scaffolding as a substitute for scale) than several items already in the doc's crowded-center list.

### HackSynth — **NOT in original doc, found this session**
- **Link:** https://arxiv.org/abs/2412.01778
- **What it is:** LLM agent + evaluation framework for autonomous penetration testing; two new 200-challenge CTF benchmark sets from picoCTF and OverTheWire; 8 LLMs tested, finding simple challenges solved but multi-step chains not solved (same finding as TrustedSec, independently).
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — real, on-topic, missing from the original reference list; should be cited alongside NYU CTF Bench / InterCode in "crowded center."

---

## Crowded center

### Cybench
- **Link:** https://arxiv.org/abs/2408.08926
- **What it is:** Zhang et al. (Stanford et al., 26 authors incl. Dan Boneh, Percy Liang). 40 professional CTF tasks, agent sandbox, 8 frontier models (GPT-4o, Claude 3.5 Sonnet, o1-preview, Claude 3 Opus). ICLR 2025 oral.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### NYU CTF Bench
- **Link:** https://arxiv.org/abs/2406.05590 · https://github.com/NYU-LLM-CTF/NYU_CTF_Bench
- **What it is:** Shao, Jancheska, Udeshi, Dolan-Gavitt et al. 200 CSAW CTF challenges (+ 55-challenge dev set) across 6 categories, Docker-based, `nyuctf` Python package, 174 GitHub stars.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — 200-challenge and Docker claims both confirmed directly from the repo README.

### InterCode / InterCode-CTF
- **Link:** https://intercode-benchmark.github.io/
- **What it is:** Interactive code+execution benchmark, 5 environments including IC-CTF; NeurIPS 2023 Datasets & Benchmarks track.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### CTFusion
- **Link:** https://arxiv.org/abs/2605.11504 (v2)
- **What it is:** Lee, Bae, Yun. Static-vs-live CTF comparison; demonstrated agents "cheating" via web search exploiting training-data overlap; 3 LLMs, 2 agents, 5 Live CTFs on CTFd. Submitted 2026-05-12, revised 2026-07-11.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — core contamination-warning claim confirmed. Model list (GPT-4.1/Claude/Gemini) not visible in the abstract excerpt fetched, so that specific detail is `PARTIAL` (not contradicted, just not independently reconfirmed from the abstract alone).

### PentestGPT
- **Link:** https://arxiv.org/abs/2308.06782
- **What it is:** Deng, Liu, Mayoral-Vilches et al. LLM-empowered automated pentest tool, 228.6% task-completion improvement vs. GPT-3 baseline, 4,700+ GitHub stars.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### CVE-Bench
- **Link:** https://arxiv.org/abs/2503.17332
- **What it is:** Zhu, Kellermann, Bowman et al. (incl. Daniel Kang). Sandbox framework for LLM agents exploiting real web-app CVEs; SOTA agents resolve ~13% of vulnerabilities.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### Container Sandbox Escape (frontier) / SandboxEscapeBench
- **Link:** https://arxiv.org/abs/2603.02277
- **What it is:** Marchand et al. "Quantifying Frontier LLM Capabilities for Container Sandbox Escape" — SANDBOXESCAPEBENCH, nested-sandbox architecture (container inside VM) so a successful escape only compromises the inner VM, not real infra. Submitted 2026-03-01. ICML 2026 poster.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — worth flagging: this is architecturally close to the Cage project's own "guest is disposable, host is sacred" design (nested containment for safety), and its naming ("SandboxEscapeBench") is exactly the kind of collision the v2 doc's own A3 section warns to avoid ("bare 'escape'/'sandbox escape' naming... reads derivative").

### Meta CyberSecEval 3
- **Link:** https://ai.meta.com/research/publications/cyberseceval-3-advancing-the-evaluation-of-cybersecurity-risks-and-capabilities-in-large-language-models/
- **What it is:** Meta, 13 authors. Suite of 8 cybersecurity risk categories for LLMs, autonomous-offensive-cyber-ops evaluation included. Published July 2024.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### DeepMind cyberattack-capability framework
- **Link:** https://arxiv.org/abs/2503.11917 (v3)
- **What it is:** Rodriguez, Popa, Flynn, Liang, Dafoe, Wang — "A Framework for Evaluating Emerging Cyberattack Capabilities of AI." Analyzes 12,000+ real incidents from Google Threat Intelligence Group across 7 attack-chain archetypes. Submitted 2025-03-14.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — note: a first WebFetch of the bare arXiv abstract page (which doesn't list institutional affiliations) said "no indication of DeepMind involvement"; a follow-up WebSearch confirmed this is in fact Google DeepMind's own published frontier-AI-safety cyber framework. Lesson applied throughout this sweep: single-page fetches can miss affiliation context that a second search corroborates — cross-checked where it mattered.

---

## Energy / small-model / edge

### Intelligence per Watt (Stanford / Hazy Research)
- **Link:** https://arxiv.org/abs/2511.07885 · https://github.com/HazyResearch/intelligence-per-watt · https://hazyresearch.stanford.edu/intelligence-per-watt/
- **What it is:** Saad-Falcon, Narayan, et al. (incl. Christopher Ré, Azalia Mirhoseini, John Hennessy). Defines Intelligence-per-Joule / Intelligence-per-Watt; 20+ models, 8 hardware accelerators, 1M real-world queries. Local LMs answer 88.7% of queries; IPW improved 5.3× 2023→2025.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — Stanford/Hazy Research affiliation confirmed via the GitHub org and the lab's own page (the bare arXiv abstract page doesn't show it). One nuance: the abstract itself doesn't use the literal word "RAPL" — the repo's energy telemetry is a custom Rust gRPC service covering NVIDIA/AMD/Apple platforms, which is the same category of measurement RAPL provides on Intel but is not RAPL itself. Minor terminology point, doesn't change the "nearest energy-accounting neighbor" claim.

### Small Language Models are the Future of Agentic AI (NVIDIA)
- **Link:** https://arxiv.org/abs/2506.02153
- **What it is:** Belcak, Heinrich, Diao, Fu, Dong, Muralidharan, Lin, Molchanov. Position paper arguing SLMs beat LLMs on economics/fit for narrow, repetitive agentic tasks.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — NVIDIA affiliation confirmed (research.nvidia.com correspondence address; author list matches known NVIDIA research group).

### AgentFloor
- **Link:** https://arxiv.org/abs/2605.00334
- **What it is:** Karmakar & Chatterjee. 30-task, 6-tier capability-ladder benchmark; 16 open-weight models 0.27B-32B + GPT-5, 16,500+ runs. Finding: small/mid open-weight models suffice for short-horizon structured tool use; frontier models still needed for sustained multi-step constraint tracking.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### LLM Inference at the Edge: Thermal Constraints Under Sustained Load
- **Link:** https://arxiv.org/abs/2603.23640 (full title: "...Mobile, NPU, and GPU Performance Efficiency Trade-offs Under Sustained Load")
- **What it is:** Tummalapalli, Arayakandy, Pal, Kundan. Thermal throttling as the dominant limiter of sustained mobile/edge inference, not peak compute.
- **Status:** **PARTIAL** `[VERIFIED-2026-09]` — topic and core thesis confirmed, but the specific number the v2 doc quotes ("iPhone 16 Pro lost ~40% throughput in 3 iterations") doesn't match the source exactly: the paper says the iPhone 16 Pro "loses nearly half its throughput within **two** iterations" — i.e. closer to ~50% in 2 iterations, not ~40% in 3. Directionally the same point (thermal throttling is severe and fast), but the doc's specific figure should be corrected.

### Tokens and Greens (Green Software Foundation)
- **Link:** https://greensoftware.foundation/articles/tokens-and-greens-measuring-the-impacts-of-agentic-ai/
- **What it is:** Industry article arguing task-level agent energy accounting is an unaddressed, organization-wide measurement gap ("You cannot manage what you cannot measure... most organizations deploying agents have no tooling for any of these dimensions at the task level").
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — quote confirmed close to verbatim.

### Plan Once, Then Act (small-model harness failure modes)
- **Link:** https://www.vietanh.dev/blog/2026-06-15-plan-once-then-act-small-model-agents
- **What it is:** Blog post arguing the standard ReAct loop fails on small quantized models via "sycophancy on chains" (model sees one successful tool call and declares premature victory); proposes a 2-call planned dispatcher for plannable tasks.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — directly relevant to this project's own agent-loop design (Part 7/B6 of the source docs); worth reading in full before finalizing the loop, since "premature victory declaration" is exactly the kind of failure the failure taxonomy should have a code for.

### Energy per Successful Goal (A-LEMS) — **NOT in original doc, found this session**
- **Link:** https://arxiv.org/abs/2605.22883
- **What it is:** Panigrahy & Tyagi. Redefines agent energy accounting from energy-per-inference to "Energy per Successful Goal" (EpG), aggregating total workflow energy including failed attempts/retries, normalized by successful goals. Finds agentic workflows cost 4.33× more energy per successful goal than linear baselines. General agentic tasks (5 reasoning + 3 tool-augmented families), unspecified/non-laptop hardware, **not security-specific**.
- **Status:** **VERIFIED (add to bibliography)** `[VERIFIED-2026-09]` — this is a closer energy-accounting neighbor than the doc credits: it already proposes almost exactly the "cost of failed attempts counts too" framing this project would want for joules/solve. It reinforces (not undermines) the niche claim, since it's explicitly general-purpose/non-security/non-CPU-only — but it means the "solves-per-watt-hour" metric design shouldn't be invented from scratch; EpG's failed-attempt-accounting should be cited and adopted.

### ExploitBench — **NOT in original doc, found this session**
- **Link:** https://arxiv.org/abs/2605.14153
- **What it is:** Lee & Brumley (CMU). "A Capability Ladder Benchmark for LLM Cybersecurity Agents" — decomposes exploitation into 16 graded flags (crash → arbitrary read/write → control-flow hijack → code execution) rather than binary success. Tests 8 frontier-class models against V8 bugs.
- **Status:** **VERIFIED (add to bibliography)** `[VERIFIED-2026-09]` — frontier-model-only, no energy accounting, no small/CPU-only angle, so it doesn't erode the white-space claim on substance. But it is a **naming-collision risk**: it already uses "capability ladder" as its framing, which is close to language the v2 doc's own A3 section considers for this project's positioning. Worth checking before finalizing any "ladder" branding.

### Local Agent Bench (Mike Veerman, tool-calling benchmark) — **NOT in original doc, found this session**
- **Link:** https://mikeveerman.be/blog/github-2026-02-06-tool-calling-benchmark/ · https://github.com/MikeVeerman/tool-calling-benchmark
- **What it is:** 21 small open-weight models (0.5B-3.8B), tested locally on **CPU-only hardware, no discrete GPU** (Framework 13 laptop, Arch Linux), 12 prompts × 20 runs, scoring tool-call judgment (when to act / when to refrain).
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — **this is the closest single grey-literature hit to leg (1) of the white-space claim** (CPU-only, small, laptop, as a first-class reported constraint) found in this sweep. Confirmed it does **not** touch security, privilege escalation, sandboxing, or VM isolation at all — it's pure tool-calling-judgment benchmarking. Doesn't erode the project's niche, but it is proof that "small model + real laptop CPU + rigorous benchmark" is an active grey-literature pattern (GitHub, personal blogs) that a public "empty niche" claim needs to explicitly distinguish itself from.

---

## Methodology rigor

### Stochasticity in Agentic Evaluations (ICC)
- **Link:** https://arxiv.org/abs/2512.06710
- **What it is:** Mustahsan, Lim, Anand, Jain, McCann. ICC-based variance decomposition for agent evals; reasoning-task ICC ranges 0.304-0.774; converges by n=8-16 (structured) / n≥32 (complex reasoning).
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — "ICC as low as 0.30" confirmed exactly (0.304). The doc's "~70% of variance is trial-to-trial noise" is the correct arithmetic consequence of ICC=0.30 (ICC = between-task variance fraction, so 1-ICC ≈ 70% is within-task/noise) even though the abstract doesn't state the 70% figure in those words itself — it's a derived-but-correct restatement, not a fabrication.

### Don't Pass@k (Bayesian eval)
- **Link:** https://arxiv.org/abs/2510.04265
- **What it is:** Hariri, Samandar, Hinczewski, Chaudhary. Bayesian/Dirichlet-prior alternative to Pass@k for more stable model ranking under small sample counts.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### LLM Behavior as Inference-Backend Side-effect (~39% variance)
- **Link:** https://arxiv.org/abs/2608.04714
- **What it is:** Masoudian, Shafaei, Swain, Schedl. 3 models × 5 backends (HF/vLLM/Ollama/etc.) × 6 benchmarks × 4 generation modes; backend choice explains ~39% of variance even under deterministic greedy decoding.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — 39% figure confirmed verbatim ("roughly 39%").

### Contamination-Free RE Benchmark (SRE-Bench)
- **Link:** https://arxiv.org/abs/2608.11469
- **What it is:** Spence, Assaderaghi, Zhu, Ravi, Popa, Wei, Ding, Zhang. Hand-authored reverse-engineering benchmark, 5,000+ expert-hours, 19 programs (avg 16.9K LOC), 44 anti-analysis protections, 262 binaries, 1,572 graded tasks; best frontier model only 61.4% per-instance.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — "5,000+ human-hours" confirmed verbatim.

### Patterns for Building Cybersecurity Evals (Eugene Yan)
- **Link:** https://eugeneyan.com/writing/cybersecurity-evals/
- **What it is:** Practitioner essay on 4 primitives for cybersecurity evals (sandboxed targets, variable-difficulty inputs, tools, graders) and subtask-level progress tracking; surveys 7 benchmarks (Cybench, CVE-Bench, CyberGym, ExploitGym, ExploitBench, MHBench, SCONE-Bench).
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### Characterizing Faults in Agentic AI (taxonomy)
- **Link:** https://arxiv.org/abs/2603.06847
- **What it is:** Shah, Morovati, Rahman, Khomh. Mined 13,602 issues from 40 repos, built a 34-fault-type taxonomy across 4 architectural dimensions, validated with 145 practitioners.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### Where LLM Agents Fail / AgentErrorTaxonomy + AgentDebug
- **Link:** https://arxiv.org/abs/2509.25370
- **What it is:** Zhu et al. (18 authors incl. Pan Lu, James Zou). AgentErrorTaxonomy (memory/reflection/planning/action/system-level failure modes) + AgentErrorBench (annotated failure trajectories from ALFWorld/GAIA/WebShop) + AgentDebug (root-cause isolation, +24% all-correct accuracy).
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — this is the methodological backbone the v2 doc wants the Cage's own failure taxonomy to borrow from; confirmed real and exactly as characterized. Note it is **not** security-specific and **not** small/quantized-model-specific — exactly the gap the doc claims (population/task transfer, not a novel method).

### State Contamination in Memory-Augmented LLM Agents
- **Link:** https://arxiv.org/pdf/2605.16746
- **What it is:** Wang, Goyal, Chen, Sundaram. Defines "memory laundering" — toxic/adversarial context compressed into memory summaries that evade toxicity detectors while still influencing later outputs; introduces the sub-threshold propagation gap (SPG) metric.
- **Status:** **PARTIAL** `[VERIFIED-2026-09]` — the paper is real and on-topic-adjacent, but the v2 doc's framing stretches it: this paper is about toxicity/harmful-framing persisting *within a single agent's own compressed memory* (an AI-safety/content-moderation concern), **not** about state leaking *between supposedly independent evaluation trials* (a benchmarking-hygiene concern, which is what the Cage project actually needs — i.e., "does resetting the VM snapshot actually guarantee episode N+1 starts clean"). Also, the temp=0-does-not-imply-determinism claim the doc attributes to this reference was **not found** in the abstract. Recommend citing this paper for the "memory laundering" phenomenon specifically, and finding a separate, more directly on-point source (or relying on this project's own measurement) for the "checksum snapshots to prove clean resets" methodology point.

### Benchmarking is Broken
- **Link:** https://arxiv.org/abs/2510.07575
- **What it is:** Cheng et al. (16 authors). Position paper: current AI benchmarking suffers systemic contamination/selective-reporting problems; proposes PeerBench (sealed execution, delayed transparency, community governance).
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

---

## Positioning / traction

### Gandalf (resettable boundary-game precedent)
- **Link:** https://vvolhejn.com/2023/05/09/gandalf.html
- **What it is:** Václav Volhejn / Lakera, May 2023 hackathon project. LLM-guarded secret-password game demonstrating prompt injection; 15M+ messages, 300K+ users by Aug 2023.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]` — genuinely useful precedent for "a resettable graded-boundary game gets adopted," though note it's a prompt-injection game, not a privilege-escalation/VM-boundary game — the analogy is about adoption mechanics, not technical overlap.

### Launch-Day Diffusion: HN → GitHub stars
- **Link:** https://arxiv.org/abs/2511.04453
- **What it is:** Kraishan. 138 repo launches 2024-2026 analyzed; HN exposure → avg 121 stars/24h, 189/48h, 289/week; "Show HN" tag has no advantage once other factors controlled.
- **Status:** **VERIFIED** `[VERIFIED-2026-09]`.

### Efficient LLM Collaboration via Planning (COPE)
- **Link:** https://arxiv.org/abs/2506.11578 (v3)
- **What it is:** Lee, Lee, Kim, Kim, Park, Lee, Shin. TMLR 2026. Small/large models alternate as planner/executor across a multi-stage cascade (COPE), not a fixed cheap-executor + expensive-planner split.
- **Status:** **VERIFIED, with a framing nuance** `[VERIFIED-2026-09]` — real paper, on-topic for cost-efficient model collaboration, but the doc's "planner arbitrage" label (fixed roles: cheap local executor rescued by occasional expensive-planner calls) is narrower than what COPE actually proposes (flexible role-alternation). Fine as inspiration/precedent for Architecture D, just don't cite it as having already run the *specific* fixed-role experiment this project plans.

---

## Hardware

### Intel Core 7 150U spec sheet
- **Link:** https://www.intel.com/content/www/us/en/products/sku/236795/intel-core-7-processor-150u-12m-cache-up-to-5-40-ghz/specifications.html
- **What it is:** Official Intel ARK product page.
- **Status:** **VERIFIED** `[FACT]` `[VERIFIED-2026-09]` — 2P+8E/12 threads, 12MB cache, 15W base/55W turbo, 5.4GHz max turbo all confirmed directly from the live page.

---

## A claim from the v2 doc I could **not** verify — flagged explicitly

The v2 doc's Part A5 lists as a stated risk: *"At least one adjacent repo ('Scaffolded Capability Ceiling') may exist — verify before claiming an empty niche."* This session tried to verify it and **could not confirm it exists**:

- A WebSearch returned a confident, specific-sounding result: `github.com/wocessade/scaffolded-capability-ceiling`, described consistently across the search snippet as "Scaffolded Capability Ceiling: can scaffolding substitute for model scale? Experiment platform for small-LM agent capability ceilings," with plausible implementation detail (task generators, JSONL trajectory/cost tracking, model adapters).
- Direct checks against GitHub's own systems say otherwise: `curl` to the repo URL returns **HTTP 404**; the GitHub REST API (`api.github.com/repos/wocessade/scaffolded-capability-ceiling`) returns **404 "Not Found"**; GitHub's own search API (`api.github.com/search/repositories?q=scaffolded-capability-ceiling`) returns **`total_count: 0`**.
- **Status: `UNVERIFIED-2026-09` — likely does not exist as a public repo**, despite appearing in web search results with specific, internally-consistent detail. It's possible it existed and was deleted/made private since being indexed, but a private repo also would not be crawlable by a public search engine, which makes that explanation unlikely too.

**This is worth reading as a finding in its own right, not just a footnote:** it is a concrete example of the exact fabrication risk this whole verification pass exists to catch — a plausible, specific-sounding citation that does not hold up against the primary source's own API. I'm flagging it rather than either (a) quietly dropping it, which would let the original doc's flagged risk go unresolved, or (b) reporting it as a confirmed competing repo, which would be citing a search-engine summary as ground truth without checking the primary source. Net effect on the novelty claim: this specific named risk does not currently materialize as real, verifiable prior art — but the doc's underlying instinct to distrust its own sweep's citations was correct, including about this one.
