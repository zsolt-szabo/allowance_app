"""Tests for the column <-> array conversion.

The database columns are positional (acct1..acct5, location1..location7)
and the API emits arrays. Slots are 1-based, array positions are 0-based,
so this is where an off-by-one would be introduced -- and it would be
quiet, moving a kid's money between sub-accounts in the display.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.api import serializers
from app.domain import buckets
from tests import factories as f


def test_bucket_arrays_carry_their_own_index(db_):
    parent = f.make_parent()
    kid = f.make_kid(parent, accounts=("Spending", "Savings"),
                     locations=("Wallet",))

    accounts = serializers.account_buckets(kid)
    locations = serializers.location_buckets(kid)

    assert [b["index"] for b in accounts] == list(buckets.ACCOUNT_SLOTS)
    assert [b["index"] for b in locations] == list(buckets.LOCATION_SLOTS)
    #  Position n holds slot n+1, and the name matches the column.
    assert accounts[0]["name"] == kid.acct1_name
    assert accounts[1]["name"] == kid.acct2_name
    assert locations[0]["name"] == kid.location1_name


def test_active_flags_line_up_with_the_columns(db_):
    parent = f.make_parent()
    kid = f.make_kid(parent, accounts=("A1", "A2", "A3"),
                     locations=("L1",))
    accounts = serializers.account_buckets(kid)

    for bucket in accounts:
        expected = getattr(kid, "acct%s_used" % bucket["index"])
        assert bucket["active"] is bool(expected), \
            "slot %s misaligned" % bucket["index"]


def test_ledger_arrays_match_the_columns(db_):
    parent = f.make_parent()
    kid = f.make_kid(parent)
    from app import db, models
    row = models.Ledger(kid_id=kid.id, adjusted_by_parent=True,
                        adjuster_name="P",
                        total_acc1=1, total_acc2=2, total_acc3=3,
                        total_acc4=4, total_acc5=5,
                        total_loc1=10, total_loc2=20, total_loc3=30,
                        total_loc4=40, total_loc5=50, total_loc6=60,
                        total_loc7=70)
    db.session.add(row)
    db.session.commit()

    out = serializers.ledger_entry(row)
    assert out["accountTotals"] == [1, 2, 3, 4, 5]
    assert out["locationTotals"] == [10, 20, 30, 40, 50, 60, 70]


def test_cells_payload_maps_to_one_based_slot_pairs():
    payload = [{"account": 1, "location": 1, "amount": 5},
               {"account": 5, "location": 7, "amount": -2}]
    assert serializers.cells_from_payload(payload) == {(1, 1): 5, (5, 7): -2}


def test_percents_to_slots_is_one_based():
    values = [10, 20, 30, 40, 0]
    mapped = serializers.percents_to_slots(values, buckets.ACCOUNT_SLOTS)
    assert mapped == {1: 10, 2: 20, 3: 30, 4: 40, 5: 0}
    #  Array position 0 is slot 1, not slot 0.
    assert 0 not in mapped


@settings(max_examples=50, deadline=None)
@given(st.lists(st.floats(min_value=0, max_value=100,
                          allow_nan=False, allow_infinity=False),
                min_size=5, max_size=5))
def test_percent_round_trip_preserves_position(values):
    """slots -> array -> slots must be the identity."""
    mapped = serializers.percents_to_slots(values, buckets.ACCOUNT_SLOTS)
    back = [mapped[slot] for slot in buckets.ACCOUNT_SLOTS]
    assert back == values


@settings(max_examples=50, deadline=None)
@given(st.dictionaries(
    keys=st.tuples(st.integers(min_value=1, max_value=5),
                   st.integers(min_value=1, max_value=7)),
    values=st.floats(min_value=-1000, max_value=1000,
                     allow_nan=False, allow_infinity=False),
    max_size=35))
def test_cell_round_trip_preserves_addresses(cells):
    """grid -> payload -> grid must be the identity."""
    payload = [{"account": a, "location": lo, "amount": amount}
               for (a, lo), amount in cells.items()]
    assert serializers.cells_from_payload(payload) == cells
