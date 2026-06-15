# Epic L Retrospective — Legacy Polish (Espionage + TTS)

Date: 2026-06-15
Facilitator: Amelia (Developer) · Project Lead: Barakganon
Participants: Amelia (Developer), Alice (Product Owner), Charlie (Senior Dev), Dana (QA)

## Epic summary
| Metric | Value |
|---|---|
| Stories | 3/3 done — L-1a (espionage backend), L-1b (espionage UI), L-2 (TTS narrator). L-1 split a/b. |
| Tests | 627 → 650 (≈50 new across the epic) |
| New deps | 0 — espionage reused the Project system; TTS reused `requests` |
| Schema change | 0 — missions ride on `Project`; intel reports on `HistoryLogEntryDB` |
| Delivery | Opus plan/verify/integrate; Sonnet subagents (L-1a/L-1b on live main; L-2 drifted to a branch) |
| Verification | unit + integration + live run-the-app each story (real assassination kill, dispatch POST success, no-key 204) |
| State | merged to `main`, pushed to origin, feature branch cleaned |

## What went well
- **Design-pass-first, again.** Both features locked 4 design decisions before code, so specs were precise and the agents didn't improvise game design. The espionage design came back **schema-free** by leaning on the existing Project system.
- **Live "run it for real" caught real bugs twice.** L-1a: the **sabotage condition-scale bug** (`< 5` on a 0.0–1.0 float → every sabotage destroyed the building) — and the unit tests *encoded the same wrong scale* (one used an impossible `condition=20.0`). Caught at review + fixed; added a destroy-below-threshold test. The live smoke also confirmed assassination **actually sets `death_year`** — the thing the old diplomacy stub never did.
- **Consolidation over accretion.** L-1a replaced the shallow `DiplomacySystem` assassinate rather than adding a second one; net debt down. The dead `PersonDB.espionage_skill` now drives mission odds.
- **Graceful degradation by design.** L-2's no-key path (browser `speechSynthesis`) means narration works for everyone today; the ElevenLabs key is pure upgrade. Verified: `turn_narration.mp3` → 204 with no key, `synthesize` never hits the network without a key.

## What was painful / caught at integration
- **Branch-vs-live-main drift, recurring.** The L-2 agent created `feature/tts-narrator` despite "work on live main"; my follow-up commits landed there and the first `push origin main` was a silent no-op. Caught the divergence, merged `--no-ff`, pushed, deleted the branch. **Second epic in a row** (12-3 did the same) → now a pattern, addressed by adopting branch-then-merge as the convention.
- **Assumption-baked tests.** The sabotage tests didn't just miss the scale bug — they *asserted* it. Green tests written against a wrong assumption are worse than none. Root cause: the spec didn't state that `Building.condition` is a 0.0–1.0 float, so both code and tests guessed.

## Continuity from Epic 11/12 retros
- ✅ "Sonnet on live main (no worktree)" — held for L-1a/L-1b; ❌ L-2 drifted (now resolved as policy).
- ✅ "Verify on real data beyond green tests" — caught sabotage + assassination behavior.
- ✅ "No blanket suppression / no schema churn" — clean (0 new deps, 0 migrations).

## Decisions (Project Lead)
1. **Branch policy:** accept **branch-then-merge** — prompts expect a feature branch; the integrator always reconciles to `main`.
2. **Test integrity:** **specs must assert domain invariants** (units/ranges/enum values/scales) so code and tests are written against documented truth.

## Action items
| # | Action | Owner | Category |
|---|--------|-------|----------|
| 1 | Adopt branch-then-merge for subagents: integrator `git fetch` + checks branch, `--no-ff` merge to main, push, delete branch (local+remote). Closes Epic-12 action #3. | Barakganon + Amelia | Process |
| 2 | Specs must state domain invariants — real units/ranges/enum values/scales (e.g. "Building.condition is a 0.0–1.0 float") — so code AND tests target documented truth. | Amelia | Process |
| 3 | Integrator merge-state check every story: after a subagent reports, `git fetch` + confirm work is on main (or reconcile the branch) + confirm `main == origin/main` before declaring done. | Amelia | Process |

## Next epic
No epic L+1 defined. **The master plan (Epics 1–12 + Epic L) is complete.** No significant-discovery alert.

## Readiness assessment
- Tests/quality: 650 green; espionage + TTS live-verified (incl. no-key path). ✅
- Stability: app boots 8091, single Alembic head, routes 200. ✅
- Release: pushed to origin; feature branch cleaned; `main == origin/main`. ✅
- Carried-forward: optional STATUS.md body reconciliation (flagged intentional, left to Project Lead); optional Epic L-1 retro folded into this one. No blockers.
