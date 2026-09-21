"""Sanity check that the fixtures build a usable world."""
from tests import factories as f
from tests.helpers import assert_book_balances


def test_fixtures_build_a_kid(db, models):
    parent = f.make_parent()
    kid = f.make_kid(parent)
    assert kid.parent_id == parent.id
    assert kid.acct1_name == "Spending"
    assert kid.acct1_used is True
    assert kid.acct3_used is False
    assert models.Kid.query.count() == 1
    assert_book_balances(kid.id)


def test_fixtures_build_an_allowance(db, models):
    parent = f.make_parent()
    kid = f.make_kid(parent)
    allowance = f.make_allowance(kid, amount=3.0, payout_days=(1, 10, 20),
                                 account_percs=(80, 20, 0, 0, 0))
    assert allowance.amount == 3.0
    assert allowance.account1_perc == 80
    assert models.AllowanceDays.query.count() == 3
    assert len(f.allowance_rows()) == 3
