"""Characterization tests for manual ledger entries.

``app/lib/a_finance.py::handle_ledger_post`` walks a 5x7 grid of deltas and
folds each cell into both its account row and its location column.  It is
driven here over HTTP, exactly as a browser drives it, because the function
reads ``request``/``g``/``flash`` directly -- so this suite keeps working
unchanged while the service layer is extracted underneath it.
"""
import re

import pytest

from tests import factories as f
from tests.helpers import (account_totals, assert_book_balances,
                           assert_totals_chain, location_totals)

KID_URL = "/ledger?kid=whipper:rabbit:rabbit"
PARENT_EMAIL = "parent@example.com"
PARENT_PW = "monstertruck"


def flash_messages(response):
    """Pull flash text out of a rendered page (base.html renders errors bold
    red and everything else as list items)."""
    text = response.data.decode()
    found = []
    for plain, error in re.findall(
            r'<li>(.*?)</li>|<b><font color="red"[^>]*>(.*?)</font></b>',
            text, re.S):
        message = (plain or error).strip()
        if message:
            found.append(
                re.sub(r"<[^>]+>", "", message).replace("&#39;", "'").strip())
    return found


@pytest.fixture
def world(db_, client):
    """A logged-in parent with one kid: accounts 1-2, locations 1-2."""
    parent = f.make_parent(email=PARENT_EMAIL, password=PARENT_PW)
    kid = f.make_kid(parent)
    client.post("/login", data={"email": PARENT_EMAIL, "password": PARENT_PW},
                follow_redirects=True)
    return parent, kid, client


def post_entry(client, **cells):
    comment = cells.pop("comment", "test entry")
    data = {k: str(v) for k, v in cells.items()}
    data["comment"] = comment
    return client.post(KID_URL, data=data, follow_redirects=True)


def login_child(client):
    client.get("/logout", follow_redirects=True)
    return client.post("/child_login",
                       data={"firstname": "whipper", "animal1": "rabbit",
                             "animal2": "rabbit", "password": "snapper",
                             "animal3": "goose", "animal4": "goose"},
                       follow_redirects=True)


def test_deposit_updates_both_axes(world):
    _, kid, client = world
    post_entry(client, acct1_loc1=10, comment="birthday money")

    rows = f.ledger_for(kid)
    assert len(rows) == 1
    assert account_totals(rows[0]) == [10, 0, 0, 0, 0]
    assert location_totals(rows[0]) == [10, 0, 0, 0, 0, 0, 0]
    assert rows[0].comment == "birthday money"
    assert rows[0].adjuster_name == "Parent"
    assert rows[0].adjusted_by_parent is True
    assert_book_balances(kid.id)


def test_running_totals_accumulate(world):
    _, kid, client = world
    post_entry(client, acct1_loc1=10, comment="one")
    post_entry(client, acct1_loc1=5, comment="two")
    post_entry(client, acct1_loc1=-3, comment="three")

    rows = f.ledger_for(kid)
    assert [r.total_acc1 for r in rows] == [10, 15, 12]
    assert [r.change_acc1 for r in rows] == [10, 5, -3]
    assert_totals_chain(kid.id)
    assert_book_balances(kid.id)


def test_one_entry_can_touch_several_cells(world):
    _, kid, client = world
    post_entry(client, acct1_loc1=6, acct2_loc2=4, comment="split deposit")

    row = f.ledger_for(kid)[-1]
    assert account_totals(row) == [6, 4, 0, 0, 0]
    assert location_totals(row) == [6, 4, 0, 0, 0, 0, 0]
    assert_book_balances(kid.id)


def test_overdrawing_a_location_is_rejected(world):
    _, kid, client = world
    post_entry(client, acct1_loc1=10, comment="seed")
    response = post_entry(client, acct1_loc1=-50, comment="too much")

    # The location axis is checked before the account axis, so the message
    # names the money storage rather than the sub-account.
    assert ("ERROR: You attempted to take too much from money storage "
            "'Mom/Dad's wallet'") in flash_messages(response)
    assert len(f.ledger_for(kid)) == 1, "no row written for a rejected entry"


def test_amount_outside_field_range_is_rejected_before_business_rules(world):
    _, kid, client = world
    post_entry(client, acct1_loc1=10, comment="seed")
    response = post_entry(client, acct1_loc1=-9999, comment="way too much")

    assert "ERROR:(Spending) Number must be between -1000 and 1000." in \
        flash_messages(response)
    assert len(f.ledger_for(kid)) == 1


def test_comment_is_required_unless_no_comment_is_ticked(world):
    _, kid, client = world
    # A browser always submits the textarea, so an empty comment arrives as "".
    response = client.post(KID_URL, data={"acct1_loc1": "1", "comment": ""},
                           follow_redirects=True)
    assert any("need to select 'no comment'" in m
               for m in flash_messages(response))
    assert f.ledger_for(kid) == []

    client.post(KID_URL,
                data={"acct1_loc1": "1", "comment": "", "no_comment": "y"},
                follow_redirects=True)
    assert len(f.ledger_for(kid)) == 1


def test_deactivated_bucket_is_drain_only(world):
    _, kid, client = world
    # Fund account 3 while it is still active, then deactivate it.
    kid.acct3_name = "Old Jar"
    kid.acct3_used = True
    f.db.session.commit()
    post_entry(client, acct3_loc1=6, comment="fund old jar")
    kid.acct3_used = False
    f.db.session.commit()

    blocked = post_entry(client, acct3_loc1=2, comment="deposit")
    assert ("ERROR: 'Old Jar' is a deactivated account, you can only take "
            "money out until the account is empty") in flash_messages(blocked)
    rows_before = len(f.ledger_for(kid))

    post_entry(client, acct3_loc1=-2, comment="drain")
    assert len(f.ledger_for(kid)) == rows_before + 1
    assert f.ledger_for(kid)[-1].total_acc3 == 4


def test_child_may_subtract_but_not_add(world):
    _, kid, client = world
    post_entry(client, acct1_loc1=10, comment="seed")
    login_child(client)

    blocked = post_entry(client, acct1_loc1=5, comment="kid adds")
    assert "ERROR: Only Parent can add money, kids can subtract" in \
        flash_messages(blocked)
    assert len(f.ledger_for(kid)) == 1

    post_entry(client, acct1_loc1=-2, comment="kid spends")
    rows = f.ledger_for(kid)
    assert len(rows) == 2
    assert account_totals(rows[-1]) == [8, 0, 0, 0, 0]
    # Child entries are attributed to the child and flagged as not-parent.
    assert rows[-1].adjuster_name == "whipper"
    assert rows[-1].adjusted_by_parent is False
    assert_book_balances(kid.id)


# ---------------------------------------------------------------------------
# Known bugs.
# ---------------------------------------------------------------------------

def test_KNOWN_BUG_pure_transfer_between_buckets_is_rejected(world):
    """The no-op guard tests the *grand sum* of the grid, not whether anything
    moved.  So moving $4 from one sub-account to another -- a completely normal
    thing to want to do -- nets to zero and is refused.
    """
    _, kid, client = world
    post_entry(client, acct1_loc1=10, comment="seed")

    response = post_entry(client, acct1_loc1=-4, acct2_loc2=4,
                          comment="move to savings")

    assert "No account changes to update" in flash_messages(response)
    assert len(f.ledger_for(kid)) == 1, (
        "Expected the transfer to be rejected. If a row was written, the "
        "grand-sum guard has been fixed -- invert this test.")


def test_KNOWN_BUG_deposit_into_unnamed_inactive_bucket_crashes(world):
    """``a_finance.py:381`` builds its rejection message with
    ``"'" + getattr(kid, "acct%s_name" % i)``.

    Inactive buckets have a NULL name, so the very message meant to reject the
    deposit raises ``TypeError: can only concatenate str (not "NoneType")`` --
    an unhandled 500 instead of a flash.
    """
    _, kid, client = world
    assert kid.acct3_name is None and kid.acct3_used is False

    with pytest.raises(TypeError, match="can only concatenate str"):
        post_entry(client, acct3_loc1=5, comment="deposit into unnamed bucket")


def test_KNOWN_BUG_no_comment_is_ignored_when_comment_field_is_absent(world):
    """``a_finance.py:347`` reads::

        if form.comment.data is None or form.comment.data == "" and \
                form.no_comment.data is not True:

    ``and`` binds tighter than ``or``, so this is
    ``(data is None) or (data == "" and not no_comment)``.  When the
    ``comment`` field is missing from the payload entirely its data is
    ``None``, the first clause short-circuits, and the ``no_comment`` opt-out
    is ignored.

    A browser always submits the textarea, so this is invisible today -- but
    any JSON client that simply omits the field hits it, which makes it a
    trap for the upcoming API.
    """
    _, kid, client = world
    response = client.post(KID_URL,
                           data={"acct1_loc1": "1", "no_comment": "y"},
                           follow_redirects=True)

    assert any("need to select 'no comment'" in m
               for m in flash_messages(response)), (
        "Expected no_comment to be ignored when the field is absent. If this "
        "now succeeds, the precedence bug is fixed -- invert this test.")
    assert f.ledger_for(kid) == []
