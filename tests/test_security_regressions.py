"""Regression tests for fixed security defects.

Each test here corresponds to a hole that was demonstrated to be real before
it was closed. They exist so a later refactor cannot quietly reopen one.
"""
from app import db, models
from tests import factories as f

PARENT_EMAIL = "parent@example.com"
PARENT_PW = "monstertruck"

# A nickname that breaks out of a double-quoted Python string literal and
# runs code. Harmless payload: it appends to a module-level list we can then
# inspect.
INJECTION_NICKNAME = (
    'x"; __import__("app").lib.a_child_login.INJECTION_CANARY.append(1); y = "'
)


def test_allowance_nickname_cannot_execute_code(db_, client):
    """The used_by_allowance table on /kid_manage used to be built by
    exec()ing generated source with the nickname pasted into a string
    literal, so a nickname containing a double quote ran as code.
    """
    from app.lib import a_child_login
    a_child_login.INJECTION_CANARY = []

    parent = f.make_parent(email=PARENT_EMAIL, password=PARENT_PW)
    kid = f.make_kid(parent)
    f.make_allowance(kid, amount=5.0, payout_days=(1,),
                     nickname=INJECTION_NICKNAME,
                     account_percs=(100, 0, 0, 0, 0),
                     location_percs=(100, 0, 0, 0, 0, 0, 0))
    client.post("/login", data={"email": PARENT_EMAIL, "password": PARENT_PW},
                follow_redirects=True)

    response = client.get("/kid_manage?kid=whipper:rabbit:rabbit",
                          follow_redirects=True)

    assert response.status_code == 200
    assert a_child_login.INJECTION_CANARY == [], \
        "allowance nickname executed as code"


def test_nickname_with_a_quote_renders_instead_of_crashing(db_, client):
    """Even the benign case was broken: any double quote was a SyntaxError."""
    parent = f.make_parent(email=PARENT_EMAIL, password=PARENT_PW)
    kid = f.make_kid(parent)
    f.make_allowance(kid, amount=5.0, payout_days=(1,),
                     nickname='Say "hi" allowance',
                     account_percs=(100, 0, 0, 0, 0),
                     location_percs=(100, 0, 0, 0, 0, 0, 0))
    client.post("/login", data={"email": PARENT_EMAIL, "password": PARENT_PW},
                follow_redirects=True)

    response = client.get("/kid_manage?kid=whipper:rabbit:rabbit",
                          follow_redirects=True)

    assert response.status_code == 200
    # Rendered, and escaped by Jinja rather than injected.
    assert "Say &#34;hi&#34; allowance" in response.data.decode() or \
           "Say &quot;hi&quot; allowance" in response.data.decode()


def test_used_by_allowance_still_marks_the_right_buckets(db_, client):
    """The replacement must preserve what the column actually reports:
    which allowances pay into which bucket."""
    parent = f.make_parent(email=PARENT_EMAIL, password=PARENT_PW)
    kid = f.make_kid(parent, accounts=("Spending", "Savings"),
                     locations=("Wallet", "Piggy"))
    f.make_allowance(kid, amount=5.0, payout_days=(1,), nickname="Weekly",
                     account_percs=(60, 40, 0, 0, 0),
                     location_percs=(100, 0, 0, 0, 0, 0, 0))
    client.post("/login", data={"email": PARENT_EMAIL, "password": PARENT_PW},
                follow_redirects=True)

    page = client.get("/kid_manage?kid=whipper:rabbit:rabbit",
                      follow_redirects=True).data.decode()

    # Weekly funds accounts 1 and 2 and location 1, so it is named against
    # those rows; it does not fund location 2.
    assert page.count("Weekly") >= 3


def test_support_token_cannot_be_forged(db_, client):
    """Covered in detail in test_support_login.py; kept here as the
    single place that lists closed holes."""
    from app import support
    parent = f.make_parent(email=PARENT_EMAIL, password=PARENT_PW)
    token = support.generate_support_token(parent.id, PARENT_EMAIL)
    forged = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")

    response = client.get("/support?t=%s" % forged, follow_redirects=True)

    assert "Support token is not valid" in response.data.decode()
    with client.session_transaction() as session:
        assert "TechSupport" not in session


def test_no_master_password_exists(db_):
    """TECH_SUPPORT was a standing credential for every parent account."""
    import config
    assert not hasattr(config, "TECH_SUPPORT")
    assert models.User.query.count() == 0 or True  # touch db_ fixture
    db.session.rollback()
