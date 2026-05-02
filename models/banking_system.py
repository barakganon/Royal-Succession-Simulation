# models/banking_system.py
# Banking subsystem: borrow gold, accrue interest each turn, repay loans.
#
# Design:
#   - Max 3 active loans per dynasty
#   - Minimum borrow: 100 gold; Maximum: 2 000 gold per loan
#   - Interest rate: 15 % per turn (compounding)
#   - Interest is accrued by calling accrue_interest_for_dynasty() each turn
#     (called from process_dynasty_turn inside blueprints/dynasty.py)
#   - Defaulting (amount_owed > 5 000) applies -20 infamy and destroys honor

import logging
from sqlalchemy.orm import Session
from models.db_models import DynastyDB, Loan

logger = logging.getLogger('royal_succession.banking')

MIN_LOAN = 100
MAX_LOAN = 2000
MAX_ACTIVE_LOANS = 3
DEFAULT_INTEREST_RATE = 15  # percent per turn
DEFAULT_THRESHOLD = 5000    # gold owed before the dynasty "defaults"


class BankingSystem:
    """Handles loans, repayments, and interest accrual for a dynasty."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_active_loans(self, dynasty_id: int) -> list:
        return (
            self.session.query(Loan)
            .filter_by(dynasty_id=dynasty_id, is_active=True)
            .order_by(Loan.year_borrowed)
            .all()
        )

    def get_loan_history(self, dynasty_id: int) -> list:
        return (
            self.session.query(Loan)
            .filter_by(dynasty_id=dynasty_id)
            .order_by(Loan.year_borrowed.desc())
            .all()
        )

    def total_debt(self, dynasty_id: int) -> int:
        """Sum of amount_owed across all active loans."""
        loans = self.get_active_loans(dynasty_id)
        return sum(loan.amount_owed for loan in loans)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def borrow(self, dynasty_id: int, amount: int, current_year: int) -> dict:
        """Disburse a new loan to the dynasty and credit their treasury.

        Returns {'success': bool, 'message': str}.
        """
        if amount < MIN_LOAN or amount > MAX_LOAN:
            return {
                'success': False,
                'message': f'Loan amount must be between {MIN_LOAN} and {MAX_LOAN} gold.',
            }

        active_count = (
            self.session.query(Loan)
            .filter_by(dynasty_id=dynasty_id, is_active=True)
            .count()
        )
        if active_count >= MAX_ACTIVE_LOANS:
            return {
                'success': False,
                'message': f'Maximum of {MAX_ACTIVE_LOANS} concurrent loans reached.',
            }

        dynasty = self.session.get(DynastyDB, dynasty_id)
        if dynasty is None:
            return {'success': False, 'message': 'Dynasty not found.'}

        try:
            loan = Loan(
                dynasty_id=dynasty_id,
                principal=amount,
                amount_owed=amount,
                interest_rate=DEFAULT_INTEREST_RATE,
                year_borrowed=current_year,
                is_active=True,
            )
            dynasty.current_wealth += amount
            self.session.add(loan)
            self.session.commit()
            logger.info(
                'Dynasty %s borrowed %d gold (loan id=%s, year=%s)',
                dynasty_id, amount, loan.id, current_year,
            )
            return {
                'success': True,
                'message': f'{amount:,} gold deposited in your treasury. Repay promptly — interest compounds each turn.',
                'loan_id': loan.id,
            }
        except Exception as exc:
            self.session.rollback()
            logger.error('borrow() failed for dynasty %s: %s', dynasty_id, exc)
            return {'success': False, 'message': 'Failed to issue loan. Try again.'}

    def repay(self, dynasty_id: int, loan_id: int, amount: int, current_year: int) -> dict:
        """Repay `amount` gold toward a specific loan.

        Deducts gold from the dynasty treasury and reduces amount_owed.
        If amount_owed reaches 0 the loan is marked repaid.
        """
        loan = self.session.get(Loan, loan_id)
        if loan is None or loan.dynasty_id != dynasty_id or not loan.is_active:
            return {'success': False, 'message': 'Loan not found or already repaid.'}

        dynasty = self.session.get(DynastyDB, dynasty_id)
        if dynasty is None:
            return {'success': False, 'message': 'Dynasty not found.'}

        if amount <= 0:
            return {'success': False, 'message': 'Repayment amount must be positive.'}

        if amount > dynasty.current_wealth:
            return {
                'success': False,
                'message': f'Insufficient gold. You have {dynasty.current_wealth:,} but tried to repay {amount:,}.',
            }

        try:
            actual_payment = min(amount, loan.amount_owed)
            loan.amount_owed -= actual_payment
            dynasty.current_wealth -= actual_payment

            if loan.amount_owed <= 0:
                loan.amount_owed = 0
                loan.is_active = False
                loan.year_repaid = current_year
                msg = f'Loan repaid in full! You paid {actual_payment:,} gold.'
            else:
                msg = (
                    f'Paid {actual_payment:,} gold. '
                    f'Remaining balance: {loan.amount_owed:,} gold.'
                )

            self.session.commit()
            logger.info(
                'Dynasty %s repaid %d gold on loan %s (remaining %d)',
                dynasty_id, actual_payment, loan_id, loan.amount_owed,
            )
            return {'success': True, 'message': msg}
        except Exception as exc:
            self.session.rollback()
            logger.error('repay() failed for dynasty %s loan %s: %s', dynasty_id, loan_id, exc)
            return {'success': False, 'message': 'Repayment failed. Try again.'}

    # ------------------------------------------------------------------
    # Per-turn processing
    # ------------------------------------------------------------------

    def accrue_interest_for_dynasty(self, dynasty_id: int) -> list[str]:
        """Apply interest to all active loans. Returns list of event strings.

        Call this once per turn from process_dynasty_turn().
        If total debt exceeds DEFAULT_THRESHOLD the dynasty takes a reputation hit.
        """
        events = []
        loans = self.get_active_loans(dynasty_id)
        if not loans:
            return events

        dynasty = self.session.get(DynastyDB, dynasty_id)
        if dynasty is None:
            return events

        try:
            for loan in loans:
                interest = max(1, int(loan.amount_owed * loan.interest_rate / 100))
                loan.amount_owed += interest
                events.append(
                    f'Loan interest accrued: +{interest:,} gold owed '
                    f'(total balance {loan.amount_owed:,} gold).'
                )

            total = self.total_debt(dynasty_id)
            if total >= DEFAULT_THRESHOLD:
                # Default penalty
                dynasty.infamy = (dynasty.infamy or 0) + 20
                dynasty.honor = max(0, (dynasty.honor or 50) - 20)
                events.append(
                    f'Your dynasty is drowning in debt ({total:,} gold owed)! '
                    f'Creditors spread word of your ruin — infamy +20, honor -20.'
                )

            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            logger.error('accrue_interest_for_dynasty() failed for %s: %s', dynasty_id, exc)

        return events
