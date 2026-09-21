"""Tests for app/auth.py -- the Actor and the single ownership check.

The ownership rule is the security boundary of this application: it is what
stops one parent reading another family's ledger, and what stops a child
reaching anything but their own record.  It is currently hand-written in five
places; these tests cover the one implementation that replaces them.
"""
import pytest
from flask import g

from app import auth
from app.services import errors
from tests import factories as f


@pytest.fixture
def two_families(db_):
    """Two unrelated parents, each with one kid."""
    alice = f.make_parent(email="alice@example.com")
    bob = f.make_parent(email="bob@example.com")
    alice_kid = f.make_kid(alice, firstname="amy",
                           animal1="rabbit", animal2="rabbit")
    bob_kid = f.make_kid(bob, firstname="ben",
                         animal1="tiger", animal2="tiger")
    return alice, alice_kid, bob, bob_kid


def as_parent(parent):
    vars(g).clear()
    g.user_id = parent.id


def as_child(kid):
    vars(g).clear()
    g.is_child = True
    g.kid_id = kid.id


def as_anonymous():
    vars(g).clear()


# --- Actor -----------------------------------------------------------------

def test_parent_actor_has_no_kid_id():
    actor = auth.Actor.parent(7)
    assert actor.is_parent and not actor.is_child
    assert actor.parent_id == 7
    assert actor.kid_id is None


def test_child_actor_has_no_parent_id():
    """The safety property: a child actor cannot supply a parent id."""
    actor = auth.Actor.child(3)
    assert actor.is_child and not actor.is_parent
    assert actor.kid_id == 3
    assert actor.parent_id is None


def test_actor_is_immutable():
    actor = auth.Actor.child(3)
    with pytest.raises(AttributeError):
        actor.parent_id = 1


# --- current_actor ---------------------------------------------------------

def test_current_actor_reads_a_parent_session(two_families):
    alice = two_families[0]
    as_parent(alice)
    assert auth.current_actor() == auth.Actor.parent(alice.id)


def test_current_actor_reads_a_child_session(two_families):
    alice_kid = two_families[1]
    as_child(alice_kid)
    assert auth.current_actor() == auth.Actor.child(alice_kid.id)


def test_current_actor_is_none_when_anonymous(db_):
    as_anonymous()
    assert auth.current_actor() is None


def test_require_actor_raises_when_anonymous(db_):
    as_anonymous()
    with pytest.raises(errors.Unauthenticated):
        auth.require_actor()


def test_require_parent_rejects_a_child_with_403_not_500(two_families):
    """Today a child reaching a parent-only handler is an AttributeError on
    g.user_id, i.e. a 500. It should be a clean, deliberate refusal."""
    as_child(two_families[1])
    with pytest.raises(errors.Forbidden) as caught:
        auth.require_parent()
    assert caught.value.status == 403


def test_parent_required_decorator_guards_a_view(two_families):
    calls = []

    @auth.parent_required
    def view():
        calls.append(1)
        return "ok"

    as_parent(two_families[0])
    assert view() == "ok"

    as_child(two_families[1])
    with pytest.raises(errors.Forbidden):
        view()
    assert calls == [1], "the view body must not run for a child"


# --- resolve_kid: the authorization matrix ---------------------------------

def test_parent_can_resolve_their_own_kid(two_families):
    alice, alice_kid, _bob, _bob_kid = two_families
    as_parent(alice)
    assert auth.resolve_kid(auth.current_actor(), alice_kid.id).id == \
        alice_kid.id


def test_parent_cannot_resolve_another_familys_kid(two_families):
    alice, _alice_kid, _bob, bob_kid = two_families
    as_parent(alice)
    with pytest.raises(errors.NotFound):
        auth.resolve_kid(auth.current_actor(), bob_kid.id)


def test_child_can_resolve_only_themselves(two_families):
    _alice, alice_kid, _bob, bob_kid = two_families
    as_child(alice_kid)
    actor = auth.current_actor()

    assert auth.resolve_kid(actor, alice_kid.id).id == alice_kid.id
    with pytest.raises(errors.NotFound):
        auth.resolve_kid(actor, bob_kid.id)


def test_missing_kid_is_not_found(two_families):
    as_parent(two_families[0])
    with pytest.raises(errors.NotFound):
        auth.resolve_kid(auth.current_actor(), 99999)


def test_another_familys_kid_is_indistinguishable_from_a_missing_one(
        two_families):
    """Probing ids must not confirm that another family's kid exists."""
    alice, _alice_kid, _bob, bob_kid = two_families
    as_parent(alice)
    actor = auth.current_actor()

    with pytest.raises(errors.NotFound) as other:
        auth.resolve_kid(actor, bob_kid.id)
    with pytest.raises(errors.NotFound) as absent:
        auth.resolve_kid(actor, 99999)

    assert other.value.message == absent.value.message
    assert other.value.status == absent.value.status == 404


# --- resolve_kid_by_login: same rules, legacy addressing -------------------

def test_resolve_by_login_enforces_the_same_ownership(two_families):
    alice, alice_kid, _bob, _bob_kid = two_families
    as_parent(alice)
    actor = auth.current_actor()

    found = auth.resolve_kid_by_login(actor, "amy", "rabbit", "rabbit")
    assert found.id == alice_kid.id

    # Bob's kid, addressed by their real login triple.
    with pytest.raises(errors.NotFound):
        auth.resolve_kid_by_login(actor, "ben", "tiger", "tiger")


def test_child_resolve_by_login_cannot_reach_another_kid(two_families):
    _alice, alice_kid, _bob, _bob_kid = two_families
    as_child(alice_kid)
    actor = auth.current_actor()

    assert auth.resolve_kid_by_login(actor, "amy", "rabbit", "rabbit").id == \
        alice_kid.id
    with pytest.raises(errors.NotFound):
        auth.resolve_kid_by_login(actor, "ben", "tiger", "tiger")


# --- parse_kid_triple ------------------------------------------------------

def test_parse_kid_triple_splits_the_url_fragment():
    assert auth.parse_kid_triple("amy:rabbit:rabbit") == \
        ("amy", "rabbit", "rabbit")


@pytest.mark.parametrize("bad", [None, "", "amy", "amy:rabbit",
                                 "amy:rabbit:rabbit:extra"])
def test_parse_kid_triple_rejects_malformed_input(bad):
    """a_finance currently lets a missing reference through and then
    dereferences None, which is a TypeError and a 500."""
    with pytest.raises(errors.ValidationFailed):
        auth.parse_kid_triple(bad)
