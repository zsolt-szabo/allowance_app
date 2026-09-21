"""Characterization tests for the allowance payout engine.

``app/lib/a_index.py::check_and_update_allowances`` is the most valuable and
least tested code in this repository.  These tests pin its behaviour
*exactly as it is today* -- including the parts that are wrong.  Tests named
``test_KNOWN_BUG_*`` assert the current (incorrect) behaviour on purpose; the
Stage 5 fix for each one flips exactly that assertion, which is what proves the
fix changed one thing and nothing else.

All tests freeze the clock: the engine works in UTC calendar days, and the
legacy suite's payout test silently no-ops on the 29th-31st of a month for
exactly this reason.
"""
import datetime

import time_machine

from app import db, models
from app.lib import a_index
from tests import factories as f
from tests.helpers import (account_changes, account_totals,
                           assert_book_balances, assert_totals_chain,
                           location_changes, location_totals)

# A mid-month date so a watermark one day back lands on the 15th.
FROZEN_NOW = datetime.datetime(2026, 3, 15, 12, 0,
                               tzinfo=datetime.timezone.utc)
ALL_TO_ACC1 = (100, 0, 0, 0, 0)
ALL_TO_LOC1 = (100, 0, 0, 0, 0, 0, 0)


def run_payouts():
    """Exactly what ``allowance_payout_cron.py`` does."""
    result = a_index.check_and_update_allowances(f.allowance_rows())
    db.session.commit()
    return result


def test_single_payout_writes_exact_columns(db_, kid):
    """A $10 allowance split 80/20 across accounts, all into location 1."""
    with time_machine.travel(FROZEN_NOW, tick=False):
        f.make_allowance(kid, amount=10.0, payout_days=(15,),
                         account_percs=(80, 20, 0, 0, 0),
                         location_percs=ALL_TO_LOC1,
                         last_ledger_update=f.days_ago(1))
        assert run_payouts() is True

        rows = f.ledger_for(kid)
        assert len(rows) == 1
        row = rows[0]

        assert account_changes(row) == [8, 2, 0, 0, 0]
        assert location_changes(row) == [10, 0, 0, 0, 0, 0, 0]
        assert account_totals(row) == [8, 2, 0, 0, 0]
        assert location_totals(row) == [10, 0, 0, 0, 0, 0, 0]

        # Payout rows are attributed to the engine, not a person.
        assert row.adjuster_name == "ALLOWANCE"
        assert row.adjusted_by_parent is True
        assert row.comment == "Payout for 'allowance' date: 2026-03-15"

        assert_book_balances(kid.id)
        assert_totals_chain(kid.id)


def test_remainder_is_absorbed_into_account5(db_, kid):
    """Accounts 1-4 are computed from their percentages; account 5 receives
    ``amount - (perc1..4 / 100 * amount)`` so the axis cannot lose money."""
    with time_machine.travel(FROZEN_NOW, tick=False):
        f.make_allowance(kid, amount=10.0, payout_days=(15,),
                         account_percs=(30, 30, 30, 0, 10),
                         location_percs=ALL_TO_LOC1,
                         last_ledger_update=f.days_ago(1))
        run_payouts()
        row = f.ledger_for(kid)[0]

        assert account_changes(row) == [3, 3, 3, 0, 1]
        assert round(sum(account_changes(row)), 2) == 10.0
        assert_book_balances(kid.id)


def test_remainder_is_absorbed_into_location7(db_, kid):
    """The same absorber exists on the location axis, in slot 7."""
    with time_machine.travel(FROZEN_NOW, tick=False):
        f.make_allowance(kid, amount=10.0, payout_days=(15,),
                         account_percs=ALL_TO_ACC1,
                         location_percs=(20, 20, 20, 20, 10, 0, 10),
                         last_ledger_update=f.days_ago(1),
                         )
        run_payouts()
        row = f.ledger_for(kid)[0]

        assert location_changes(row) == [2, 2, 2, 2, 1, 0, 1]
        assert round(sum(location_changes(row)), 2) == 10.0
        assert_book_balances(kid.id)


def test_multi_day_catchup_pays_each_matching_day(db_, kid):
    """If the job has not run for 40 days, every payout day inside that window
    is paid retroactively -- one ledger row each."""
    with time_machine.travel(FROZEN_NOW, tick=False):
        f.make_allowance(kid, amount=5.0, payout_days=(1,),
                         account_percs=ALL_TO_ACC1,
                         location_percs=ALL_TO_LOC1,
                         last_ledger_update=f.days_ago(40))
        run_payouts()

        rows = f.ledger_for(kid)
        # 40 days back from 2026-03-15 is 2026-02-03; only Mar 1 matches.
        assert [r.comment for r in rows] == [
            "Payout for 'allowance' date: 2026-03-01"]
        assert rows[0].total_acc1 == 5
        assert_totals_chain(kid.id)


def test_catchup_chains_running_totals_across_entries(db_, kid):
    """Successive payouts in one run chain off the previous *uncommitted* row
    (the ``ll = ledge_entry`` trick), so totals accumulate correctly."""
    with time_machine.travel(FROZEN_NOW, tick=False):
        f.make_allowance(kid, amount=5.0, payout_days=(1,),
                         account_percs=ALL_TO_ACC1,
                         location_percs=ALL_TO_LOC1,
                         last_ledger_update=f.days_ago(75))
        run_payouts()

        rows = f.ledger_for(kid)
        # 75 days back from 2026-03-15 is 2025-12-30: Jan 1, Feb 1, Mar 1.
        assert len(rows) == 3
        assert [r.total_acc1 for r in rows] == [5, 10, 15]
        assert [r.change_acc1 for r in rows] == [5, 5, 5]
        assert_totals_chain(kid.id)
        assert_book_balances(kid.id)


def test_idempotent_within_the_same_day(db_, kid):
    """Running the cron twice in one day must not pay twice."""
    with time_machine.travel(FROZEN_NOW, tick=False):
        f.make_allowance(kid, amount=5.0, payout_days=(15,),
                         account_percs=ALL_TO_ACC1,
                         location_percs=ALL_TO_LOC1,
                         last_ledger_update=f.days_ago(1))
        assert run_payouts() is True
        assert len(f.ledger_for(kid)) == 1

        assert run_payouts() is False
        assert len(f.ledger_for(kid)) == 1


def test_allowance_with_no_payout_days_never_pays(db_, kid):
    """The engine is driven by an inner join, so an allowance with no
    AllowanceDays rows is invisible to it."""
    with time_machine.travel(FROZEN_NOW, tick=False):
        f.make_allowance(kid, amount=5.0, payout_days=(),
                         account_percs=ALL_TO_ACC1,
                         location_percs=ALL_TO_LOC1,
                         last_ledger_update=f.days_ago(10))
        assert f.allowance_rows() == []
        # NOTE: returns None, not False, for an empty batch -- the
        # `return update_occurred` sits inside `if len(allowances) > 0`
        # even though the docstring promises a bool.
        assert run_payouts() is None
        assert f.ledger_for(kid) == []


# ---------------------------------------------------------------------------
# Known bugs. These assert today's WRONG behaviour so the Stage 5 fixes are
# provably single-behaviour changes.
# ---------------------------------------------------------------------------

def test_KNOWN_BUG_rounding_breaks_the_two_axis_invariant(db_, kid):
    """The remainder absorber only catches residue left in slots acc5/loc7.

    When percentages 1-4 already sum to 100 but do not divide into whole cents,
    the rounding loss is never recovered and the two axes silently disagree --
    here accounts hold $9.99 while locations hold $10.00 of the same money.
    """
    with time_machine.travel(FROZEN_NOW, tick=False):
        f.make_allowance(kid, amount=10.0, payout_days=(15,),
                         account_percs=(33.33, 33.33, 33.34, 0, 0),
                         location_percs=ALL_TO_LOC1,
                         last_ledger_update=f.days_ago(1))
        run_payouts()
        row = f.ledger_for(kid)[0]

        assert account_changes(row) == [3.33, 3.33, 3.33, 0, 0]
        assert round(sum(account_changes(row)), 2) == 9.99
        assert round(sum(location_changes(row)), 2) == 10.0

        # The invariant the whole data model rests on is violated.
        try:
            assert_book_balances(kid.id)
        except AssertionError:
            pass
        else:
            raise AssertionError(
                "Expected the two-axis invariant to be violated here. If this "
                "now passes, the rounding bug is fixed -- delete this test.")


def test_KNOWN_BUG_batch_flag_advances_watermark_without_paying(db_, parent):
    """``update_occurred`` is initialised once outside the per-allowance loop
    (a_index.py:82) but checked inside it (a_index.py:227).

    So once *any* allowance in the batch pays out, every later allowance has
    its watermark advanced to today even though it paid nothing -- silently
    skipping the days it should have been paid for on the next run.
    """
    with time_machine.travel(FROZEN_NOW, tick=False):
        kid_a = f.make_kid(parent, firstname="kidA",
                           animal1="rabbit", animal2="rabbit")
        kid_b = f.make_kid(parent, firstname="kidB",
                           animal1="tiger", animal2="tiger")

        f.make_allowance(kid_a, amount=5.0, payout_days=(15,),
                         account_percs=ALL_TO_ACC1, location_percs=ALL_TO_LOC1,
                         last_ledger_update=f.days_ago(1))
        # Pays on the 20th, which a one-day window cannot reach.
        allowance_b = f.make_allowance(
            kid_b, amount=7.0, payout_days=(20,),
            account_percs=ALL_TO_ACC1, location_percs=ALL_TO_LOC1,
            last_ledger_update=f.days_ago(1))
        watermark_before = allowance_b.last_ledger_update

        run_payouts()

        assert len(f.ledger_for(kid_a)) == 1, "kidA was due and should be paid"
        assert len(f.ledger_for(kid_b)) == 0, "kidB was not due"

        refreshed = db.session.get(models.Allowance, allowance_b.id)
        assert refreshed.last_ledger_update != watermark_before, (
            "Expected kidB's watermark to be wrongly advanced. If this now "
            "holds steady, the update_occurred bug is fixed -- invert this "
            "assertion.")
        assert refreshed.last_ledger_update == datetime.datetime(2026, 3, 15)


def test_KNOWN_BUG_duplicate_payout_days_pay_twice(db_, kid):
    """``UniqueConstraint('id', 'payout_day')`` is a no-op because ``id`` is
    already the primary key; the intended constraint is on
    ``('allowance_id', 'payout_day')``.

    Two identical payout-day rows therefore insert cleanly and pay twice.
    """
    with time_machine.travel(FROZEN_NOW, tick=False):
        f.make_allowance(kid, amount=5.0, payout_days=(15, 15),
                         account_percs=ALL_TO_ACC1,
                         location_percs=ALL_TO_LOC1,
                         last_ledger_update=f.days_ago(1))
        assert models.AllowanceDays.query.count() == 2, (
            "Duplicate (allowance_id, payout_day) was rejected -- the missing "
            "constraint has been added; invert this test.")

        run_payouts()

        rows = f.ledger_for(kid)
        assert len(rows) == 2, "the same day paid out twice"
        assert [r.total_acc1 for r in rows] == [5, 10]
