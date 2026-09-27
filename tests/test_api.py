"""Tests for the JSON API.

The API must enforce exactly the rules the Jinja screens enforce, because
during the transition both are live against the same database. The
authorization section is the important one: an SPA makes ownership
mistakes cheap to introduce and expensive to notice.
"""
import pytest

from app import models
from tests import factories as f

PW = "monstertruck"


@pytest.fixture
def world(db_, client):
    """Two families. Alice has one kid with money; Bob has one kid."""
    alice = f.make_parent(email="alice@example.com", password=PW)
    bob = f.make_parent(email="bob@example.com", password=PW)
    amy = f.make_kid(alice, firstname="amy",
                     animal1="rabbit", animal2="rabbit")
    ben = f.make_kid(bob, firstname="ben",
                     animal1="tiger", animal2="tiger")
    return {"alice": alice, "bob": bob, "amy": amy, "ben": ben,
            "client": client}


def login_parent(client, email):
    return client.post("/api/auth/parent/login",
                       json={"email": email, "password": PW})


def login_child(client, kid):
    return client.post("/api/auth/child/login",
                       json={"firstname": kid.firstname,
                             "animal1": kid.animal1,
                             "animal2": kid.animal2,
                             "password": kid.pw,
                             "animal3": kid.animal3,
                             "animal4": kid.animal4})


def add_money(client, kid_id, account, location, amount, comment="seed"):
    return client.post(
        "/api/kids/%s/ledger/entries" % kid_id,
        json={"cells": [{"account": account, "location": location,
                         "amount": amount}], "comment": comment})


# --- session --------------------------------------------------------------

def test_session_is_200_when_anonymous(world):
    """Not an error: the landing page needs to know, not to fail."""
    response = world["client"].get("/api/auth/session")
    assert response.status_code == 200
    assert response.get_json() == {"authenticated": False, "actor": None}


def test_parent_login_and_session(world):
    client = world["client"]
    assert login_parent(client, "alice@example.com").status_code == 200

    body = client.get("/api/auth/session").get_json()
    assert body["authenticated"] is True
    assert body["actor"]["kind"] == "parent"
    assert body["actor"]["id"] == world["alice"].id


def test_child_login_and_session(world):
    client = world["client"]
    assert login_child(client, world["amy"]).status_code == 200

    body = client.get("/api/auth/session").get_json()
    assert body["actor"]["kind"] == "child"
    assert body["actor"]["id"] == world["amy"].id


def test_bad_password_is_401_with_an_envelope(world):
    response = world["client"].post("/api/auth/parent/login",
                                    json={"email": "alice@example.com",
                                          "password": "wrong"})
    assert response.status_code == 401
    error = response.get_json()["error"]
    assert error["code"] == "auth.bad_login"
    assert error["message"] == "User/Password combination not found"


def test_logout_clears_the_session(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/session").get_json()["authenticated"] is False


def test_csrf_endpoint_returns_a_token(world):
    body = world["client"].get("/api/csrf").get_json()
    assert isinstance(body["token"], str) and body["token"]


# --- dashboard ------------------------------------------------------------

def test_dashboard_requires_a_session(world):
    response = world["client"].get("/api/dashboard")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthenticated"


def test_parent_dashboard_lists_only_their_kids(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    body = client.get("/api/dashboard").get_json()

    assert [k["firstname"] for k in body["kids"]] == ["amy"]
    assert body["actor"]["kind"] == "parent"


def test_child_dashboard_shows_only_themselves(world):
    client = world["client"]
    login_child(client, world["amy"])
    body = client.get("/api/dashboard").get_json()
    assert [k["firstname"] for k in body["kids"]] == ["amy"]


def test_dashboard_totals_reflect_the_ledger(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    add_money(client, world["amy"].id, 1, 1, 12.50)

    body = client.get("/api/dashboard").get_json()
    assert body["totalOwed"] == 12.50
    assert body["kids"][0]["balance"] == 12.50


# --- kids -----------------------------------------------------------------

def test_kid_detail_uses_indexed_bucket_arrays(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    body = client.get("/api/kids/%s" % world["amy"].id).get_json()

    assert [b["index"] for b in body["accounts"]] == [1, 2, 3, 4, 5]
    assert [b["index"] for b in body["locations"]] == [1, 2, 3, 4, 5, 6, 7]
    assert body["accounts"][0]["name"] == "Spending"
    assert body["accounts"][0]["active"] is True
    assert body["accounts"][2]["active"] is False


def test_password_is_withheld_unless_asked_for(world):
    client = world["client"]
    login_parent(client, "alice@example.com")

    plain = client.get("/api/kids/%s" % world["amy"].id).get_json()
    assert "password" not in plain

    asked = client.get("/api/kids/%s?includePassword=true"
                       % world["amy"].id).get_json()
    assert asked["password"] == world["amy"].pw


def test_a_child_cannot_ask_for_the_password_field(world):
    """Only the owning parent may read it back."""
    client = world["client"]
    login_child(client, world["amy"])
    body = client.get("/api/kids/%s?includePassword=true"
                      % world["amy"].id).get_json()
    assert "password" not in body


def test_animals_endpoint_lists_the_credential_alphabet(world):
    body = world["client"].get("/api/animals").get_json()
    keys = [a["key"] for a in body["animals"]]
    assert "tiger" in keys and "rabbit" in keys
    assert all(a["imageUrl"].startswith("/static/") for a in body["animals"])


# --- allowances -----------------------------------------------------------

def test_create_and_list_an_allowance(world):
    client = world["client"]
    login_parent(client, "alice@example.com")

    created = client.post(
        "/api/kids/%s/allowances" % world["amy"].id,
        json={"amount": 5.0, "nickname": "Weekly", "payoutDays": [1, 15],
              "accountPercents": [80, 20, 0, 0, 0],
              "locationPercents": [100, 0, 0, 0, 0, 0, 0]})
    assert created.status_code == 201
    body = created.get_json()
    assert body["nickname"] == "Weekly"
    assert body["payoutDays"] == [1, 15]
    assert body["accountPercents"] == [80, 20, 0, 0, 0]

    listed = client.get("/api/kids/%s/allowances"
                        % world["amy"].id).get_json()
    assert len(listed["allowances"]) == 1


def test_percentages_must_total_one_hundred(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    response = client.post(
        "/api/kids/%s/allowances" % world["amy"].id,
        json={"amount": 5.0, "payoutDays": [1],
              "accountPercents": [50, 0, 0, 0, 0],
              "locationPercents": [100, 0, 0, 0, 0, 0, 0]})
    assert response.status_code == 422


def test_a_child_cannot_create_an_allowance(world):
    client = world["client"]
    login_child(client, world["amy"])
    response = client.post(
        "/api/kids/%s/allowances" % world["amy"].id,
        json={"amount": 5.0, "payoutDays": [1],
              "accountPercents": [100, 0, 0, 0, 0],
              "locationPercents": [100, 0, 0, 0, 0, 0, 0]})
    assert response.status_code == 403


def test_delete_an_allowance(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    created = client.post(
        "/api/kids/%s/allowances" % world["amy"].id,
        json={"amount": 5.0, "payoutDays": [1],
              "accountPercents": [100, 0, 0, 0, 0],
              "locationPercents": [100, 0, 0, 0, 0, 0, 0]}).get_json()

    assert client.delete("/api/allowances/%s"
                         % created["id"]).status_code == 200
    assert models.Allowance.query.count() == 0
    assert models.AllowanceDays.query.count() == 0


# --- ledger ---------------------------------------------------------------

def test_post_a_ledger_entry_and_read_it_back(world):
    client = world["client"]
    login_parent(client, "alice@example.com")

    created = add_money(client, world["amy"].id, 1, 1, 10.0, "birthday")
    assert created.status_code == 201
    entry = created.get_json()
    assert entry["accountChanges"] == [10, 0, 0, 0, 0]
    assert entry["accountTotals"] == [10, 0, 0, 0, 0]
    assert entry["locationTotals"] == [10, 0, 0, 0, 0, 0, 0]
    assert entry["adjustedByParent"] is True

    page = client.get("/api/kids/%s/ledger" % world["amy"].id).get_json()
    assert page["grandTotal"] == 10
    assert len(page["entries"]) == 1
    assert page["visibleAccounts"] == [1, 2]
    assert page["visibleLocations"] == [1, 2]


def test_a_multi_cell_entry_folds_into_both_axes(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    response = client.post(
        "/api/kids/%s/ledger/entries" % world["amy"].id,
        json={"cells": [{"account": 1, "location": 1, "amount": 6},
                        {"account": 2, "location": 2, "amount": 4}],
              "comment": "split"})
    entry = response.get_json()
    assert entry["accountTotals"] == [6, 4, 0, 0, 0]
    assert entry["locationTotals"] == [6, 4, 0, 0, 0, 0, 0]
    assert sum(entry["accountTotals"]) == sum(entry["locationTotals"])


def test_a_child_may_subtract_but_not_add(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    add_money(client, world["amy"].id, 1, 1, 10.0)
    client.post("/api/auth/logout")
    login_child(client, world["amy"])

    blocked = add_money(client, world["amy"].id, 1, 1, 5.0, "kid adds")
    assert blocked.status_code == 403
    assert blocked.get_json()["error"]["code"] == "ledger.child_cannot_add"

    allowed = add_money(client, world["amy"].id, 1, 1, -2.0, "kid spends")
    assert allowed.status_code == 201
    assert allowed.get_json()["accountTotals"] == [8, 0, 0, 0, 0]
    assert allowed.get_json()["adjustedByParent"] is False


def test_overdrawing_is_refused(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    add_money(client, world["amy"].id, 1, 1, 10.0)

    response = add_money(client, world["amy"].id, 1, 1, -50.0, "too much")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ledger.location_overdrawn"


def test_a_cell_outside_the_grid_is_rejected(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    response = client.post(
        "/api/kids/%s/ledger/entries" % world["amy"].id,
        json={"cells": [{"account": 9, "location": 1, "amount": 5}],
              "comment": "nope"})
    assert response.status_code == 422


def test_a_comment_is_required_unless_opted_out(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    kid_id = world["amy"].id

    missing = client.post("/api/kids/%s/ledger/entries" % kid_id,
                          json={"cells": [{"account": 1, "location": 1,
                                           "amount": 5}]})
    assert missing.status_code == 422

    opted_out = client.post("/api/kids/%s/ledger/entries" % kid_id,
                            json={"cells": [{"account": 1, "location": 1,
                                             "amount": 5}],
                                  "noComment": True})
    assert opted_out.status_code == 201


# --- authorization --------------------------------------------------------

def test_a_parent_cannot_read_another_familys_kid(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    response = client.get("/api/kids/%s" % world["ben"].id)
    assert response.status_code == 404


def test_a_parent_cannot_read_another_familys_ledger(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    assert client.get("/api/kids/%s/ledger"
                      % world["ben"].id).status_code == 404


def test_a_parent_cannot_post_money_to_another_familys_kid(world):
    client = world["client"]
    login_parent(client, "alice@example.com")
    response = add_money(client, world["ben"].id, 1, 1, 100.0, "theft")
    assert response.status_code == 404
    assert models.Ledger.query.count() == 0


def test_a_parent_cannot_delete_another_familys_allowance(world):
    client = world["client"]
    login_parent(client, "bob@example.com")
    created = client.post(
        "/api/kids/%s/allowances" % world["ben"].id,
        json={"amount": 5.0, "payoutDays": [1],
              "accountPercents": [100, 0, 0, 0, 0],
              "locationPercents": [100, 0, 0, 0, 0, 0, 0]}).get_json()
    client.post("/api/auth/logout")

    login_parent(client, "alice@example.com")
    assert client.delete("/api/allowances/%s"
                         % created["id"]).status_code == 404
    assert models.Allowance.query.count() == 1


def test_a_child_cannot_read_another_kid(world):
    client = world["client"]
    login_child(client, world["amy"])
    assert client.get("/api/kids/%s" % world["ben"].id).status_code == 404


def test_another_familys_kid_looks_exactly_like_a_missing_one(world):
    """Probing ids must not confirm that another family's kid exists."""
    client = world["client"]
    login_parent(client, "alice@example.com")
    other = client.get("/api/kids/%s" % world["ben"].id)
    absent = client.get("/api/kids/999999")
    assert other.status_code == absent.status_code == 404
    assert other.get_json() == absent.get_json()


# --- shape ----------------------------------------------------------------

def test_unknown_api_path_returns_json_not_html(world):
    response = world["client"].get("/api/nope")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_unknown_non_api_path_still_returns_html(world):
    """The Jinja side must keep its normal error pages."""
    response = world["client"].get("/definitely-not-here")
    assert response.status_code == 404
    assert response.get_json(silent=True) is None


def test_payout_trigger_is_refused_without_the_shared_secret(world):
    assert world["client"].post("/api/payouts/run").status_code == 403


# --- payout parity --------------------------------------------------------

def test_dashboard_pays_due_allowances_like_the_jinja_index(world):
    """The Jinja index runs the payout sweep on every page load. If the
    JSON dashboard did not, a family that only ever used the SPA would
    quietly stop being paid."""
    import datetime
    import time_machine

    client = world["client"]
    frozen = datetime.datetime(2026, 3, 15, 12, 0,
                               tzinfo=datetime.timezone.utc)
    with time_machine.travel(frozen, tick=False):
        f.make_allowance(world["amy"], amount=4.0, payout_days=(15,),
                         account_percs=(100, 0, 0, 0, 0),
                         location_percs=(100, 0, 0, 0, 0, 0, 0),
                         last_ledger_update=f.days_ago(1))
        login_parent(client, "alice@example.com")

        assert models.Ledger.query.count() == 0
        body = client.get("/api/dashboard").get_json()

        assert models.Ledger.query.count() == 1, "the payout did not run"
        assert body["totalOwed"] == 4.0


def test_dashboard_payout_can_be_switched_off(world, flask_obj):
    """The flag is how payouts become cron-only once cron is proven."""
    import datetime
    import time_machine

    client = world["client"]
    frozen = datetime.datetime(2026, 3, 15, 12, 0,
                               tzinfo=datetime.timezone.utc)
    flask_obj.config["PAYOUT_ON_DASHBOARD_READ"] = False
    try:
        with time_machine.travel(frozen, tick=False):
            f.make_allowance(world["amy"], amount=4.0, payout_days=(15,),
                             account_percs=(100, 0, 0, 0, 0),
                             location_percs=(100, 0, 0, 0, 0, 0, 0),
                             last_ledger_update=f.days_ago(1))
            login_parent(client, "alice@example.com")
            client.get("/api/dashboard")
            assert models.Ledger.query.count() == 0
    finally:
        flask_obj.config["PAYOUT_ON_DASHBOARD_READ"] = True


def test_dashboard_payout_only_touches_the_requesting_family(world):
    """due_rows_for_kid narrows the sweep; a parent opening their
    dashboard must not run another family's payouts."""
    import datetime
    import time_machine

    client = world["client"]
    frozen = datetime.datetime(2026, 3, 15, 12, 0,
                               tzinfo=datetime.timezone.utc)
    with time_machine.travel(frozen, tick=False):
        f.make_allowance(world["ben"], amount=9.0, payout_days=(15,),
                         account_percs=(100, 0, 0, 0, 0),
                         location_percs=(100, 0, 0, 0, 0, 0, 0),
                         last_ledger_update=f.days_ago(1))
        login_parent(client, "alice@example.com")
        client.get("/api/dashboard")

        assert models.Ledger.query.filter_by(
            kid_id=world["ben"].id).count() == 0
