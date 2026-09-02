# Persola — Persona Fine-Tuning Initiation Plan

**Date**: 2026-09-02
**Status**: READY TO EXECUTE
**Owner**: Deepiri ML Engineering (Persola / personalization)

---

## Goal

Persola is the **agentic personality framework** — it turns 40 tunable knobs into behavioral system prompts + inference sampling params. Today a persona is expressed **entirely at the prompt/parameter layer**; the underlying model is never modified. This plan adds **persona fine-tuning** so a persona becomes **natively embodied in model weights** via LoRA/QLoRA, powered by the data Persola already extracts from writing samples and conversations, and trained through the **Helox** factory.

Two modes to support:
1. **Prompt-layer persona (today)**: knobs → system prompt + sampling params. No training.
2. **Weight-layer persona (this plan)**: per-persona LoRA adapter trained on persona-annotated dialogue, hot-loaded by Cyrex `DynamicLoRAService`.

---

## Current State

| Area | Status |
|------|--------|
| `PersonaProfile` model, 40 knobs, presets | Complete |
| `PersonaEngine` (knobs → system prompt + sampling) | Complete |
| `SamplingEngine` (knobs → temperature/top_p/top_k) | Complete |
| `PersolaLLM` (Ollama/OpenAI/Anthropic adapters) | Complete |
| Writing-sample analysis (`persola/analysis/`) — extracts trait vector from text | Implemented |
| `CyrexClient` bridge (`persola/integrations/cyrex.py`) | Implemented |
| PostgreSQL persistence + Alembic (`persola/db/`) | Implemented on `main` |
| Orchestration/Communal City (`persola/orchestration/`) | Implemented |
| FastAPI + React UI | Implemented |
| **Any model weight training / LoRA / adapter generation** | **NOT PRESENT** |
| **Persona dataset → Helox training emit** | **NOT PRESENT** |
| **Per-persona adapter hot-reload path** | **NOT PRESENT** |

### The gap

Persola generates *instructions* (system prompts) but produces **no training data** and **no adapter weights**. "Fine-tuning Persola" therefore means building a bridge: persona trait vectors + dialogue → chat/instruct dataset → Helox LoRA fine-tune → per-persona adapter → Cyrex runtime hot-load.

---

## Execution Plan

### Phase 1 — Build Persona Chat Datasets

**Goal**: turn persona definitions and real LLM conversations into fine-tuning data.

- [ ] **1.1** **Synthetic persona dialogue generator**: for each `PersonaProfile`, generate chat-style (instruction/response) examples using `PersolaLLM` seeded with the persona system prompt + sampling params. Save as JSONL with persona id/tag.
- [ ] **1.2** **Curate real conversations**: instrument agent sessions (via Cyrex) tagged by persona id and knob vector into a `persona_turns` store in Postgres.
- [ ] **1.3** **Augment from analysis**: for uploaded writing samples (Phase-3 analysis), pair the extracted trait vector with the text as a grounding example.
- [ ] **1.4** Produce a **dataset manifest** per persona: `{instruction, input, output, persona=tag, knobs=vector}` — the same contract Helox expects.
- [ ] **1.5** Version + validate the dataset (dedup, balance across personas, min size per persona) via `deepiri-dataset-processor`.

### Phase 2 — Emit Datasets to Helox

**Goal**: Get persona datasets into the training factory.

- [ ] **2.1** Add a `HeloxJobClient`-style submit path (mirroring `diri-cyrex` pattern) that queues a persona LoRA training job on the `training-jobs` stream.
- [ ] **2.2** Emit the persona dataset to `pipeline.helox-training.structured` (or direct job payload) with persona provenance.
- [ ] **2.3** Define the LoRA hyperparams per persona (rank, alpha, target modules) captured in the job request.

### Phase 3 — Persona LoRA Fine-Tuning (via Helox)

**Goal**: train per-persona adapter weights.

- [ ] **3.1** Hand the persona dataset + base model tag to Helox's LoRA/QLoRA trainer (`mlops/infrastructure/lora_training.py` in diri-helox).
- [ ] **3.2** Train one adapter per flagship persona (start with 3–5: Friendly, Analytical, Professional).
- [ ] **3.3** Evaluate each adapter on persona-consistency metrics (does it hold the target trait vs base model) using the post-training eval harness.
- [ ] **3.4** Register adapters in the model registry and publish `model-ready` events per persona.

### Phase 4 — Hot-Load Adapters into Runtime

**Goal**: serve the weight-tuned persona at inference.

- [ ] **4.1** Extend `CyrexClient` / a `ModelReloadListener` consumer to download + mount per-persona LoRA adapters.
- [ ] **4.2** Hook into Cyrex `DynamicLoRAService` so selecting a Persola persona loads the matching adapter instead of only applying a system prompt.
- [ ] **4.3** Add a fallback: if no adapter exists for a persona, use the prompt-layer path (current behavior).

### Phase 5 — Persona/Model A-B Evaluation

**Goal**: prove weight-layer personas are more consistent than prompt-layer.

- [ ] **5.1** Build a persona-consistency eval set (trait-relevant prompts scored against the target trait).
- [ ] **5.2** Compare: base + prompt vs base + prompt + LoRA (same persona).
- [ ] **5.3** Score on formality/humor/empathy/verbosity adherence; A-B report per persona.
- [ ] **5.4** Track all experiments in MLflow (knob vector → adapter → metric delta).

### Phase 6 — Foundational Hardening (parallel)

From `IMPLEMENTATION_PLAN.md` remaining phases — required discipline gates:

- [ ] **6.1** Authentication + rate limiting before internet exposure (Phase 6).
- [ ] **6.2** Observability + test suite (Phase 7): CI runs on these features.
- [ ] **6.3** Persistence verification: persona turns + datasets survive restart (already on DB; add tests).

---

## Key Commands (target)

```bash
# 1. Generate a persona chat dataset
persola persona dataset --name "Friendly Assistant" --dialogues 200 --out data/personas/friendly.jsonl

# 2. Curate real persona turns
persola dataset collect --persona "Friendly Assistant" --out data/personas/friendly-turns.jsonl

# 3. Validate + version dataset
poetry run python scripts/dataset_versioning_cli.py create --name friendly --version 1.0.0

# 4. Submit persona LoRA job to Helox
persola trainer submit-lora --persona "Friendly Assistant" --base <model-tag> --dataset data/personas/friendly.jsonl

# 5. A-B evaluate persona consistency
persola eval a-b --persona "Friendly Assistant" --adapter <adapter-tag> --base <model-tag>
```

---

## Data Flow (Persola ↔ Helox ↔ Cyrex)

```
persona knobs + LLM     writing samples
    │                        │
    ▼                        ▼
persona dialogue dataset ── persona trait vector
    │
    ▼
data manifest (instruction/input/output + persona label)
    │
    ▼
Helox LoRA/QLoRA fine-tune ─▶ per-persona adapter ─▶ model registry
    │
    ▼
model-ready event ─▶ Cyrex DynamicLoRAService hot-load ─▶ inference
    │
    A-B eval (persona consistency) ─▶ iterate
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Persona data too small | Synthetic dialogue generator (Phase 1.1) + real-turn curation (1.2) |
| Adapter overfits/trivial | Eval on persona-consistency set, balance personas, min-per-persona size |
| No adapter for a persona | Prompt-layer fallback (Phase 4.3) keeps current behavior |
| Relying on prompt-only weakens brand | A-B eval (Phase 5) proves the weight-layer benefit before rollout |
| Data drift across personas | Version datasets per persona; MLflow tracks config → metric |
| Runtime hot-load complexity | Start with 3–5 flagship personas; reuse `DynamicLoRAService` |

---

## Success Criteria

1. Per-persona chat datasets generated + versioned (≥3 flagship personas).
2. Persona datasets flow to Helox; LoRA adapters trained and registered.
3. Per-persona adapters hot-load into Cyrex runtime.
4. A-B eval shows weight-layer personas hold target traits better than prompt-layer (with a measured metric).
5. Auth, observability, and tests are green.

---

## Dependencies

- Helox training factory + LoRA trainer + model registry (diri-helox PR #128).
- Cyrex runtime + `DynamicLoRAService` + `model-ready` events (diri-cyrex PR #181).
- `PersolaLLM` providers (Ollama/OpenAI/Anthropic) for synthetic data generation.
- `deepiri-dataset-processor` for dataset validation/versioning.
