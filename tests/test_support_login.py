"""Tests for the support-token login that replaced the master password."""
import datetime

import pytest
import time_machine

from app import db, models, support
from tests import factories as f

PARENT_EMAIL = "parent@example.com"
PARENT_PW = "monstertruck"
NOW = datetime.datetime(2026, 3, 15, 12, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture
def parent_account(db_):
    return f.make_parent(email=PARENT_EMAIL, password=PARENT_PW)


def test_valid_token_enters_the_named_account(parent_account, client):
    token = support.generate_support_token(parent_account.id, PARENT_EMAIL)

    response = client.get("/support?t=%s" % token, follow_redirects=True)
    page = response.data.decode()

    assert "Logout" in page, "should be signed in"
    # base.html renders this banner whenever session['TechSupport'] is set.
    assert "TECH SUPPORT" in page
    with client.session_transaction() as session:
        assert session["TechSupport"] is True


def test_token_expires(parent_account, client):
    with time_machine.travel(NOW, tick=False):
        token = support.generate_support_token(
            parent_account.id, PARENT_EMAIL, minutes=15)

    # 16 minutes later the token is stale.
    with time_machine.travel(NOW + datetime.timedelta(minutes=16), tick=False):
        response = client.get("/support?t=%s" % token, follow_redirects=True)

    assert "Support token has expired" in response.data.decode()
    with client.session_transaction() as session:
        assert "TechSupport" not in session


def test_token_is_still_valid_just_before_expiry(parent_account, client):
    with time_machine.travel(NOW, tick=False):
        token = support.generate_support_token(
            parent_account.id, PARENT_EMAIL, minutes=15)

    with time_machine.travel(NOW + datetime.timedelta(minutes=14), tick=False):
        response = client.get("/support?t=%s" % token, follow_redirects=True)

    assert "Logout" in response.data.decode()


def test_tampered_token_is_rejected(parent_account, client):
    token = support.generate_support_token(parent_account.id, PARENT_EMAIL)
    forged = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")

    response = client.get("/support?t=%s" % forged, follow_redirects=True)

    assert "Support token is not valid" in response.data.decode()


def test_missing_token_is_rejected(parent_account, client):
    response = client.get("/support", follow_redirects=True)
    assert "No support token supplied" in response.data.decode()


def test_token_for_a_deleted_account_is_rejected(parent_account, client):
    token = support.generate_support_token(parent_account.id, PARENT_EMAIL)
    db.session.delete(parent_account)
    db.session.commit()

    response = client.get("/support?t=%s" % token, follow_redirects=True)

    assert "does not match an existing account" in response.data.decode()


def test_token_is_rejected_if_the_address_was_reassigned(parent_account,
                                                         client):
    """The id alone is not enough: the email must still match."""
    token = support.generate_support_token(parent_account.id, PARENT_EMAIL)
    parent_account.email = "someone-else@example.com"
    db.session.commit()

    response = client.get("/support?t=%s" % token, follow_redirects=True)

    assert "does not match an existing account" in response.data.decode()


def test_ttl_is_capped(parent_account):
    """A caller cannot mint a token that outlives the hard ceiling."""
    token = support.generate_support_token(
        parent_account.id, PARENT_EMAIL, minutes=999999)
    payload = support.consume_support_token(token)
    assert payload["ttl"] == support.MAX_TTL_MINUTES


def test_the_old_master_password_no_longer_works(parent_account, client):
    """config.TECH_SUPPORT is gone; only the account's real password works."""
    import config
    assert not hasattr(config, "TECH_SUPPORT")

    response = client.post("/login",
                           data={"email": PARENT_EMAIL,
                                 "password": "<UPDATEME>"},
                           follow_redirects=True)

    assert "User/Password combination not found" in response.data.decode()
    assert models.User.query.count() == 1


def test_normal_password_login_still_works(parent_account, client):
    response = client.post("/login",
                           data={"email": PARENT_EMAIL,
                                 "password": PARENT_PW},
                           follow_redirects=True)
    page = response.data.decode()
    assert "Logout" in page
    assert "TECH SUPPORT" not in page
