# Story 10B: Banking / Loans Subsystem

**Status:** in-progress
**Branch:** feature/banking-system
**Sprint:** 10

## Story

As a player, I want to borrow gold from moneylenders and repay loans with interest, so I can fund armies and buildings when my treasury runs dry, while managing the risk of debt default.

## Acceptance Criteria

- [ ] AC1: Player can borrow between 100 and 2000 gold per loan; max 3 concurrent active loans
- [ ] AC2: Each turn, 15% compound interest is added to all active loans
- [ ] AC3: Player can repay any active loan (partial or full); loan closes when owed reaches 0
- [ ] AC4: Total debt ≥ 5000 gold triggers default: infamy +20, honor −20
- [ ] AC5: Banking UI (`/dynasty/<id>/banking`) shows treasury, active loans, loan history, borrow form, repay form
- [ ] AC6: Interest accrual is wired into `process_dynasty_turn()` automatically each turn
- [ ] AC7: Unit tests cover borrow, repay, interest accrual, default logic
- [ ] AC8: Integration tests cover banking_view, banking_borrow, banking_repay routes

## Tasks/Subtasks

- [x] Task 1: Create `Loan` DB model in `models/db_models.py`
  - [x] Add `loans` relationship to `DynastyDB`
  - [x] Add migration in `models/db_initialization.py`
- [x] Task 2: Implement `BankingSystem` in `models/banking_system.py`
  - [x] `borrow()` — validate amount, create loan, credit treasury
  - [x] `repay()` — validate, deduct, close loan when owed=0
  - [x] `accrue_interest_for_dynasty()` — compound interest + default check
  - [x] `get_active_loans()`, `get_loan_history()`, `total_debt()`
- [x] Task 3: Add banking routes to `blueprints/economy.py`
  - [x] `banking_view` GET
  - [x] `banking_borrow` POST
  - [x] `banking_repay` POST
- [x] Task 4: Create `templates/banking.html`
- [x] Task 5: Wire `accrue_interest_for_dynasty()` into `process_dynasty_turn()` in `blueprints/dynasty.py`
- [ ] Task 6: Fix `format_number` Jinja2 filter bug in `templates/banking.html`
- [ ] Task 7: Write unit tests for `BankingSystem` in `tests/unit/test_banking_system.py`
- [ ] Task 8: Write integration tests for banking routes in `tests/integration/test_banking_routes.py`
- [ ] Task 9: Commit all files and update STATUS.md

## Dev Notes

- `Loan.__tablename__ = 'loan'`; `DynastyDB.loans` uses `back_populates`, no `backref`
- `infamy` and `honor` columns already exist on `DynastyDB` (lines 65-66 of db_models.py)
- `format_number` filter is used in banking.html but NOT registered in Flask app — fix by removing the filter and using plain `{{ dynasty.current_wealth }}` or registering a filter
- `max_active_loans` not passed to template from view — template uses `default(3)` which works; optionally pass it explicitly for clarity
- Test fixture pattern: session-scoped `app`, function-scoped `session` that drops/recreates tables
- Integration tests need `_register_and_login()` + `_create_dynasty()` helpers (see `tests/integration/test_dynasty_routes.py`)
- LLM not used in banking — no mock needed

## Dev Agent Record

### Implementation Plan

Partially implemented. Completing: fix template filter bug, write tests.

### Debug Log

_empty_

### Completion Notes

_empty_

## File List

- `models/banking_system.py` (new)
- `models/db_models.py` (modified — Loan model, DynastyDB.loans relationship)
- `models/db_initialization.py` (modified — loan table migration)
- `blueprints/economy.py` (modified — 3 banking routes)
- `blueprints/dynasty.py` (modified — interest wired into advance_turn)
- `templates/banking.html` (new)
- `tests/unit/test_banking_system.py` (new — TODO)
- `tests/integration/test_banking_routes.py` (new — TODO)
- `STATUS.md` (modified)

## Change Log

- 2026-05-01: Story created from CLAUDE.md Task 10B spec; Tasks 1-5 already complete on branch
