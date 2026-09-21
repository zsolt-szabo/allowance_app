"""Object factories for tests.

Ports the fixture shapes from ``unit/local_data.py`` into callables so tests
can build exactly the scenario they need instead of sharing mutable state.
"""
from datetime import datetime, timedelta, timezone

from app import db
from app import models


def make_parent(email="parent@example.com", firstname="Parent",
                password="monstertruck", money_symbol="$"):
    user = models.User(firstname=firstname, email=email,
                       money_symbol=money_symbol)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def make_kid(parent, firstname="whipper", animal1="rabbit", animal2="rabbit",
             animal3="goose", animal4="goose", pw="snapper",
             accounts=("Spending", "Savings"),
             locations=("Mom/Dad's wallet", "Gift Card From Grandma")):
    """Create a Kid. ``accounts``/``locations`` name the *active* buckets, in
    slot order; remaining slots are left inactive."""
    kwargs = dict(firstname=firstname, parent_id=parent.id, pw=pw,
                  animal1=animal1, animal2=animal2,
                  animal3=animal3, animal4=animal4)
    for i in range(1, 6):
        active = i <= len(accounts)
        kwargs["acct%s_name" % i] = accounts[i - 1] if active else None
        kwargs["acct%s_used" % i] = active
    for j in range(1, 8):
        active = j <= len(locations)
        kwargs["location%s_name" % j] = locations[j - 1] if active else None
        kwargs["location%s_used" % j] = active
    kid = models.Kid(**kwargs)
    db.session.add(kid)
    db.session.commit()
    return kid


def make_allowance(kid, amount=3.0, nickname="allowance", payout_days=(1,),
                   account_percs=(100, 0, 0, 0, 0),
                   location_percs=(100, 0, 0, 0, 0, 0, 0),
                   last_ledger_update=None):
    """Create an Allowance plus its AllowanceDays rows.

    ``last_ledger_update`` overrides the watermark that ``Allowance.__init__``
    backdates by one day -- payout tests need to control it precisely.
    """
    allowance = models.Allowance(
        kid_id=kid.id, amount=amount, nickname=nickname,
        **{"account%s_perc" % i: account_percs[i - 1] for i in range(1, 6)},
        **{"location%s_perc" % j: location_percs[j - 1] for j in range(1, 8)})
    db.session.add(allowance)
    db.session.commit()

    if last_ledger_update is not None:
        allowance.last_ledger_update = last_ledger_update
        db.session.commit()

    for day in payout_days:
        db.session.add(models.AllowanceDays(payout_day=day,
                                            allowance_id=allowance.id))
    db.session.commit()
    return allowance


def days_ago(n):
    """A naive UTC datetime ``n`` days in the past, matching how the payout
    engine stores its watermark (``datetime.combine(date, min.time())``)."""
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day) - timedelta(days=n)


def allowance_rows():
    """The (Allowance, AllowanceDays) tuple list the payout engine expects --
    exactly the query ``allowance_payout_cron.py`` runs."""
    return db.session.query(models.Allowance, models.AllowanceDays).filter(
        models.Allowance.id == models.AllowanceDays.allowance_id).all()


def ledger_for(kid):
    return models.Ledger.query.filter(
        models.Ledger.kid_id == kid.id).order_by(models.Ledger.id).all()
