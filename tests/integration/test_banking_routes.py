# tests/integration/test_banking_routes.py
# Integration tests for the banking subsystem routes.

import pytest
from models.db_models import User, DynastyDB, Loan

VALID_THEME_KEY = 'MEDIEVAL_EUROPEAN'


def _register_and_login(app, db, client, username="bank_user", password="bankpass123"):
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'username': username, 'password': password})


def _create_dynasty(client, dynasty_name="House Goldvault", start_year="1100"):
    return client.post(
        '/dynasty/create',
        data={
            'dynasty_name': dynasty_name,
            'theme_type': 'predefined',
            'theme_key': VALID_THEME_KEY,
            'start_year': start_year,
            'succession_rule': 'PRIMOGENITURE_MALE_PREFERENCE',
        },
        follow_redirects=True,
    )


def _get_dynasty_id(app, db, username="bank_user"):
    with app.app_context():
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            return None
        dynasty = db.session.query(DynastyDB).filter_by(user_id=user.id).first()
        return dynasty.id if dynasty else None


@pytest.fixture
def client(app, session):
    return app.test_client()


class TestBankingView:
    def test_banking_view_requires_login(self, app, client, session):
        resp = client.get('/dynasty/1/banking', follow_redirects=True)
        assert resp.status_code == 200
        assert b'login' in resp.data.lower()

    def test_banking_view_renders_for_owner(self, app, db, client, session):
        _register_and_login(app, db, client, "bv_user")
        _create_dynasty(client, "House Bvault")
        dynasty_id = _get_dynasty_id(app, db, "bv_user")
        assert dynasty_id is not None

        resp = client.get(f'/dynasty/{dynasty_id}/banking')
        assert resp.status_code == 200
        assert b'Moneylender' in resp.data or b'Banking' in resp.data or b'Treasury' in resp.data

    def test_banking_view_forbidden_for_non_owner(self, app, db, client, session):
        _register_and_login(app, db, client, "bv_owner")
        _create_dynasty(client, "House Owner")
        dynasty_id = _get_dynasty_id(app, db, "bv_owner")

        # Log in as a different user
        with app.app_context():
            other = User(username="bv_other", email="bv_other@example.com")
            other.set_password("pw")
            db.session.add(other)
            db.session.commit()
        client.get('/logout')
        client.post('/login', data={'username': 'bv_other', 'password': 'pw'})

        resp = client.get(f'/dynasty/{dynasty_id}/banking', follow_redirects=True)
        assert resp.status_code == 200
        assert b'Not authorized' in resp.data or b'dashboard' in resp.data.lower()


class TestBankingBorrow:
    def test_borrow_valid_amount_credits_treasury(self, app, db, client, session):
        _register_and_login(app, db, client, "borrow_integ")
        _create_dynasty(client, "House Borrow")
        dynasty_id = _get_dynasty_id(app, db, "borrow_integ")

        with app.app_context():
            dynasty_before = db.session.get(DynastyDB, dynasty_id)
            wealth_before = dynasty_before.current_wealth

        resp = client.post(
            f'/dynasty/{dynasty_id}/banking/borrow',
            data={'amount': '500'},
            follow_redirects=True,
        )
        assert resp.status_code == 200

        with app.app_context():
            dynasty = db.session.get(DynastyDB, dynasty_id)
            assert dynasty.current_wealth == wealth_before + 500
            loans = db.session.query(Loan).filter_by(dynasty_id=dynasty_id, is_active=True).all()
            assert len(loans) == 1
            assert loans[0].principal == 500

    def test_borrow_below_minimum_flashes_error(self, app, db, client, session):
        _register_and_login(app, db, client, "borrow_low_i")
        _create_dynasty(client, "House Low")
        dynasty_id = _get_dynasty_id(app, db, "borrow_low_i")

        resp = client.post(
            f'/dynasty/{dynasty_id}/banking/borrow',
            data={'amount': '50'},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b'between' in resp.data or b'amount' in resp.data.lower()

    def test_borrow_non_numeric_amount_handled(self, app, db, client, session):
        _register_and_login(app, db, client, "borrow_nan")
        _create_dynasty(client, "House NaN")
        dynasty_id = _get_dynasty_id(app, db, "borrow_nan")

        resp = client.post(
            f'/dynasty/{dynasty_id}/banking/borrow',
            data={'amount': 'abc'},
            follow_redirects=True,
        )
        assert resp.status_code == 200


class TestBankingRepay:
    def test_repay_reduces_loan_balance(self, app, db, client, session):
        _register_and_login(app, db, client, "repay_integ")
        _create_dynasty(client, "House Repay")
        dynasty_id = _get_dynasty_id(app, db, "repay_integ")

        # First borrow
        client.post(
            f'/dynasty/{dynasty_id}/banking/borrow',
            data={'amount': '500'},
            follow_redirects=True,
        )

        with app.app_context():
            loan = db.session.query(Loan).filter_by(dynasty_id=dynasty_id, is_active=True).first()
            loan_id = loan.id

        resp = client.post(
            f'/dynasty/{dynasty_id}/banking/repay',
            data={'loan_id': str(loan_id), 'amount': '200'},
            follow_redirects=True,
        )
        assert resp.status_code == 200

        with app.app_context():
            loan = db.session.get(Loan, loan_id)
            assert loan.amount_owed == 300
            assert loan.is_active is True

    def test_repay_full_amount_closes_loan(self, app, db, client, session):
        _register_and_login(app, db, client, "repay_full_i")
        _create_dynasty(client, "House Full")
        dynasty_id = _get_dynasty_id(app, db, "repay_full_i")

        client.post(
            f'/dynasty/{dynasty_id}/banking/borrow',
            data={'amount': '300'},
            follow_redirects=True,
        )

        with app.app_context():
            loan = db.session.query(Loan).filter_by(dynasty_id=dynasty_id, is_active=True).first()
            loan_id = loan.id

        client.post(
            f'/dynasty/{dynasty_id}/banking/repay',
            data={'loan_id': str(loan_id), 'amount': '300'},
            follow_redirects=True,
        )

        with app.app_context():
            loan = db.session.get(Loan, loan_id)
            assert loan.is_active is False
            assert loan.amount_owed == 0

    def test_repay_invalid_values_handled(self, app, db, client, session):
        _register_and_login(app, db, client, "repay_bad_i")
        _create_dynasty(client, "House Bad")
        dynasty_id = _get_dynasty_id(app, db, "repay_bad_i")

        resp = client.post(
            f'/dynasty/{dynasty_id}/banking/repay',
            data={'loan_id': 'notanumber', 'amount': 'alsonot'},
            follow_redirects=True,
        )
        assert resp.status_code == 200
