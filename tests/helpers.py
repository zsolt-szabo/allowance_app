"""Shared assertions.

``assert_book_balances`` encodes the invariant the entire two-axis data model
rests on and which the application asserts *nowhere*: the money split across
the 5 sub-accounts must always equal the split across the 7 locations.
"""
from app import models

ACCOUNT_SLOTS = range(1, 6)
LOCATION_SLOTS = range(1, 8)


def account_totals(row):
    return [getattr(row, "total_acc%s" % i) or 0 for i in ACCOUNT_SLOTS]


def location_totals(row):
    return [getattr(row, "total_loc%s" % j) or 0 for j in LOCATION_SLOTS]


def account_changes(row):
    return [getattr(row, "change_acc%s" % i) or 0 for i in ACCOUNT_SLOTS]


def location_changes(row):
    return [getattr(row, "change_loc%s" % j) or 0 for j in LOCATION_SLOTS]


def assert_book_balances(kid_id, tolerance=0.0):
    """Every ledger row for this kid must balance across both axes."""
    rows = models.Ledger.query.filter(
        models.Ledger.kid_id == kid_id).order_by(models.Ledger.id).all()
    for row in rows:
        acc = round(sum(account_totals(row)), 2)
        loc = round(sum(location_totals(row)), 2)
        assert abs(acc - loc) <= tolerance, (
            "Ledger row %s for kid %s does not balance: "
            "accounts=%s (sum %s) vs locations=%s (sum %s)"
            % (row.id, kid_id, account_totals(row), acc,
               location_totals(row), loc))
    return rows


def assert_totals_chain(kid_id):
    """Each row's totals must equal the previous row's totals plus this row's
    changes -- the append-only running-balance property."""
    rows = models.Ledger.query.filter(
        models.Ledger.kid_id == kid_id).order_by(models.Ledger.id).all()
    prev_acc = [0] * 5
    prev_loc = [0] * 7
    for row in rows:
        want_acc = [round(p + c, 2)
                    for p, c in zip(prev_acc, account_changes(row))]
        want_loc = [round(p + c, 2)
                    for p, c in zip(prev_loc, location_changes(row))]
        assert account_totals(row) == want_acc, (
            "Row %s account totals %s != previous %s + changes %s = %s"
            % (row.id, account_totals(row), prev_acc,
               account_changes(row), want_acc))
        assert location_totals(row) == want_loc, (
            "Row %s location totals %s != previous %s + changes %s = %s"
            % (row.id, location_totals(row), prev_loc,
               location_changes(row), want_loc))
        prev_acc, prev_loc = account_totals(row), location_totals(row)
    return rows
