"""Characterization tests for allowance percentage redistribution.

When a parent deactivates a sub-account or money location that an existing
allowance still pays into, ``app/lib/a_child_login.py:139-174`` redistributes
that bucket's percentage across the buckets still active and non-zero.

The algorithm gives every surviving bucket after the first an even
``round(diff / n, 2)`` share and makes the *first* one absorb whatever is left
(``diff - amount_added``).  That absorber is load-bearing: the DB
``CheckConstraint`` ``acc_100`` requires the percentages to sum to exactly 100,
so an even split that rounded to 99.99 would be rejected outright.
"""
import re

import pytest

from app import db, models
from tests import factories as f

PARENT_EMAIL = "parent@example.com"
PARENT_PW = "monstertruck"


def kid_form(kid, **overrides):
    """Build the full RegisterChild1 payload for /kid_manage from a Kid row."""
    data = {"firstname": kid.firstname, "password": kid.pw,
            "animal1": kid.animal1, "animal2": kid.animal2,
            "animal3": kid.animal3, "animal4": kid.animal4,
            "initial_animal1": kid.animal1, "initial_animal2": kid.animal2}
    for i in range(1, 6):
        data["acct%s_name" % i] = getattr(kid, "acct%s_name" % i) or ""
        data["acct%s_comment" % i] = getattr(kid, "acct%s_comment" % i) or ""
        if getattr(kid, "acct%s_used" % i):
            data["acct%s_used" % i] = "y"
    for j in range(1, 8):
        data["location%s_name" % j] = getattr(kid, "location%s_name" % j) or ""
        data["location%s_comment" % j] = \
            getattr(kid, "location%s_comment" % j) or ""
        if getattr(kid, "location%s_used" % j):
            data["location%s_used" % j] = "y"
    data.update(overrides)
    return data


def flash_messages(response):
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


def account_percents(allowance):
    return [getattr(allowance, "account%s_perc" % i) or 0 for i in range(1, 6)]


def location_percents(allowance):
    return [getattr(allowance, "location%s_perc" % j) or 0
            for j in range(1, 8)]


@pytest.fixture
def parent_client(db_, client):
    f.make_parent(email=PARENT_EMAIL, password=PARENT_PW)
    client.post("/login", data={"email": PARENT_EMAIL, "password": PARENT_PW},
                follow_redirects=True)
    return client


def deactivate_account(client, kid, slot):
    data = kid_form(kid)
    data.pop("acct%s_used" % slot, None)
    response = client.post("/kid_manage", data=data, follow_redirects=True)
    db.session.expire_all()
    return response


def deactivate_location(client, kid, slot):
    data = kid_form(kid)
    data.pop("location%s_used" % slot, None)
    response = client.post("/kid_manage", data=data, follow_redirects=True)
    db.session.expire_all()
    return response


def test_closed_account_percentage_is_split_evenly(parent_client, db_):
    parent = models.User.query.first()
    kid = f.make_kid(parent, accounts=("Spending", "Savings", "Charity"),
                     locations=("Wallet", "Piggy"))
    allowance = f.make_allowance(kid, amount=9.0, payout_days=(1,),
                                 account_percs=(50, 25, 25, 0, 0),
                                 location_percs=(100, 0, 0, 0, 0, 0, 0))

    response = deactivate_account(parent_client, kid, 2)
    assert "Child info updated" in flash_messages(response)

    updated = db.session.get(models.Allowance, allowance.id)
    # The closed 25% is shared evenly between the two survivors.
    assert account_percents(updated) == [62.5, 0.0, 37.5, 0.0, 0.0]
    assert sum(account_percents(updated)) == 100
    assert db.session.get(models.Kid, kid.id).acct2_used is False


def test_uneven_split_is_absorbed_by_the_first_survivor(parent_client, db_):
    """10% shared across three survivors is 3.33 each, leaving 0.01 that the
    first survivor absorbs so the total lands on exactly 100."""
    parent = models.User.query.first()
    kid = f.make_kid(parent,
                     accounts=("Alpha", "Beta", "Gamma", "Delta"),
                     locations=("Wallet",))
    allowance = f.make_allowance(kid, amount=9.0, payout_days=(1,),
                                 account_percs=(10, 30, 30, 30, 0),
                                 location_percs=(100, 0, 0, 0, 0, 0, 0))

    deactivate_account(parent_client, kid, 1)

    updated = db.session.get(models.Allowance, allowance.id)
    percents = account_percents(updated)
    assert percents == [0.0, 33.34, 33.33, 33.33, 0.0]
    # Exactly 100, not 99.99 -- the acc_100 CheckConstraint demands it.
    assert sum(percents) == 100


def test_locations_use_the_same_algorithm(parent_client, db_):
    parent = models.User.query.first()
    kid = f.make_kid(parent, accounts=("Spending",),
                     locations=("Wallet", "Piggy", "Bank"))
    allowance = f.make_allowance(kid, amount=9.0, payout_days=(1,),
                                 account_percs=(100, 0, 0, 0, 0),
                                 location_percs=(50, 25, 25, 0, 0, 0, 0))

    deactivate_location(parent_client, kid, 2)

    updated = db.session.get(models.Allowance, allowance.id)
    assert location_percents(updated) == [62.5, 0.0, 37.5, 0.0, 0.0, 0.0, 0.0]
    assert sum(location_percents(updated)) == 100


def test_zero_percentage_buckets_are_left_alone(parent_client, db_):
    """Buckets sitting at 0% are treated as deliberately ignored, so they are
    not brought back in as redistribution targets."""
    parent = models.User.query.first()
    kid = f.make_kid(parent, accounts=("Alpha", "Beta", "Gamma"),
                     locations=("Wallet",))
    allowance = f.make_allowance(kid, amount=9.0, payout_days=(1,),
                                 account_percs=(60, 40, 0, 0, 0),
                                 location_percs=(100, 0, 0, 0, 0, 0, 0))

    deactivate_account(parent_client, kid, 2)

    updated = db.session.get(models.Allowance, allowance.id)
    # All 40% goes to account 1; account 3 stays at zero.
    assert account_percents(updated) == [100.0, 0.0, 0.0, 0.0, 0.0]


def test_KNOWN_BUG_closing_the_only_funded_bucket_returns_500(parent_client,
                                                              db_):
    """Deactivating the only bucket an allowance pays into is a 500, not a
    helpful message.

    The code flashes "Could not fix allowance distribution..." and then falls
    through and runs the UPDATE anyway with every percentage set to 0.  That
    violates the ``acc_100`` CheckConstraint, the bare ``except`` catches the
    IntegrityError and renders ``child_account.html`` -- but without the
    ``used_by_allowance`` attribute the template requires, so Jinja raises and
    the parent gets an error page.
    """
    import jinja2

    parent = models.User.query.first()
    kid = f.make_kid(parent, accounts=("Spending", "Savings"),
                     locations=("Wallet",))
    f.make_allowance(kid, amount=9.0, payout_days=(1,),
                     account_percs=(100, 0, 0, 0, 0),
                     location_percs=(100, 0, 0, 0, 0, 0, 0))

    with pytest.raises(jinja2.exceptions.UndefinedError,
                       match="used_by_allowance"):
        deactivate_account(parent_client, kid, 1)
