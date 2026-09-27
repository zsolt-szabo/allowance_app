"""Tests for the account and child-management endpoints."""
import pytest

from app import models
from tests import factories as f

PW = "monstertruck"


@pytest.fixture
def world(db_, client):
    alice = f.make_parent(email="alice@example.com", password=PW)
    bob = f.make_parent(email="bob@example.com", password=PW)
    amy = f.make_kid(alice, firstname="amy",
                     animal1="rabbit", animal2="rabbit")
    ben = f.make_kid(bob, firstname="ben",
                     animal1="tiger", animal2="tiger")
    return {"alice": alice, "bob": bob, "amy": amy, "ben": ben,
            "client": client}


def login(client, email="alice@example.com"):
    return client.post("/api/auth/parent/login",
                       json={"email": email, "password": PW})


def buckets(active_accounts=1, active_locations=1):
    accounts = [{"index": i, "name": "Acct%s" % i,
                 "active": i <= active_accounts, "comment": None}
                for i in range(1, 6)]
    locations = [{"index": j, "name": "Loc%s" % j,
                  "active": j <= active_locations, "comment": None}
                 for j in range(1, 8)]
    return accounts, locations


# --- captcha and registration ---------------------------------------------

def test_captcha_returns_image_urls_not_the_answer(world):
    body = world["client"].get("/api/auth/captcha").get_json()
    assert body["operation"]
    assert all(u.startswith("/static/") for u in body["firstDigits"])
    assert "solution" not in body and "answer" not in body


def test_register_requires_the_captcha_answer(world):
    client = world["client"]
    client.get("/api/auth/captcha")
    response = client.post("/api/parents",
                           json={"email": "new@example.com",
                                 "firstname": "New", "password": "pw123456",
                                 "captcha": "definitely-wrong"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "parent.bad_captcha"
    assert models.User.query.filter_by(email="new@example.com").count() == 0


def test_register_succeeds_and_signs_in(world):
    client = world["client"]
    client.get("/api/auth/captcha")
    with client.session_transaction() as session:
        answer = session["cap_solution"]

    response = client.post("/api/parents",
                           json={"email": "new@example.com",
                                 "firstname": "New", "password": "pw123456",
                                 "captcha": str(answer).replace(" ", "")})
    assert response.status_code == 201
    assert response.get_json()["email"] == "new@example.com"
    assert client.get("/api/auth/session").get_json()["authenticated"]


def test_register_rejects_a_duplicate_email(world):
    client = world["client"]
    client.get("/api/auth/captcha")
    with client.session_transaction() as session:
        answer = session["cap_solution"]
    response = client.post("/api/parents",
                           json={"email": "alice@example.com",
                                 "firstname": "Imposter",
                                 "password": "pw123456",
                                 "captcha": str(answer).replace(" ", "")})
    assert response.status_code == 409


# --- own account -----------------------------------------------------------

def test_get_me(world):
    client = world["client"]
    login(client)
    body = client.get("/api/me").get_json()
    assert body["email"] == "alice@example.com"
    assert body["isGoogle"] is False


def test_update_my_profile(world):
    client = world["client"]
    login(client)
    body = client.patch("/api/me",
                        json={"firstname": "Alicia",
                              "moneySymbol": "£"}).get_json()
    assert body["firstname"] == "Alicia"
    assert body["moneySymbol"] == "£"


def test_password_change_requires_the_old_one(world):
    client = world["client"]
    login(client)
    refused = client.patch("/api/me", json={"newPassword": "brand-new",
                                            "oldPassword": "wrong"})
    assert refused.status_code == 401

    ok = client.patch("/api/me", json={"newPassword": "brand-new",
                                       "oldPassword": PW})
    assert ok.status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/parent/login",
                       json={"email": "alice@example.com",
                             "password": "brand-new"}).status_code == 200


def test_delete_me_requires_confirmation(world):
    client = world["client"]
    login(client)
    refused = client.delete("/api/me")
    assert refused.status_code == 400
    assert models.User.query.count() == 2

    ok = client.delete("/api/me?confirm=true")
    assert ok.status_code == 200
    assert models.User.query.filter_by(email="alice@example.com").count() == 0
    #  and the child records went with it
    assert models.Kid.query.filter_by(firstname="amy").count() == 0
    #  but the other family is untouched
    assert models.Kid.query.filter_by(firstname="ben").count() == 1


# --- children --------------------------------------------------------------

def test_create_a_kid(world):
    client = world["client"]
    login(client)
    accounts, locations = buckets(active_accounts=2, active_locations=2)
    response = client.post("/api/kids",
                           json={"firstname": "cleo",
                                 "password": "snapper",
                                 "loginAnimals": ["goose", "duck"],
                                 "passwordAnimals": ["shark", "fish"],
                                 "accounts": accounts,
                                 "locations": locations})
    assert response.status_code == 201
    body = response.get_json()
    assert body["firstname"] == "cleo"
    assert body["loginAnimals"] == ["goose", "duck"]
    assert [b["active"] for b in body["accounts"]] == [True, True,
                                                       False, False, False]


def test_a_duplicate_login_triple_is_refused(world):
    """The identifying triple is unique across the whole system."""
    client = world["client"]
    login(client)
    accounts, locations = buckets()
    response = client.post("/api/kids",
                           json={"firstname": "ben",
                                 "password": "snapper",
                                 "loginAnimals": ["tiger", "tiger"],
                                 "passwordAnimals": ["goose", "goose"],
                                 "accounts": accounts,
                                 "locations": locations})
    assert response.status_code == 409


def test_a_kid_needs_at_least_one_active_bucket(world):
    """Mirrors the at_least_one_acc CheckConstraint."""
    client = world["client"]
    login(client)
    accounts, locations = buckets(active_accounts=0, active_locations=1)
    response = client.post("/api/kids",
                           json={"firstname": "nobody",
                                 "password": "snapper",
                                 "loginAnimals": ["goose", "duck"],
                                 "passwordAnimals": ["shark", "fish"],
                                 "accounts": accounts,
                                 "locations": locations})
    assert response.status_code == 422


def test_a_child_cannot_create_a_kid(world):
    client = world["client"]
    client.post("/api/auth/child/login",
                json={"firstname": "amy", "animal1": "rabbit",
                      "animal2": "rabbit", "password": world["amy"].pw,
                      "animal3": "goose", "animal4": "goose"})
    accounts, locations = buckets()
    response = client.post("/api/kids",
                           json={"firstname": "sneaky",
                                 "password": "snapper",
                                 "loginAnimals": ["goose", "duck"],
                                 "passwordAnimals": ["shark", "fish"],
                                 "accounts": accounts,
                                 "locations": locations})
    assert response.status_code == 403


def test_update_a_kids_name(world):
    client = world["client"]
    login(client)
    body = client.patch("/api/kids/%s" % world["amy"].id,
                        json={"firstname": "amelia"}).get_json()
    assert body["kid"]["firstname"] == "amelia"
    assert body["orphanedAllowances"] == []


def test_switching_a_bucket_off_redistributes_the_allowance(world):
    """The same rule the Jinja settings screen applies."""
    client = world["client"]
    login(client)
    kid = world["amy"]
    f.make_allowance(kid, amount=9.0, payout_days=(1,),
                     account_percs=(50, 50, 0, 0, 0),
                     location_percs=(100, 0, 0, 0, 0, 0, 0))

    accounts = [{"index": i,
                 "name": getattr(kid, "acct%s_name" % i) or "Acct%s" % i,
                 "active": i == 1, "comment": None} for i in range(1, 6)]
    locations = [{"index": j,
                  "name": getattr(kid, "location%s_name" % j) or "Loc%s" % j,
                  "active": j == 1, "comment": None} for j in range(1, 8)]

    response = client.patch("/api/kids/%s" % kid.id,
                            json={"accounts": accounts,
                                  "locations": locations})
    assert response.status_code == 200
    assert response.get_json()["orphanedAllowances"] == []

    allowance = models.Allowance.query.first()
    assert allowance.account1_perc == 100
    assert allowance.account2_perc == 0


def test_delete_a_kid_requires_confirmation(world):
    client = world["client"]
    login(client)
    kid_id = world["amy"].id
    f.make_allowance(world["amy"], amount=5.0, payout_days=(1, 2))

    refused = client.delete("/api/kids/%s" % kid_id)
    assert refused.status_code == 400
    assert models.Kid.query.filter_by(id=kid_id).count() == 1

    ok = client.delete("/api/kids/%s?confirm=true" % kid_id)
    assert ok.status_code == 200
    assert models.Kid.query.filter_by(id=kid_id).count() == 0
    assert models.Allowance.query.count() == 0
    assert models.AllowanceDays.query.count() == 0


def test_cannot_delete_another_familys_kid(world):
    client = world["client"]
    login(client)
    response = client.delete("/api/kids/%s?confirm=true" % world["ben"].id)
    assert response.status_code == 404
    assert models.Kid.query.filter_by(id=world["ben"].id).count() == 1


def test_cannot_update_another_familys_kid(world):
    client = world["client"]
    login(client)
    response = client.patch("/api/kids/%s" % world["ben"].id,
                            json={"firstname": "hijacked"})
    assert response.status_code == 404
