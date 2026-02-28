# Gemini 3.0 Real-Time Personalized Mantra + AI Kirtan

Version: 0.1 (deep scope draft)
Context: Scoped using Chapter 2 (AIPDL), Chapter 3 (trade-offs), and Chapter 6 (metric blend/OKRs) from *Building AI-Powered Products*.

## 1) Product Vision
Build a real-time, adaptive spiritual music companion that helps users:
- Learn and retain mantras with correct pronunciation, rhythm, and intent.
- Enter and sustain devotional flow during solo or group kirtan.
- Receive music/session adaptation based on listener input, biometric signals, and environment context.

Core principle: AI is not the product; the experience is the product.

## 2) Problem Framing
### User problems
- Many learners do not know whether they are chanting correctly.
- Existing mantra apps are static and not context-aware (energy, time of day, stress, setting).
- Kirtan practice often needs a responsive accompanist, especially for solo practitioners.
- People struggle with consistency and progression in long-term mantra practice.

### Why now
- Real-time multimodal models can combine text, audio, and structured signals.
- Wearables and phone sensors can provide lightweight context.
- Personalized coaching and adaptive music can increase retention and consistency.

## 3) Product Type (AIPDL Lens)
This is primarily a `0-to-1` AI product:
- Novel combined experience (learning + devotional + adaptive accompaniment).
- Product-market fit is unknown and must be validated through rapid experiments.
- Strong emphasis on opportunity validation and risk management before scale.

It can evolve into `1-to-n` through integrations (music platforms, studio tools, temple/community features).

## 4) Target Segments
### Primary segment (MVP focus)
- Spiritual seekers and practitioners (18-45) practicing alone at home 3-5 times per week.
- Needs: guidance, confidence, consistency, emotional grounding.

### Secondary segment
- Kirtan facilitators and small community groups.
- Needs: dynamic backing, call-and-response support, session planning.

### Excluded in MVP
- Clinical therapeutic claims.
- Full music streaming replacement.
- Enterprise/temple administration workflows.

## 5) JTBD (Jobs To Be Done)
- "When I practice alone, help me chant correctly and stay in flow without breaking concentration."
- "When my energy changes, adapt tempo/instrumentation/guidance in real time."
- "When I lead or join kirtan, provide accompaniment that responds to voice, rhythm, and group state."
- "After each session, show progress and next best practice."

## 6) Experience Pillars
### Pillar A: Mantra Learning Coach
- Pronunciation coaching (phoneme-level or syllable-level feedback).
- Rhythm and pace coaching with incremental difficulty.
- Meaning/context prompts to deepen retention and intent.
- Spaced repetition practice plans.

### Pillar B: AI-Assisted Kirtan
- Real-time responsive drone/percussion/harmonic bed.
- Call-and-response generation options (leader/follower mode).
- Adaptive arrangement based on participant energy.

### Pillar C: Context-Aware Personalization
- Input channels: explicit user input, biometric state, environmental context.
- Session adaptation: tempo, key, guidance intensity, silence intervals, mantra selection.

## 7) Input Model
### Explicit listener input
- Mood ("grounded", "anxious", "joyful"), intention, tradition preference, session length.
- Immediate controls: "more energetic", "slower", "repeat line", "explain meaning".

### Biometric (optional, consented)
- Heart rate, HRV, stress proxy, breath cadence (if wearable supports).
- Confidence tagging: high-confidence vs low-confidence sensor windows.

### Environmental context
- Noise level, time of day, location class (home/outdoor/commute), device mode.

### Principle
- Never require biometric data for core utility.
- Biometric and environment are augmenters, not blockers.

## 8) Functional Scope (MVP vs Later)
### MVP (Phase 1 launch candidate)
- Single-user mantra coach with 20-40 curated mantras.
- Real-time voice feedback loop (basic pronunciation + pacing).
- Context-aware session adaptation using explicit input + optional wearable HR.
- AI-kirtan accompaniment in 2-3 styles with tempo/key adaptation.
- Session recap (what improved, what to practice next).

### Phase 2
- Group mode (2-10 users), shared tempo alignment, leader handoff.
- Better improvisation support and richer arrangement control.
- Community playlists and practice circles.

### Phase 3
- Creator tools, API ecosystem, advanced tradition packs, multilingual voice pedagogy.

## 9) System Architecture (Logical)
### Client layer
- Mobile app (iOS/Android) + optional desktop web.
- Audio capture, playback, sensor permissions, live controls.

### Real-time orchestration layer
- Session state machine (warm-up, learn, flow, cooldown, reflection).
- Context fusion service (explicit + biometric + environment).
- Policy engine (guardrails + personalization bounds).

### AI layer
- Gemini 3.0 orchestration for:
- Intent extraction and dialogue.
- Session planning and adaptation logic.
- Lyric/mantra explanation and reflective prompts.
- Structured decision outputs (tempo target, guidance intensity, transitions).

### Music/audio intelligence
- Beat/tempo tracker from live vocal input.
- Pitch/key tracker.
- Backing generator/player (drone/percussion/harmonic stems or generated loops).

### Data + feedback layer
- Event logging, session outcomes, model eval traces.
- Consent and privacy store.
- Experiment flags (A/B and staged rollouts).

## 10) Learning Design Scope (Instructional Layer)
Use a structured teaching loop so mantra learning quality is measurable.

### Learning objectives
- Correctly pronounce target mantra at >= defined threshold.
- Sustain cadence for target duration without drift.
- Explain core meaning/intention in own words.
- Transfer: perform in a live or near-live kirtan setting.

### Suggested progression
- Level 1: listen + repeat.
- Level 2: paced call-response.
- Level 3: memory-only chanting with corrective feedback.
- Level 4: improvisational devotional flow with minimal prompts.

### Assessment signals
- Pronunciation score trend.
- Rhythm stability trend.
- Prompt-dependence decay (fewer interventions needed).
- Retention after 24h/7d spaced recall.

## 11) Data Strategy and Privacy
### Data classes
- P0: Account and consent metadata.
- P1: Session controls and usage telemetry.
- P2: Audio features (avoid storing raw audio by default).
- P3: Biometric signals (strict opt-in, granular toggles).

### Privacy defaults
- Privacy-first onboarding with explicit consent tiers.
- Raw biometric storage off by default.
- Local/on-device preprocessing where possible.
- User-visible "why this adaptation happened" explanation panel.

### Compliance and risk posture
- Clear sensitive data policy and deletion controls.
- No diagnostic/medical claims from biometric interpretation.
- Bias checks across voice accents, gender, age bands, and chant styles.

## 12) Trade Space (Chapter 3 Style)
### Key trade-offs to decide early
- Personalization depth vs privacy sensitivity.
- Real-time latency vs recommendation/feedback accuracy.
- Explainability vs model complexity.
- Build vs buy for accompaniment generation stack.
- On-device inference vs cloud orchestration cost.

### Decision framing
- Rank constraints: user trust and safety first, then experience quality, then growth speed.
- Keep one-page decision logs with options, risks, and chosen rationale.

## 13) Metrics and OKRs (Chapter 6 Style)
### North Star (MVP)
- Weekly "meaningful devotional sessions" per active user.
Definition: session >= 10 min + completion of intended practice goal + user-rated value >= 4/5.

### Product health metrics
- Week-4 retention.
- Session completion rate.
- Average weekly minutes in guided practice.
- "I felt in flow" self-report rate.

### System health metrics
- Real-time loop latency (target p95 < 250ms end-to-end for feedback events).
- Uptime (>= 99% for live session services).
- Error rate per session.

### AI proxy metrics
- Pronunciation feedback precision/recall against labeled validation set.
- Context-adaptation acceptance rate ("this adaptation helped": yes/no).
- Recommendation relevance score for mantra/arrangement selection.

### Guardrail metrics
- User-reported discomfort/confusion rate.
- False spiritual certainty signals (model overconfident guidance).
- Privacy control opt-out friction.

## 14) Experiment Plan (Opportunity + Testing Stages)
### Experiment 1: Value validation
- Compare static practice flow vs adaptive flow.
- Success: +20% session completion and +15% week-2 return rate.

### Experiment 2: Biometric augmentation value
- Compare explicit-only personalization vs explicit+biometric.
- Success: measurable improvement in flow score with no trust drop.

### Experiment 3: AI-assisted kirtan usefulness
- Solo accompanist mode vs no accompanist baseline.
- Success: +25% average practice duration and improved qualitative delight.

## 15) Phase Roadmap (High Confidence)
### Phase 0 (2-4 weeks): Discovery + feasibility
- 20-30 target-user interviews.
- Concierged prototype sessions (human-in-loop).
- Baseline privacy and risk requirements.

### Phase 1 (6-10 weeks): MVP build
- Real-time session engine, mantra coach basics, limited accompaniment styles.
- Consent system + telemetry + experiment framework.
- Internal alpha with clear no-go thresholds.

### Phase 2 (4-8 weeks): Beta + optimization
- Controlled beta cohort (100-300 users).
- Improve latency and adaptation quality.
- Tune onboarding and learning progression.

### Phase 3: Go-to-market readiness
- Broader rollout, creator/teacher partnerships, channel strategy.
- Ongoing model evaluation and bias audits.

## 16) Go/No-Go Gates
### Gate A: User desirability
- >= 40% users say they would be "very disappointed" if removed (or equivalent strong retention signal).

### Gate B: Technical feasibility
- Real-time feedback p95 latency within target under expected concurrency.
- Stable session success rate in production-like conditions.

### Gate C: Business viability
- Early evidence of repeat usage + acceptable cost per meaningful session.
- No unresolved high-severity privacy/ethics blockers.

## 17) Team Shape (Lean MVP)
- Product lead (you).
- AI/ML engineer (real-time personalization + evals).
- Audio DSP engineer (tempo/pitch/accompaniment pipeline).
- Full-stack/mobile engineer.
- Designer (interaction + devotional UX sensitivity).
- Part-time domain advisor (mantra/kirtan practitioner-teacher).
- Part-time trust/privacy advisor.

## 18) Open Decisions to Resolve Next
- Which traditions/mantra sets are in-scope for MVP?
- What wearable integrations are mandatory vs optional at launch?
- Build vs buy for accompaniment generation engine?
- Is first launch solo-only, or solo + small-group beta?
- What monetization hypothesis to test first (subscription, premium packs, teacher-led cohorts)?

## 19) Immediate Next Actions (Next 10 Days)
1. Write PRD v0 with one primary persona and one core user journey.
2. Define data consent matrix and privacy copy before prototyping.
3. Build a "Wizard of Oz" prototype for 5 live guided sessions.
4. Finalize MVP metric dashboard schema (North Star + guardrails).
5. Decide first 20 mantra corpus with domain expert review.
