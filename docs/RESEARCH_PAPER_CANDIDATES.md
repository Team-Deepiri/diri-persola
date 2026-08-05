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

## Recommendation

- **Ambitious target:** Communal City emergent-society paper (#1) — requires building out controlled multi-agent experiments first.
- **Safer/faster target:** Personality parameterization + trait-consistency evaluation (#2) — the engine already exists; mainly needs a rigorous eval harness.
