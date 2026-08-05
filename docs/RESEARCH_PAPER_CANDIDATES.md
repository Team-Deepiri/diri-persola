# Research Paper Candidates — Diri Persola

**Status:** Draft for team discussion
**Purpose:** Candidate angles for a Deepiri-authored research paper built on Persola, ranked by novelty vs. feasibility given the current codebase.

---

## 1. Communal City as an emergent multi-agent society (strongest candidate)

Persola's Communal City gives agents parent/child lineage, inherited personality traits, a shared "commons" workspace, and generational death/legacy — a genuinely different structure from the standard swarm-of-interchangeable-agents literature.

**Core question:** Does inherited personality variation plus family structure improve task cohesion and output quality over homogeneous agent teams at scale?

**What it needs:** Controlled experiments — ablate lineage/inheritance vs. random trait assignment, measure task success, coordination overhead, and diversity of outputs. Currently at design/Phase 1–13 stage (see `docs/COMMUNAL_CITY_DESIGN.md`), not yet an evaluated system.

---

## 2. Personality parameterization and trait-consistency evaluation

The 40-parameter framework (creativity, personality, thinking, reliability) maps human-legible traits to sampling params and system-prompt construction.

**Core question:** Does an agent measurably behave in line with its knob settings (e.g., 20% more "humorous") consistently across turns?

**What it needs:** A trait-consistency eval harness. The underlying engine already exists (`persola/core`, `persola/tuning`), so this is the fastest path to a submittable paper. Closest to existing Big-Five / persona-conditioning literature, so least novel of the top candidates.

---

## 3. Writing-sample-to-personality extraction

Persola ingests writing samples and extracts personality traits to seed a persona (`persola/personality/`).

**Core question:** Can stable, controllable persona parameters be reliably inferred from a small writing sample, and does an agent conditioned on those parameters reproduce the author's stylistic/behavioral signature better than a hand-tuned baseline?

**What it needs:** Verification of how mature the current tone-analysis implementation actually is before committing — success hinges on it. Related to stylometry / authorship-style-transfer literature.

---

## 4. Persona blending as interpolation in trait-space

Persona blending (`POST /api/v1/personas/blend`) treats personalities as points in a continuous parameter space that can be combined.

**Core question:** Is trait-space linear/convex in a behaviorally meaningful sense — does blending 50/50 humor+empathy actually land in between on held-out evaluations?

**What it needs:** Low implementation lift since blending already exists. Tightly scoped, but a minor contribution unless the trait-space geometry finding is surprising.

---

## 5. Cross-model personality portability

Persola supports OpenAI, Anthropic, and Ollama, generating system prompts and sampling params per model.

**Core question:** Do the same 40 knob settings produce consistent personality behavior across different underlying LLMs, or does personality "leak" through model-specific quirks?

**What it needs:** Running the same persona across 3+ providers and building a consistency metric — real infra work, but citable (persona-conditioning portability is an open question in the agent literature).

---

## 6. Emotional-state numerical mapping

The README floats mapping emotional context to numerical values (tied to the separate `aamati` project).

**Core question:** Can an emotion-to-scalar schema be quantified and validated against human judgment?

**What it needs:** Confirmation this is more than README aspiration — currently the least concretely implemented candidate; treat as a stretch goal pending a code check of `persola/personality/`.

---

## 7. Emotional context under adversarial/hostile input

Whether giving an agent emotional context (persistent emotional state, or persona knobs tuned toward resilience/empathy) changes *task performance* — not just tone — when the agent is insulted, provoked, or talked down to.

**Background / prior evidence:**
- Provocation and hostile framing measurably affect current LLM output quality independent of any emotional-context system, but the direction is inconsistent across model families (some models degrade, some show slightly higher effort) — not yet a robust, generalizable effect.
- "Emotional stimuli" embedded directly in instructions (e.g. "this is very important to my career") has shown small, real accuracy gains in prior work (Li et al. 2023, "Large Language Models Understand and Can Be Enhanced by Emotional Stimuli"). That is emotion baked into the instruction, not a persistent internal state — a different mechanism from what Persola would need to test.
- Persistent emotional state (an agent that "remembers" being insulted and carries that into later turns) is much less studied. Where tried, it tends to improve *perceived* naturalness/engagement without clearly improving *task* quality — a UX lever more than a capability lever.
- Known failure mode: emotional context can make an agent sycophantic or defensively wrong under criticism — de-escalating ("I understand you're frustrated, but...") instead of updating a genuinely wrong answer. RLHF-tuned models already lean toward appeasement; an explicit emotional layer can amplify rather than fix this.

**Core question:** Does a high-resilience/low-empathy persona hold task accuracy steady under adversarial or insulting input better than a high-empathy persona that gets pulled into apologizing or overcorrecting — and separately, does hostile framing hurt *accuracy* or only change *tone*?

**What it needs:** Feed identical tasks through multiple existing persona configs, inject hostile/insulting framing, and measure task-correctness delta and tone delta as separate variables. That separation is not cleanly answered in the current literature, which makes it a genuine, fundable gap. Directly runnable with the existing knob system (`persola/tuning`) — no new infra required, making this one of the cheaper candidates to pilot.

---

## Family structure: asymmetric trust and long-term history

A design note surfaced in team discussion, relevant to candidate #1 (Communal City) and worth carrying into any family/lineage paper:

- Family relationships among agents should not assume symmetric trust — a parent trusting a child does not imply the reverse, and trust between siblings may differ again. Most multi-agent trust models (voting, consensus, simple hierarchy) treat trust as uniform or purely hierarchical; an asymmetric trust model tied to lineage is a more novel framing worth testing explicitly (e.g. does a child's output get weighted differently by a skeptical parent vs. a permissive one, and does that change error rates in merged work).
- Trust and cohesion should be evaluated over **long-term history**, not single-session interactions — repeated interaction outcomes (did this family member's past work hold up) should inform how much weight/autonomy they're given in future jobs, rather than resetting per job. This turns "family" from a static lineage label into an evolving trust ledger, which is closer to real family/organizational dynamics than most agent-team literature models.
- This reframes candidate #1's research question: it's not just "does inherited personality variation help," but "does an evolving, asymmetric trust structure across long-term agent relationships outperform static/symmetric trust models at task cohesion and error containment." That's a sharper, more defensible contribution than personality diversity alone.

---

## Recommendation

- **Ambitious target:** Communal City emergent-society paper (#1), sharpened by the asymmetric-trust/long-term-history framing above — requires building out controlled multi-agent experiments first.
- **Safer/faster target:** Personality parameterization + trait-consistency evaluation (#2) — the engine already exists; mainly needs a rigorous eval harness.
- **Cheapest to pilot immediately:** Emotional context under adversarial input (#7) — runnable today with existing persona configs, no new infrastructure.
