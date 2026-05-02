# tests/unit/test_banking_system.py
import pytest
from models.banking_system import BankingSystem, MIN_LOAN, MAX_LOAN, MAX_ACTIVE_LOANS, DEFAULT_THRESHOLD
from models.db_models import DynastyDB, User, Loan


def _make_dynasty(session, app, username="bank_unit_user", wealth=1000):
    """Create a minimal User + DynastyDB for testing."""
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password("pw")
        session.add(user)
        session.flush()

        dynasty = DynastyDB(
            user_id=user.id,
            name="Test House",
            theme_identifier_or_json="MEDIEVAL_EUROPEAN",
            start_year=1000,
            current_simulation_year=1000,
            current_wealth=wealth,
        )
        session.add(dynasty)
        session.commit()
        return dynasty.id


@pytest.mark.unit
class TestBankingSystemBorrow:
    def test_borrow_success_credits_treasury(self, session, app):
        dynasty_id = _make_dynasty(session, app, "borrow_ok")
        with app.app_context():
            bs = BankingSystem(session)
            result = bs.borrow(dynasty_id, 500, 1000)
            assert result['success'] is True
            dynasty = session.get(DynastyDB, dynasty_id)
            assert dynasty.current_wealth == 1000 + 500
            loans = bs.get_active_loans(dynasty_id)
            assert len(loans) == 1
            assert loans[0].principal == 500
            assert loans[0].amount_owed == 500

    def test_borrow_below_minimum_rejected(self, session, app):
        dynasty_id = _make_dynasty(session, app, "borrow_low")
        with app.app_context():
            bs = BankingSystem(session)
            result = bs.borrow(dynasty_id, MIN_LOAN - 1, 1000)
            assert result['success'] is False
            assert 'between' in result['message']

    def test_borrow_above_maximum_rejected(self, session, app):
        dynasty_id = _make_dynasty(session, app, "borrow_high")
        with app.app_context():
            bs = BankingSystem(session)
            result = bs.borrow(dynasty_id, MAX_LOAN + 1, 1000)
            assert result['success'] is False

    def test_borrow_max_concurrent_loans_enforced(self, session, app):
        dynasty_id = _make_dynasty(session, app, "borrow_max", wealth=10000)
        with app.app_context():
            bs = BankingSystem(session)
            for _ in range(MAX_ACTIVE_LOANS):
                bs.borrow(dynasty_id, 500, 1000)
            result = bs.borrow(dynasty_id, 500, 1000)
            assert result['success'] is False
            assert 'Maximum' in result['message']

    def test_borrow_nonexistent_dynasty_rejected(self, session, app):
        with app.app_context():
            bs = BankingSystem(session)
            result = bs.borrow(99999, 500, 1000)
            assert result['success'] is False


@pytest.mark.unit
class TestBankingSystemRepay:
    def test_repay_partial_reduces_balance(self, session, app):
        dynasty_id = _make_dynasty(session, app, "repay_partial", wealth=1000)
        with app.app_context():
            bs = BankingSystem(session)
            borrow_result = bs.borrow(dynasty_id, 500, 1000)
            loan_id = borrow_result['loan_id']
            dynasty = session.get(DynastyDB, dynasty_id)
            treasury_before = dynasty.current_wealth

            result = bs.repay(dynasty_id, loan_id, 200, 1001)
            assert result['success'] is True
            loan = session.get(Loan, loan_id)
            assert loan.amount_owed == 300
            assert loan.is_active is True
            dynasty = session.get(DynastyDB, dynasty_id)
            assert dynasty.current_wealth == treasury_before - 200

    def test_repay_full_closes_loan(self, session, app):
        dynasty_id = _make_dynasty(session, app, "repay_full", wealth=2000)
        with app.app_context():
            bs = BankingSystem(session)
            borrow_result = bs.borrow(dynasty_id, 500, 1000)
            loan_id = borrow_result['loan_id']

            result = bs.repay(dynasty_id, loan_id, 500, 1001)
            assert result['success'] is True
            loan = session.get(Loan, loan_id)
            assert loan.is_active is False
            assert loan.amount_owed == 0
            assert loan.year_repaid == 1001

    def test_repay_insufficient_gold_rejected(self, session, app):
        dynasty_id = _make_dynasty(session, app, "repay_poor", wealth=100)
        with app.app_context():
            bs = BankingSystem(session)
            bs.borrow(dynasty_id, 100, 1000)
            dynasty = session.get(DynastyDB, dynasty_id)
            dynasty.current_wealth = 0
            session.commit()

            loans = bs.get_active_loans(dynasty_id)
            result = bs.repay(dynasty_id, loans[0].id, 50, 1001)
            assert result['success'] is False
            assert 'Insufficient' in result['message']

    def test_repay_wrong_dynasty_rejected(self, session, app):
        dynasty_id = _make_dynasty(session, app, "repay_wrong", wealth=1000)
        with app.app_context():
            bs = BankingSystem(session)
            borrow_result = bs.borrow(dynasty_id, 500, 1000)
            loan_id = borrow_result['loan_id']
            result = bs.repay(99999, loan_id, 100, 1001)
            assert result['success'] is False


@pytest.mark.unit
class TestBankingSystemInterest:
    def test_interest_accrues_each_turn(self, session, app):
        dynasty_id = _make_dynasty(session, app, "interest_basic", wealth=1000)
        with app.app_context():
            bs = BankingSystem(session)
            borrow_result = bs.borrow(dynasty_id, 1000, 1000)
            loan_id = borrow_result['loan_id']

            events = bs.accrue_interest_for_dynasty(dynasty_id)
            assert len(events) >= 1
            loan = session.get(Loan, loan_id)
            assert loan.amount_owed > 1000

    def test_interest_is_compound(self, session, app):
        dynasty_id = _make_dynasty(session, app, "interest_compound", wealth=1000)
        with app.app_context():
            bs = BankingSystem(session)
            bs.borrow(dynasty_id, 1000, 1000)

            bs.accrue_interest_for_dynasty(dynasty_id)
            loan_after_1 = bs.get_active_loans(dynasty_id)[0]
            owed_after_1 = loan_after_1.amount_owed

            bs.accrue_interest_for_dynasty(dynasty_id)
            loan_after_2 = bs.get_active_loans(dynasty_id)[0]
            interest_turn_2 = loan_after_2.amount_owed - owed_after_1
            # Second turn's interest must be larger than first turn's (compounding)
            first_interest = owed_after_1 - 1000
            assert interest_turn_2 >= first_interest

    def test_no_events_without_loans(self, session, app):
        dynasty_id = _make_dynasty(session, app, "interest_none", wealth=1000)
        with app.app_context():
            bs = BankingSystem(session)
            events = bs.accrue_interest_for_dynasty(dynasty_id)
            assert events == []

    def test_default_triggered_when_debt_exceeds_threshold(self, session, app):
        dynasty_id = _make_dynasty(session, app, "interest_default", wealth=10000)
        with app.app_context():
            bs = BankingSystem(session)
            # Borrow enough that interest will push total debt over DEFAULT_THRESHOLD
            for _ in range(MAX_ACTIVE_LOANS):
                bs.borrow(dynasty_id, MAX_LOAN, 1000)

            dynasty = session.get(DynastyDB, dynasty_id)
            dynasty.loans  # ensure relationship loaded

            # Manually inflate amount_owed to just below threshold
            loans = bs.get_active_loans(dynasty_id)
            total = 0
            for loan in loans:
                loan.amount_owed = (DEFAULT_THRESHOLD // MAX_ACTIVE_LOANS) + 1
                total += loan.amount_owed
            session.commit()

            infamy_before = dynasty.infamy or 0
            honor_before = dynasty.honor or 50
            events = bs.accrue_interest_for_dynasty(dynasty_id)

            dynasty = session.get(DynastyDB, dynasty_id)
            default_events = [e for e in events if 'infamy' in e]
            assert len(default_events) >= 1
            assert dynasty.infamy > infamy_before
            assert dynasty.honor < honor_before


@pytest.mark.unit
class TestBankingSystemQueries:
    def test_total_debt_sums_active_loans(self, session, app):
        dynasty_id = _make_dynasty(session, app, "debt_sum", wealth=5000)
        with app.app_context():
            bs = BankingSystem(session)
            bs.borrow(dynasty_id, 500, 1000)
            bs.borrow(dynasty_id, 300, 1000)
            assert bs.total_debt(dynasty_id) == 800

    def test_loan_history_includes_repaid(self, session, app):
        dynasty_id = _make_dynasty(session, app, "hist_query", wealth=5000)
        with app.app_context():
            bs = BankingSystem(session)
            r = bs.borrow(dynasty_id, 500, 1000)
            bs.repay(dynasty_id, r['loan_id'], 500, 1001)
            history = bs.get_loan_history(dynasty_id)
            assert len(history) == 1
            assert history[0].is_active is False
