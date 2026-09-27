"""Tests for the Flask-Login session id encoding.

Two tables act as identities, so the stored id has to say which one it
refers to. Getting that wrong means resolving an id against the wrong
table -- a child decoding as a parent, or vice versa.

The back-compat tests matter operationally: deploying this must not sign
every live user out.
"""
import pytest

from app import models, session_ids
from tests import factories as f


# --- encoding --------------------------------------------------------------

def test_parent_id_is_prefixed(db_):
    parent = f.make_parent()
    assert parent.get_id() == "p:%s" % parent.id


def test_child_id_is_prefixed(db_):
    parent = f.make_parent()
    kid = f.make_kid(parent)
    assert kid.get_id() == "c:%s" % kid.id


def test_round_trip_parent(db_):
    parent = f.make_parent()
    assert session_ids.parse(parent.get_id()) == \
        (session_ids.PARENT, parent.id)


def test_round_trip_child(db_):
    parent = f.make_parent()
    kid = f.make_kid(parent)
    assert session_ids.parse(kid.get_id()) == (session_ids.CHILD, kid.id)


def test_a_parent_and_a_child_with_the_same_row_id_do_not_collide():
    """The whole point: id 7 in `user` and id 7 in `kid` are different."""
    assert session_ids.parse("p:7") == (session_ids.PARENT, 7)
    assert session_ids.parse("c:7") == (session_ids.CHILD, 7)


# --- back compatibility ----------------------------------------------------

def test_legacy_child_tuple_still_parses():
    """Children used to be stored as the tuple ('child', '7')."""
    assert session_ids.parse(("child", "7")) == (session_ids.CHILD, 7)


def test_legacy_child_tuple_as_list_still_parses():
    """Depending on serializer the tuple can come back as a list."""
    assert session_ids.parse(["child", "7"]) == (session_ids.CHILD, 7)


def test_legacy_bare_parent_string_still_parses():
    """Parents used to be stored as a bare numeric string."""
    assert session_ids.parse("7") == (session_ids.PARENT, 7)


def test_bare_int_parses_as_a_parent():
    assert session_ids.parse(7) == (session_ids.PARENT, 7)


# --- junk ------------------------------------------------------------------

@pytest.mark.parametrize("junk", [
    None, "", "p:", "c:", "p:abc", "nonsense", ("child",),
    ("parent", "7"), (), [], {}, 3.5,
])
def test_unusable_values_parse_to_nothing(junk):
    """A corrupt cookie degrades to anonymous rather than raising."""
    assert session_ids.parse(junk) == (None, None)


# --- the operational concern -----------------------------------------------

def test_a_live_legacy_parent_session_still_authenticates(db_, client):
    """A parent signed in before this change keeps their session."""
    parent = f.make_parent(email="p@example.com", password="pw123456")

    with client.session_transaction() as session:
        session["_user_id"] = str(parent.id)      # the old encoding

    page = client.get("/index", follow_redirects=True).data.decode()
    assert "Logout" in page, "legacy parent session was dropped"


def test_a_live_legacy_child_session_still_authenticates(db_, client):
    """A child signed in before this change keeps their session, and is
    still recognised as a child rather than resolving against `user`."""
    parent = f.make_parent(email="p@example.com", password="pw123456")
    kid = f.make_kid(parent)

    with client.session_transaction() as session:
        session["_user_id"] = ("child", str(kid.id))   # the old encoding

    page = client.get("/index", follow_redirects=True).data.decode()
    assert "Logout" in page, "legacy child session was dropped"
    # The child dashboard shows the kid's own name.
    assert kid.firstname in page


def test_a_session_naming_a_deleted_row_is_anonymous(db_, client):
    with client.session_transaction() as session:
        session["_user_id"] = "p:99999"

    page = client.get("/index", follow_redirects=True).data.decode()
    assert "Logout" not in page
    assert models.User.query.count() == 0
