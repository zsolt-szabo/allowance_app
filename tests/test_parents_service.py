"""Tests for app/services/parents.py."""
import pytest

import config
from app import models
from app.services import errors, parents
from tests import factories as f


def test_authenticate_accepts_the_right_password(db_):
    parent = f.make_parent(email="a@example.com", password="correct-horse")
    assert parents.authenticate("a@example.com", "correct-horse").id == \
        parent.id


def test_authenticate_rejects_a_wrong_password(db_):
    f.make_parent(email="a@example.com", password="correct-horse")
    with pytest.raises(errors.Unauthenticated):
        parents.authenticate("a@example.com", "wrong")


def test_unknown_email_is_indistinguishable_from_a_wrong_password(db_):
    """The login form must not reveal which addresses have accounts."""
    f.make_parent(email="a@example.com", password="correct-horse")

    with pytest.raises(errors.Unauthenticated) as wrong_pw:
        parents.authenticate("a@example.com", "wrong")
    with pytest.raises(errors.Unauthenticated) as no_such:
        parents.authenticate("nobody@example.com", "wrong")

    assert wrong_pw.value.message == no_such.value.message


def test_create_hashes_the_password(db_):
    user = parents.create(email="new@example.com", firstname="New",
                          password="s3cret", money_symbol="$")
    assert user.pw_hash != "s3cret"
    assert user.check_password("s3cret")


def test_create_rejects_a_duplicate_email(db_):
    f.make_parent(email="taken@example.com")
    with pytest.raises(errors.Conflict):
        parents.create(email="taken@example.com", firstname="Other",
                       password="pw", money_symbol="$")


def test_delete_cascades_to_every_child_record(db_):
    """The models declare bare ForeignKeys with no ondelete, so the cascade
    is hand-rolled and a wrong order leaves orphans."""
    parent = f.make_parent(email="doomed@example.com")
    kid = f.make_kid(parent)
    f.make_allowance(kid, amount=5.0, payout_days=(1, 15))
    assert models.Kid.query.count() == 1
    assert models.Allowance.query.count() == 1
    assert models.AllowanceDays.query.count() == 2

    parents.delete_with_children(parent)

    assert models.User.query.count() == 0
    assert models.Kid.query.count() == 0
    assert models.Allowance.query.count() == 0
    assert models.AllowanceDays.query.count() == 0


def test_delete_leaves_other_families_alone(db_):
    keeper = f.make_parent(email="keeper@example.com")
    keeper_kid = f.make_kid(keeper, firstname="keep",
                            animal1="goose", animal2="goose")
    f.make_allowance(keeper_kid, amount=5.0, payout_days=(1,))

    doomed = f.make_parent(email="doomed@example.com")
    doomed_kid = f.make_kid(doomed, firstname="gone",
                            animal1="tiger", animal2="tiger")
    f.make_allowance(doomed_kid, amount=5.0, payout_days=(1,))

    parents.delete_with_children(doomed)

    assert [u.email for u in models.User.query.all()] == \
        ["keeper@example.com"]
    assert [k.firstname for k in models.Kid.query.all()] == ["keep"]
    assert models.Allowance.query.count() == 1


def test_the_demo_account_cannot_be_deleted(db_):
    """Everyone is invited to sign in as it, so it must survive."""
    demo = f.make_parent(email="anonymous@coward.com")
    demo.id = config.ANON_C
    from app import db
    db.session.commit()

    assert parents.is_demo_account(demo.id)
    with pytest.raises(errors.Forbidden):
        parents.delete_with_children(demo)
    assert models.User.query.count() == 1
