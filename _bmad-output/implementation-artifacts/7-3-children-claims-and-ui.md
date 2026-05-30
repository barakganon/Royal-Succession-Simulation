# Story 7-3: Children-with-Claims + Foreign-Court Marriage UI

Status: ready-for-dev

## Story

A child born of a cross-dynasty union should carry a **claim** on the parent-house it did NOT inherit (it takes the mother's dynasty, so it holds a claim on the father's dynasty) — the seed of future inheritance/casus-belli mechanics. AND the player should get a **new UI surface** — a "Foreign Court" panel on the world map listing marriageable nobles of other dynasties — where they can right-click a foreign character and **propose marriage to one of their own children**, with the target AI house deciding accept/reject (reusing the Story 7-2 gate) and an accepted union linking the couple, bumping relations, and writing a wedding chronicle.

## Acceptance Criteria

1. **AC1 — `ClaimDB` model (`models/db_models.py`).** New table `claim` mirroring the `MarriageOfferDB` pattern (db_models.py:1165). Columns: `id` PK; `claimant_sim_id` FK→`person_db.id` (`use_alter=True, name='fk_claim_claimant'`, nullable=False, index); `target_dynasty_id` FK→`dynasty.id` (nullable=False, index) — **the dynasty being claimed**; `source_dynasty_id` FK→`dynasty.id` (nullable=True, index) — the claimant's own dynasty; `claim_type` String(30) default `'cross_dynasty_birth'`; `strength` Integer default 0; `created_year` Integer nullable; `is_active` Boolean default True; `created_at` DateTime default `datetime.datetime.utcnow`. Relationships (no backrefs): `claimant` → PersonDB `foreign_keys=[claimant_sim_id]`; `target_dynasty` / `source_dynasty` → DynastyDB with explicit `foreign_keys`. `__repr__`. Table auto-creates via `db.create_all()` (db_initialization.py) — no manual migration needed for a brand-new table.

2. **AC2 — Register a claim on cross-dynasty birth (`models/turn_processor.py`, `process_childbirth_check`, ~line 707-773).** After the child is created/flushed and **only if the child survived** (`child.death_year is None`) AND the union is cross-dynasty (`spouse.dynasty_id != woman.dynasty_id`; recall `woman.dynasty_id == dynasty.id` and the child takes `dynasty.id`), insert `ClaimDB(claimant_sim_id=child.id, target_dynasty_id=spouse.dynasty_id, source_dynasty_id=woman.dynasty_id, claim_type='cross_dynasty_birth', created_year=current_year)` and add to the session. The child takes the **mother's** dynasty; the claim is on the **father's** dynasty (`spouse.dynasty_id`). Wrap defensively — a claim-insert failure must never abort the birth. Same-dynasty births register NO claim.

3. **AC3 — `MarriageSystem` business logic (NEW `models/marriage_system.py`).** Class `MarriageSystem` whose constructor takes `session: Session` as its only arg (project rule). Methods:
   - `list_foreign_marriageable(self, dynasty_id: int, year: int | None = None) -> list[dict]` — every PersonDB that is alive (`death_year is None`), noble, unmarried (`spouse_sim_id is None`), age 16-55, and in a dynasty **other than** `dynasty_id`. If `year` is None, derive the current year from the *requesting* dynasty's `current_simulation_year`. Each dict: `{id, name, surname, gender, age, dynasty_id, dynasty_name, traits (list[str]), is_ai (bool)}`.
   - `eligible_children(self, dynasty_id: int, target_gender: str) -> list[dict]` — the requesting dynasty's OWN nobles that are alive, unmarried, age ≥ 16, and of the gender **opposite** `target_gender` (so they can wed a foreign character of `target_gender`). Each dict: `{id, name, surname, gender, age}`.
   - `propose_marriage(self, proposer_person_id: int, target_person_id: int, year: int) -> dict` — `proposer_person_id` is the player's own child; `target_person_id` is the foreign noble. Validate both exist, alive, unmarried, **opposite gender**, and in **different** dynasties (else `{'ok': False, 'accepted': False, 'message': <reason>, 'offer_id': None}`). Create a `MarriageOfferDB(proposer_dynasty_id=<proposer's dynasty>, target_dynasty_id=<target's dynasty>, proposer_person_id, target_person_id, status='pending', created_year=year)`. Decide acceptance: if the **target's** dynasty `is_ai_controlled`, build `AIController(session, target_dynasty_id, <target dynasty ai_personality or ''>)` and call `decide_marriage_response(context)` with `context = {'proposer_dynasty_id': <proposer dynasty id>, 'relation_score': <relation between the two dynasties>, 'proposer_prestige': <proposer dynasty prestige>, 'own_prestige': <target dynasty prestige>}`; if target is **not** AI (human) → auto-accept (mirror 7-2). On **accept**: set both `spouse_sim_id`, bump the diplomatic relation **+30** (`DiplomacySystem(session).get_diplomatic_relation(a, b)` then `.update_relation('marriage_alliance', 30)`), append a **wedding** `HistoryLogEntryDB` (event_type `marriage`) via `build_wedding_chronicle_prompt(...)` when `_llm_available()` (guarded inline `genai`, ≤150 tok, error→fallback) else `generate_wedding_fallback(...)` (Story 7-2 helpers in `utils/llm_prompts.py`), set `offer.status='accepted'`, return `{'ok': True, 'accepted': True, 'message': <wedding line>, 'offer_id': offer.id}`. On **reject**: `offer.status='rejected'`, return `{'ok': True, 'accepted': False, 'message': <polite rejection>, 'offer_id': offer.id}`. Never raises; rollback + `{'ok': False, ...}` on error. Lazy-import `AIController` / `DiplomacySystem` / the prompt helpers inside the method to avoid import cycles.

4. **AC4 — Routes (`blueprints/diplomacy.py`).** All `@login_required`; verify the dynasty belongs to `current_user` (else 403). Delegate to `MarriageSystem` (lazy import inside the route). Pass serialized dicts to templates/JSON — never raw ORM.
   - `GET /game/<int:dynasty_id>/foreign_characters.json` → fn `foreign_characters_json` → `jsonify({'characters': MarriageSystem(db.session).list_foreign_marriageable(dynasty_id)})`.
   - `GET /game/<int:dynasty_id>/eligible_children.json?target_gender=MALE|FEMALE` → fn `eligible_children_json` → `jsonify({'children': MarriageSystem(db.session).eligible_children(dynasty_id, request.args.get('target_gender', 'MALE'))})`.
   - `POST /game/<int:dynasty_id>/propose_marriage` → fn `propose_marriage` → reads `proposer_person_id` + `target_person_id` (form or JSON), resolves the year from the dynasty's `current_simulation_year`, returns `jsonify(MarriageSystem(db.session).propose_marriage(...))`. DB writes wrapped in try/except + rollback (the system already guards, but the route stays defensive).

5. **AC5 — Foreign-Court UI (`templates/world_map.html`).** A button **`id="open-foreign-court"`** (label e.g. "Foreign Court" / "Royal Matches") in the existing left rail / map controls opens a panel **`id="foreign-court-panel"`** that `fetch`es `foreign_characters.json` and lists each foreign noble (name, house, age, gender, traits) as a row carrying `data-char-id` and `data-char-gender`. Right-clicking a row (reuse the existing `game-context-menu` pattern from Story 3-2/4-2, or a per-row "Propose Marriage" button) `fetch`es `eligible_children.json?target_gender=<row gender>` and presents the player's eligible children; choosing one POSTs to `propose_marriage` (CSRF disabled in tests; in app use the existing fetch/JSON convention already used by the map actions) and shows the returned `message` as a toast/flash-style notice. Use `url_for('diplomacy.<fn>', dynasty_id=...)` — never hardcode URLs. Extends `base.html` patterns already in the file. Keep it consistent with the medieval theme + existing panel styling.

6. **AC6 — Tests (NEW files only) — ≥8 new tests.**
   - `tests/integration/test_claims.py`:
     - A cross-dynasty birth registers exactly one `ClaimDB` with `target_dynasty_id == father's dynasty`, `source_dynasty_id == mother's dynasty`, `claimant_sim_id == child.id`, `claim_type=='cross_dynasty_birth'`. (Drive `process_childbirth_check` directly with a married cross-dynasty couple; patch infant mortality / RNG so the child survives — see the RNG note below.)
     - A **same-dynasty** birth registers **no** claim.
     - An infant that dies at birth registers **no** claim.
   - `tests/integration/test_propose_marriage.py`:
     - `MarriageSystem.list_foreign_marriageable` returns only other-dynasty, alive, unmarried, age-16-55 nobles (excludes own dynasty, married, dead, out-of-range).
     - `eligible_children(target_gender='MALE')` returns only the requester's own unmarried FEMALE nobles ≥16 (and vice-versa).
     - `propose_marriage` to a **neutral AI** dynasty → `accepted True`, both `spouse_sim_id` linked, the inter-dynasty relation increased by 30, a `marriage` chronicle entry exists, offer.status `accepted`.
     - `propose_marriage` to a **hostile AI** dynasty (relation < -20) → `accepted False`, neither linked, offer.status `rejected`, no +30 bump.
     - `propose_marriage` validation: same-dynasty or same-gender or already-married target → `{'ok': False}`.
     - Route smoke: `GET .../foreign_characters.json` 200 + `'characters'` key; `POST .../propose_marriage` returns JSON with `accepted`. (Use the integration `client` + login pattern from `test_ai_marriage.py`.)

7. **AC7 — No regressions.** Full suite green vs baseline **415 passed** (the flake is fixed; new tests additive). Single-dynasty setups unchanged. 7-1/7-2 turn-based matching untouched.

## Tasks / Subtasks
- [ ] Task 1 — `ClaimDB` + claim-on-birth + `MarriageSystem`. [Agent A]
- [ ] Task 2 — Routes in `blueprints/diplomacy.py`. [Agent B]
- [ ] Task 3 — Foreign-Court UI in `templates/world_map.html`. [Agent C]
- [ ] Task 4 — Tests (new files). [Agent D]

## Dev Notes

### Multi-agent split (4 worktree agents + integrator) — ZERO file overlap
- **Agent A** — `models/db_models.py` (`ClaimDB`) + `models/turn_processor.py` (claim on cross-dynasty birth, in `process_childbirth_check`) + NEW `models/marriage_system.py` (`MarriageSystem`).
- **Agent B** — `blueprints/diplomacy.py` ONLY (3 routes delegating to `MarriageSystem`; lazy-import it — A's module is absent in B's worktree, so a lazy import keeps B importable, mirroring prior stories).
- **Agent C** — `templates/world_map.html` ONLY (Foreign-Court panel + right-click propose-marriage flow + fetch/POST JS).
- **Agent D** — NEW `tests/integration/test_claims.py` + `tests/integration/test_propose_marriage.py` ONLY.
- No shared files. Each agent gets the full FROZEN CONTRACT inlined.

### FROZEN INTERFACE CONTRACT (authoritative — prevents the recurring signature drift)
- **`ClaimDB`** table `claim`, columns exactly as AC1; `claimant`/`target_dynasty`/`source_dynasty` relationships with explicit `foreign_keys`.
- **Claim direction:** child takes mother's dynasty; `ClaimDB.target_dynasty_id = father's dynasty (spouse.dynasty_id)`, `source_dynasty_id = mother's dynasty (woman.dynasty_id)`, `claimant_sim_id = child.id`. Only when `child.death_year is None` and cross-dynasty.
- **`MarriageSystem(session)`** — constructor takes session only.
  - `list_foreign_marriageable(dynasty_id, year=None) -> list[dict]` keys: `id, name, surname, gender, age, dynasty_id, dynasty_name, traits, is_ai`.
  - `eligible_children(dynasty_id, target_gender) -> list[dict]` keys: `id, name, surname, gender, age` (returns the OPPOSITE gender to `target_gender`).
  - `propose_marriage(proposer_person_id, target_person_id, year) -> dict` keys: `ok, accepted, message, offer_id`. Proposer = player child; target = foreign noble. AI target → `decide_marriage_response`; non-AI → auto-accept. Accept → link both `spouse_sim_id` + relation **+30** + `marriage` wedding chronicle. Reject → `offer.status='rejected'`.
- **`AIController.decide_marriage_response(context: dict) -> bool`** (7-2, frozen): context keys `proposer_dynasty_id, relation_score, proposer_prestige, own_prestige`. Reject if `relation_score < -20`.
- **`build_wedding_chronicle_prompt(spouse1_name, spouse1_traits, spouse2_name, spouse2_traits, house1, house2, year)`** + **`generate_wedding_fallback(spouse1_name, spouse2_name, house1, house2, year)`** (7-2, frozen — call args in THIS order).
- **Routes / endpoints (url_for names):** `diplomacy.foreign_characters_json` (GET `/game/<dynasty_id>/foreign_characters.json`), `diplomacy.eligible_children_json` (GET `/game/<dynasty_id>/eligible_children.json`), `diplomacy.propose_marriage` (POST `/game/<dynasty_id>/propose_marriage`). JSON shapes: `{'characters': [...]}`, `{'children': [...]}`, the propose dict.
- **DOM hooks (frozen so D/C agree):** open button `id="open-foreign-court"`, panel container `id="foreign-court-panel"`, foreign rows carry `data-char-id` + `data-char-gender`.

### Reuse / project rules
- `MarriageOfferDB` (table `marriage_offer`, db_models.py:1165) already exists — reuse, don't redefine. `DynastyDB.is_ai_controlled` / `ai_personality` / `prestige` / `current_simulation_year`. Relations via `DiplomacySystem.get_diplomatic_relation` + `DiplomaticRelation.update_relation` (clamps ±100). `_llm_available()` guard + ≤150-tok chronicle; prompt strings only in `utils/llm_prompts.py`. `logger = logging.getLogger('royal_succession.marriage_system')`. DB writes in try/except + rollback. `@login_required` + ownership 403 on routes. Lazy imports in B and in `MarriageSystem` to dodge cycles.
- **RNG / determinism in tests (IMPORTANT — see latest test-isolation fix):** turn lifecycle consumes the global `random`; a function-scoped autouse `_deterministic_random` fixture now re-seeds before every test. For claim tests, drive `process_childbirth_check` directly and `patch('models.turn_processor.process_marriage_check', return_value=False)` is not needed (you call childbirth directly), but DO control infant mortality — either `mocker.patch('models.turn_processor.random.random', return_value=0.99)` (survives the 15% check) or assert on the surviving-child path. Do NOT rely on incidental RNG.

### Out of scope / deferred
- Inheritance resolution / casus-belli from claims, claim strength growth, pressing claims via war → later epic. 7-3 only **registers** the claim + ships the proposal UI. Full alliance-treaty creation beyond the +30 bump → later. Portraits in the foreign-court list are optional polish (PersonDB has `portrait_svg` if C wants it).

## Previous Story Intelligence
- Worktree contract-first via the **Workflow tool**. Agents default to plan mode → each prompt MUST say "EXECUTE NOW — do not enter plan mode / EnterPlanMode, pre-approved." Worktrees branch off `main`; the story file is absent in their trees → the FULL contract is inlined per prompt.
- **Integrator caution (recurring):** agents leak edits into the MAIN working tree — verify `git status` before each merge; if a merge fails on a dirty tree, discard the leaked copies and merge the branch. **Helper-signature drift** between the impl agent and the tests agent bit 7-1 and 7-2 twice — the FROZEN CONTRACT signatures above are authoritative; integrator reconciles any drift to them.
- Baseline **415 passed** (flake eliminated 2026-05-30: autouse RNG seed + heir-majority test patches marriage/childbirth). UI story → **run-the-app visual check required** at integration (Epic 3 retro lesson): dev server `python main_flask_app.py` (set `MPLBACKEND=Agg` to avoid the macOS NSWindow crash), load `/world/map`, open the Foreign Court panel, confirm it lists foreign characters and a propose-marriage attempt shows a result.

## References
- Claim-model template: `models/db_models.py:1165` (`MarriageOfferDB`). Table auto-create: `models/db_initialization.py:119`.
- Childbirth insert point: `models/turn_processor.py:707-773` (`process_childbirth_check`; child `dynasty_id=dynasty.id` @709, `father_sim_id=spouse.id` @715, flush @746, `return True` @773).
- AI gate: `models/ai_controller.py:225-281` (`decide_marriage_response`).
- Wedding prompt/fallback: `utils/llm_prompts.py` (7-2 `build_wedding_chronicle_prompt` / `generate_wedding_fallback`).
- Relations: `models/diplomacy_system.py:68` (`get_diplomatic_relation`), `models/db_models.py:882` (`update_relation`).
- Route pattern: `blueprints/diplomacy.py:158-188` (`diplomatic_action`). Map context-menu pattern: `templates/world_map.html` (`game-context-menu`, Story 3-2/4-2).
- Test fixtures: `tests/integration/test_cross_dynasty_marriage.py` (`_create_user_and_dynasty`, `_add_person`), `tests/integration/test_ai_marriage.py` (`_set_relation`, client/login).

## Dev Agent Record
### Agent Model Used
claude-opus-4-8[1m] — 4 worktree sub-agents via the Workflow tool + main-session integrator.

### Completion Notes List
- _pending_

### File List
- `models/db_models.py` — MODIFIED (`ClaimDB`)
- `models/turn_processor.py` — MODIFIED (claim on cross-dynasty birth)
- `models/marriage_system.py` — NEW (`MarriageSystem`)
- `blueprints/diplomacy.py` — MODIFIED (3 routes)
- `templates/world_map.html` — MODIFIED (Foreign-Court panel + propose-marriage flow)
- `tests/integration/test_claims.py` — NEW
- `tests/integration/test_propose_marriage.py` — NEW
- `_bmad-output/implementation-artifacts/{7-3-...md, sprint-status.yaml}`, `STATUS.md` — MODIFIED

### Change Log
| Date | Change |
|---|---|
| 2026-05-30 | spec(7-3); ready-for-dev; 4 worktree agents via Workflow |
