"""Pytest fixtures for the kidallowance test suite.

The application object is created at import time in ``app/__init__.py``
(there is no app factory yet -- that arrives in Stage 2).  So these fixtures
do the same re-binding dance the legacy ``unit/test_group_01.py`` does: point
SQLAlchemy at a throwaway SQLite file, then drop/create the schema around
every test so each one starts from an empty database.
"""
import os
import sys
import logging
import tempfile

import pytest
from flask.testing import FlaskClient
from flask.globals import _cv_app as _app_ctx

# The app package lives at the repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import app as app_pkg                      # noqa: E402
from app import app as flask_app           # noqa: E402
from app import db as _db                  # noqa: E402

logging.getLogger().setLevel(logging.ERROR)


@pytest.fixture(scope="session")
def _bound_app():
    """Bind the module-level Flask app to a temporary SQLite database, once."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db",
                                      prefix="kidallowance-test-")

    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path

    # Flask-SQLAlchemy caches the engine per-app under this extension key; drop
    # it so init_app picks up the new URI instead of the one from config.py.
    del flask_app.extensions["sqlalchemy"]
    _db.init_app(flask_app)

    ctx = flask_app.app_context()
    ctx.push()

    yield flask_app

    _db.session.remove()
    ctx.pop()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def flask_obj(_bound_app):
    """A Flask app with an empty schema. Function-scoped for test isolation."""
    _db.session.remove()
    _db.drop_all()
    _db.create_all()
    yield _bound_app
    _db.session.remove()


@pytest.fixture
def db(flask_obj):
    return _db


class IsolatedClient(FlaskClient):
    """A test client that gives every request a clean ``flask.g``.

    ``g`` is stored on the *application* context, not the request context.  The
    fixtures here keep one long-lived app context pushed so ORM objects stay
    attached, which means Flask would otherwise reuse that same ``g`` for every
    request -- and Flask-Login, finding its cached ``g._login_user``, would
    skip calling ``load_user`` entirely.  That matters because ``load_user``
    is what populates ``g.is_child`` / ``g.kid_id`` / ``g.user_id``; without
    this reset, child-path tests exercise a harness artifact rather than the
    real app, where each request genuinely starts with an empty ``g``.
    """

    def open(self, *args, **kwargs):
        ctx = _app_ctx.get(None)
        if ctx is not None:
            vars(ctx.g).clear()
        return super().open(*args, **kwargs)


@pytest.fixture
def client(flask_obj):
    """A test client for driving the current Jinja app over HTTP."""
    flask_obj.test_client_class = IsolatedClient
    return flask_obj.test_client()


@pytest.fixture
def models():
    return app_pkg.models


@pytest.fixture
def db_(flask_obj):
    """Alias of ``db`` for tests that only need the empty-schema guarantee."""
    return _db


@pytest.fixture
def parent(db_):
    from tests import factories
    return factories.make_parent()


@pytest.fixture
def kid(parent):
    from tests import factories
    return factories.make_kid(parent)
