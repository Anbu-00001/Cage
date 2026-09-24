# Research brief — state of the field, and how well it actually supports the niche claim

> This is the research-validation companion to `constraint-cage.md` (feasibility) and
> `constraint-cage-v2.md` (market position). It does not re-litigate architecture, hardware
> budget, or build plan — those are settled elsewhere and out of this file's lane. This
> document answers one question as skeptically as possible: **is the claimed white space
> actually open, and how strong is the evidence either way?** Every reference cited here is
> checked in detail in `docs/REFERENCES.md`; this file synthesizes, that file substantiates.
>
> Tags: `[FACT]` `[EST]` `[ASSUME]` `[LIT-VERIFIED]` `[LIT-INFERRED]` per the source docs'
> convention, plus `[VERIFIED-2026-09]` where I personally confirmed a claim via live
> WebFetch/WebSearch this session (2026-09-24). Verification method and per-reference notes
> are in `docs/REFERENCES.md` — this file states conclusions, that one shows the work.

---

## 1. The state of the field, honestly

Four adjacent literatures were checked this session, all independently active as of
September 2026:

**LLM agents for privilege escalation / pentest / CTF.** This is not a thin literature —
it is dense and getting denser. Classic prior art (HackingBuddyGPT, 2023-2026, still being
revised) established that frontier models can autonomously chain Linux privesc against real
VM targets. Since then the field has moved specifically toward the "can a *small* model do
it" question this project wants to claim: PrivEsc-LLM (a 4B Qwen3 model post-trained with
RL, 95.8% success at 20 rounds — nearly matching Claude Opus's 97.5%), PrivEscalate (531
Docker privesc scenarios, six LLMs), Perses (small LLMs coordinated via role-heterogeneity
for misconfiguration exploitation), and Context-Segmentation SLM (small local models on
picoCTF, fighting context bloat). Two more were found this session that the v2 doc's own
sweep missed entirely: HackSynth (200 CTF challenges, 8 LLMs, same "simple solved,
multi-step not" finding TrustedSec reports independently) and the TrustedSec self-hosted
benchmark itself, which is arguably the single most relevant grey-literature data point in
the whole field for this project — 4,800 runs, 24-87B self-hosted models, confirms local
models "demonstrate more offensive-security knowledge than they can express through tool
calls" and **all of them fail multi-step chained exploits** while succeeding 85-98% at
single-step. `[LIT-VERIFIED]` `[VERIFIED-2026-09]`

**Small-model / CPU-only / edge agent evaluation.** Also dense, but mostly *not* about
security. AgentFloor (16 open-weight models 0.27B-32B vs GPT-5, 16,500+ runs) establishes
that small models already suffice for short-horizon structured tool use generally.
Intelligence-per-Watt (Stanford/Hazy Research) is the serious, well-resourced neighbor on
energy accounting for local inference — 20+ models, 8 hardware backends, 1M real queries.
NVIDIA's "Small Language Models are the Future of Agentic AI" is a widely-cited position
paper making the economic case for SLM-first agent design. None of these touch adversarial
/ security tasks. A grey-literature find this session — Mike Veerman's 21-model tool-calling
benchmark, run on a CPU-only Framework 13 laptop — is the closest match to "small model +
real consumer laptop + rigorous benchmark methodology" found anywhere in this sweep, and it
also does not touch security. `[VERIFIED-2026-09]`

**Energy accounting for agents.** Real, active, but general-purpose. Intelligence-per-Watt
(above) and a second paper found this session — "Energy per Successful Goal" / A-LEMS,
which proposes exactly the "count failed attempts and retries in the energy denominator"
framing this project would want for joules/solve — are both non-security, non-CPU-only-
specific. The Green Software Foundation's own public position is that task-level agent
energy accounting is an industry-wide measurement gap. So: the *method* of energy-per-task
accounting is not novel and shouldn't be presented as invented here, but nobody has paired
it with an adversarial security task on documented CPU-only hardware. `[LIT-VERIFIED]`
`[VERIFIED-2026-09]`

**Failure taxonomies / evaluation rigor for agents.** The strongest, most directly reusable
literature found. AgentErrorTaxonomy + AgentDebug (Zhu et al.) is a real, general-purpose
failure taxonomy with released annotated traces (ALFWorld/GAIA/WebShop) — not
security-specific, not small-model-specific, exactly matching the doc's characterization.
"Characterizing Faults in Agentic AI" (34-fault taxonomy from 13,602 mined issues) is a
second, independent, equally real taxonomy effort. On the rigor side: the ICC/stochasticity
paper (ICC as low as 0.304, meaning ~70% of variance on hard tasks is within-task noise),
the inference-backend-variance paper (~39% of score variance from backend choice alone,
confirmed verbatim), and the contamination-free RE benchmark (5,000+ expert-hours to build
genuinely novel instances) are all real and all support the same conclusion: **the field's
current hero-number, single-backend, possibly-contaminated evaluation practice is a
widely-acknowledged, actively-being-fixed problem**, and adopting these fixes (N≥30 seeds,
report ICC, pin the inference stack, procedurally regenerate instances) is a genuine,
achievable rigor advantage available cheaply to a one-laptop project. `[LIT-VERIFIED]`
`[VERIFIED-2026-09]`

---

## 2. The claimed white space, leg by leg — and how well the literature actually supports "open"

The v2 doc's pitch is a **triple intersection**: (1) CPU-only/single-laptop/no-GPU/≤8B as a
first-class reported variable, **×** (2) autonomous discovery + chaining of engineered
privilege/trust boundaries in a resettable VM, **×** (3) efficiency (joules/solve) +
interpretable failure taxonomy reporting.

| Leg | Is it actually unclaimed? | Confidence after this session's checks |
|---|---|---|
| **(1) CPU-only/laptop/no-GPU/≤8B as a reported variable, for *any* agentic task** | Partially crowded in the non-security world (Mike Veerman's 21-model laptop benchmark, AgentFloor down to 0.27B, Intelligence-per-Watt across 8 hardware classes). Nobody found this session pairs it with a *security* task. | **Medium-high.** The hardware constraint itself is not novel or rare in grey literature; its pairing with an adversarial task is what's actually unclaimed. |
| **(2) Autonomous discovery + chaining of engineered boundaries** | Multiple papers now do exactly this with small models — PrivEsc-LLM (4B, 95.8%), PrivEscalate, Perses, HackSynth. TrustedSec independently confirms multi-step chaining is *the* open problem even at 24-87B scale. | **Medium.** "Small model chains privesc" is *not* an open question anymore — it's been shown to basically work (95.8%!) under generous compute (RL training on 4×H100). What's open is whether it still works when the *inference-time* compute is also constrained (CPU-only, no RL post-training budget, off-the-shelf checkpoint) — a materially different, harder claim than the v2 doc sometimes implies. |
| **(3) Efficiency (joules/solve) + interpretable failure taxonomy, for security tasks** | The *methods* for both halves are proven and citable (Intelligence-per-Watt, A-LEMS for energy; AgentErrorTaxonomy/AgentDebug, Characterizing-Faults for taxonomies) but neither has been applied to this population (small, quantized, CPU-only) doing this task (engineered privesc chains in a VM). | **High.** This is genuinely the strongest, most defensible leg — the doc is right that a security-domain failure taxonomy for small quantized agents doesn't yet exist in the checked literature, and pairing energy accounting with adversarial tasks specifically is also unclaimed. |
| **Behavior (not just speed) under degraded compute (thermal/memory pressure)** | Edge-thermal papers (confirmed: iPhone 16 Pro loses ~50% throughput within 2 iterations under sustained load — note this is a *stronger* number than the doc's quoted "~40% in 3 iterations," which was slightly mis-cited) measure throughput/latency degradation, not *plan quality or error-mode* degradation. | **High.** No paper found this session asks whether an agent's *strategy* (not just its speed) changes under throttling. This may be the single most genuinely open sub-claim in the whole document. |

**Bottom line:** the *literal* triple intersection — all three legs simultaneously, in one
project — does appear to be unclaimed by anything found in this sweep, including a
targeted grey-literature pass (GitHub topics, Hacker News via the Algolia API, blog/Reddit
search). But "unclaimed intersection" is a weaker claim than the v2 doc's own language
sometimes implies, because **leg (2) in isolation is close to solved** at generous
inference-time compute, and **leg (1) in isolation is common** outside security. The
project's real contribution is narrower and more precise than "nobody does small +
CPU-only + privesc": it's closer to **"nobody has shown whether small-model privesc
capability survives when inference-time compute is also constrained, and nobody has
produced an interpretable, security-domain failure taxonomy for when it doesn't."** That
framing is defensible; "we're first at the whole niche" framing invites exactly the
"so what, PrivEsc-LLM already got 95.8%" pushback the v2 doc itself warns against in A5.

---

## 3. Strongest supporting evidence, and biggest risks to the novelty claim

### Strongest supporting evidence
1. **PrivEsc-LLM's own limitations are close to this project's future-work shape** — it
   trains on 4×H100 (~29h) and benchmarks inference on an RTX 4090, and documents only two
   ad hoc failure modes with no systematic taxonomy. Confirmed exactly as the v2 doc
   claims, down to the numbers. `[VERIFIED-2026-09]`
2. **TrustedSec's independent, large-N finding** (4,800 runs) that self-hosted models fail
   multi-step chaining while excelling at single-step is a real, load-bearing result that
   this project's own Level 7 (multi-stage chaining) directly targets. It's real prior
   evidence *for* the research question being non-trivial, not evidence the question is
   already answered. `[VERIFIED-2026-09]`
3. **The rigor gap is real and cheap to close.** ICC/variance, backend-variance, and
   contamination papers all independently document that the field's current practice is
   weak on exactly the axes (single-run hero numbers, unpinned inference stack,
   possibly-contaminated instances) this project's design already addresses via seeded
   procedural generation and N≥30 reporting. This is a genuine, low-cost differentiator.
   `[VERIFIED-2026-09]`

### Biggest risks to the novelty claim
1. **Leg (2) is closer to "answered" than the pitch implies.** A 4B model already hits
   95.8% on privesc chaining — with enough training compute. If reviewers read "small
   model chains privilege escalation" as the headline, PrivEsc-LLM is a direct, damaging
   comparison, and the project's actual differentiator (inference-time hardware
   constraint, not model size) needs to be foregrounded relentlessly, exactly as the v2
   doc's own A3 positioning section already recommends. This is the single biggest threat
   found this session — not a missing citation, but a framing risk in the doc's own
   headline language if leg (1) and leg (2) get conflated in a reader's mind.
2. **Grey literature is not empty, just off-target.** Two real, working, CPU-only-laptop
   small-model benchmarks exist in the wild right now (Mike Veerman's 21-model tool-calling
   bench; the general laptop-model-bench repo found in a GitHub search) — neither touches
   security, but their existence means "nobody runs rigorous small-model benchmarks on
   real laptop CPUs" is false as a general claim, even though "nobody does it for
   privilege-escalation chaining" still holds up. Precision in the public write-up matters.
3. **A specific named risk in the v2 doc turned out to be unconfirmable, not real** — see
   `docs/REFERENCES.md`'s final section. "Scaffolded Capability Ceiling" was flagged as a
   possible adjacent repo but does not resolve against GitHub's own API (404, zero search
   results). Net effect: one fewer real competitor than feared, but a reminder that this
   project's own future citation sweeps need the same "check against the primary source's
   own API/site, not just a search snippet" discipline applied here.
4. **Naming collisions are real and multiple**, beyond what v2 already flagged. This
   session additionally found "ExploitBench: A Capability Ladder Benchmark" (CMU, 2026) —
   meaning "capability ladder" language, not just "escape"/"sandbox escape", is also
   already in use nearby. SandboxEscapeBench (frontier container escapes, nested VM safety
   architecture) is close enough in *design pattern* (not just name) to this project's own
   "guest is disposable, host is sacred" containment strategy that it's worth reading in
   full before finalizing the safety-architecture writeup — not because it undermines the
   contribution, but because independent convergence on the same safety pattern is worth
   citing as validation, not ignoring.
5. **Two of the v2 doc's own methodology citations don't quite say what's claimed.** The
   "State Contamination in Memory-Augmented LLM Agents" paper is about toxicity persisting
   through memory-summary compression *within* one agent's continuous run (an AI-safety
   framing), not about state leaking *between* independent evaluation trials (a
   benchmark-hygiene framing) — which is what this project actually needs for "does VM
   snapshot revert really give a clean trial." The edge-thermal paper's iPhone number is
   off (2 iterations/~50%, not 3 iterations/~40%). Neither is fatal, both are easy fixes:
   cite the memory-laundering paper for what it actually shows, and find a more precise
   source (or just measure it directly, which this project can do more rigorously than any
   cited paper since it controls its own hardware) for the "clean reset" claim.

---

## 4. Before you claim an empty niche publicly — search these venues/terms

Checked this session (documented in full in `docs/REFERENCES.md`), but should be repeated
periodically since the field is moving monthly, and repeated again immediately before any
public claim of novelty:

- **Hacker News** — via `https://hn.algolia.com/api/v1/search?query=...&tags=story`
  (free, no auth, used this session). Queries tried this session ("local LLM privilege
  escalation agent", "CPU-only LLM agent CTF") returned **zero hits** — genuinely no HN
  discussion found under those exact phrasings, but HN search is phrase-sensitive; retry
  with "privesc", "local model hacking", "small model red team", "laptop LLM security"
  before trusting the null result.
- **r/LocalLLaMA** — standard web search does not reliably index Reddit content; this
  session's searches came back empty but that is a search-engine limitation, not
  confirmation of absence. Before a public claim, search Reddit directly (logged-in web
  search or Reddit's own search) for "privesc", "privilege escalation agent", "CTF local
  model", "VM escape LLM agent".
- **GitHub topics/search** — `github.com/topics/local-privilege-escalation` and plain
  GitHub search for combinations of "small language model" + "privilege escalation" +
  "agent" surfaced real adjacent work this session (Perses's institutional page, HackSynth,
  hackingBuddyGPT, LLM4Pentest, laptop-model-bench) that the original doc's arXiv-focused
  sweep missed entirely. **arXiv-only literature sweeps systematically under-count
  GitHub-first and blog-first grey literature** — this is the single most actionable
  process fix for future novelty claims on this project.
- **arXiv listings** directly (not just a search agent's summary) for `cs.CR` (Cryptography
  and Security) and `cs.AI` cross-listed with `cs.CR`, filtered to the last 60-90 days —
  new privesc/CTF-agent papers are appearing roughly monthly per this sweep (2603, 2605,
  2608, 2609-dated papers all found and confirmed real), so a sweep more than ~2 months old
  should be considered stale before a public claim.
- **Conference proceedings directly**, not just arXiv preprints: AsiaCCS (Perses was found
  via ACM DL, not arXiv, and would have been missed by an arXiv-only sweep), ICML/ICLR
  workshops (SandboxEscapeBench is an ICML 2026 poster), ESORICS workshops (RAISE 2026,
  where Context-Segmentation SLM was accepted).
- **Company/lab blogs** doing informal benchmarking: TrustedSec (found and heavily used
  this session), and by extension similarly-positioned security consultancies/red-team
  shops that sometimes publish grey-literature benchmarks outside arXiv entirely.

---

## 5. What this session could and couldn't do

**Could:** verify 33 of 33 references from the v2 doc's bibliography against live primary
sources (arXiv abstract/HTML pages, GitHub repos/APIs, blog posts, an official Intel spec
page) — see `docs/REFERENCES.md` for the full per-reference breakdown. 29 fully VERIFIED,
4 PARTIAL (specific sub-claims off or stretched, source itself real and on-topic), 0
CONTRADICTED, 0 fully UNVERIFIED among the original 33. Additionally found and verified 7
missing-but-relevant sources (Perses, HackSynth, Energy-per-Successful-Goal, ExploitBench,
Local Agent Bench, the PrivEsc-LLM code repo, and — as a negative result — the
non-existence of "Scaffolded Capability Ceiling").

**Could not:** exhaustively search Discord, private Slack communities, or non-English
grey literature, which the v2 doc's own confidence note already flags as out of scope for
this kind of sweep. Could not access paywalled venues beyond what abstract pages and ACM's
public DOI page exposed. Treat this brief as materially stronger evidence than the original
4-agent sweep (every citation was independently re-fetched, not just summarized), but not
as a substitute for a dedicated grey-literature pass immediately before any public
"first"/"unclaimed niche" statement — per Section 4 above.
