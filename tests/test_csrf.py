"""CSRF protection, exercised with it actually switched on.

The rest of the suite runs with WTF_CSRF_ENABLED=False for convenience, so
these tests build their own application with the real setting. Without
them, nothing would notice CSRFProtect being removed again.
"""
import os
import re
import tempfile

import pytest

from app import create_app, db, models


@pytest.fixture
def csrf_app():
    fd, path = tempfile.mkstemp(suffix=".db", prefix="csrf-test-")
    app = create_app(TESTING=True,
                     WTF_CSRF_ENABLED=True,
                     SQLALCHEMY_DATABASE_URI="sqlite:///" + path)
    with app.app_context():
        db.create_all()
        user = models.User(firstname="Pat", email="pat@example.com")
        user.set_password("pw123456")
        db.session.add(user)
        db.session.commit()
    yield app
    os.close(fd)
    os.unlink(path)


def csrf_token_from(html):
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return match.group(1) if match else None


def test_post_without_a_token_is_rejected(csrf_app):
    client = csrf_app.test_client()
    response = client.post("/login", data={"email": "pat@example.com",
                                           "password": "pw123456"})
    assert response.status_code == 400
    assert "Logout" not in response.data.decode()


def test_post_with_a_valid_token_succeeds(csrf_app):
    client = csrf_app.test_client()
    token = csrf_token_from(client.get("/login").data.decode())
    assert token, "the login form should render a csrf_token field"

    response = client.post("/login",
                           data={"email": "pat@example.com",
                                 "password": "pw123456",
                                 "csrf_token": token},
                           follow_redirects=True)
    assert response.status_code == 200
    assert "Logout" in response.data.decode()


def test_a_forged_token_is_rejected(csrf_app):
    client = csrf_app.test_client()
    client.get("/login")
    response = client.post("/login", data={"email": "pat@example.com",
                                           "password": "pw123456",
                                           "csrf_token": "not-a-real-token"})
    assert response.status_code == 400


def test_the_token_may_be_sent_as_a_header(csrf_app):
    """JSON clients cannot use a hidden form field; WTF_CSRF_HEADERS lets
    them send the same token as X-CSRFToken."""
    client = csrf_app.test_client()
    token = csrf_token_from(client.get("/login").data.decode())

    response = client.post("/login",
                           data={"email": "pat@example.com",
                                 "password": "pw123456"},
                           headers={"X-CSRFToken": token},
                           follow_redirects=True)
    assert response.status_code == 200
    assert "Logout" in response.data.decode()


def test_google_signin_is_no_longer_exempt(csrf_app):
    """This endpoint reads request.form directly with no FlaskForm, so
    before CSRFProtect was instantiated it had no protection at all."""
    client = csrf_app.test_client()
    response = client.post("/google_signin",
                           data={"id_token": "x", "email": "pat@example.com"})
    assert response.status_code == 400


def test_session_cookie_is_hardened(csrf_app):
    assert csrf_app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert csrf_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


@pytest.mark.parametrize("path", ["/login", "/child_login", "/register"])
def test_form_pages_render_a_token(csrf_app, path):
    """Every page with a form must emit one, or the form is unusable now
    that CSRFProtect enforces it."""
    html = csrf_app.test_client().get(path).data.decode()
    assert csrf_token_from(html), "no csrf_token field on %s" % path


def test_registration_round_trips_with_csrf_on(csrf_app):
    """register.html is the one template with two <form> matches; make
    sure the real flow still completes end to end."""
    client = csrf_app.test_client()
    page = client.get("/register").data.decode()
    token = csrf_token_from(page)

    with csrf_app.app_context():
        from flask import session as flask_session  # noqa: F401
    # The captcha answer is held in the session; read it back out.
    with client.session_transaction() as session:
        answer = session.get("cap_solution")

    response = client.post("/register",
                           data={"email": "new@example.com",
                                 "firstname": "New",
                                 "password1": "pw123456",
                                 "password2": "pw123456",
                                 "money_symbol": "$",
                                 "captcha": str(answer).replace(" ", ""),
                                 "csrf_token": token},
                           follow_redirects=True)
    assert response.status_code == 200
    with csrf_app.app_context():
        assert models.User.query.filter_by(
            email="new@example.com").count() == 1
