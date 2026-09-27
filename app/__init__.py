# Copyright (C) 2016  name of Zsolt Szabo zsoltman@hotmail.com

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
from logging import Formatter
from logging.handlers import RotatingFileHandler
import os
import sqlite3

from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

import config

#  Extensions are created unbound and attached in create_app, so more than
#  one application can exist in a process -- which is what lets each test
#  have an isolated one instead of re-initialising a module-level app.
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
lm = LoginManager()
lm.login_view = 'login'
lm.session_protection = "basic"


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite ignores FOREIGN KEY constraints unless asked not to.

    Registered against the Engine class rather than one engine, so it
    applies to every application created here.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _configure_logging(app):
    """Rotating logfile. Module loggers under app.* propagate into this."""
    if any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        return
    handler = RotatingFileHandler(
        app.config['FLASK_LOG_LOCATION'],
        maxBytes=app.config['FLASK_LOG_MAXSIZE'],
        backupCount=app.config['FLASK_LOG_RETAIN'])
    handler.setFormatter(
        Formatter('[%(levelname)s][%(asctime)s] %(message)s'))
    app.logger.addHandler(handler)


def _check_secret_key(app):
    """Refuse to sign cookies with the key that ships in the repository.

    The environment wins over config.py, so a deployment can supply the key
    without a file rewrite. If the effective key is still the published
    placeholder this is CRITICAL rather than fatal by default -- a hard
    failure at import time would break the dev server and the test suite,
    both of which legitimately run on the placeholder. Set
    KIDALLOWANCE_REQUIRE_SECURE_KEY=1 in the deployment to make it fatal.
    """
    from_env = os.environ.get('KIDALLOWANCE_SECRET_KEY')
    if from_env:
        app.config['SECRET_KEY'] = from_env

    insecure = getattr(config, 'INSECURE_SECRET_KEY', None)
    if insecure is not None and app.config.get('SECRET_KEY') == insecure:
        message = ('SECRET_KEY is still the placeholder published in this '
                   'repository. Session cookies, CSRF tokens and support '
                   'login links are all forgeable. Set '
                   'KIDALLOWANCE_SECRET_KEY in the environment.')
        if os.environ.get('KIDALLOWANCE_REQUIRE_SECURE_KEY') == '1':
            raise RuntimeError(message)
        app.logger.critical(message)


def create_app(config_object='config', **overrides):
    """Build an application.

    Params
    ------
    config_object:  dotted name loaded via from_object
    overrides:      config values applied afterwards, for tests
    """
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.config.update(overrides)
    app.jinja_env.globals.update(config=config)  # Config avail to Templates

    db.init_app(app)
    migrate.init_app(app, db)
    lm.init_app(app)
    #  WTF_CSRF_ENABLED was True all along, but CSRFProtect was never
    #  instantiated -- so only routes going through FlaskForm.validate_on_
    #  submit() were checked. Anything reading request.form directly, or
    #  acting on GET, was not protected at all.
    csrf.init_app(app)
    _configure_logging(app)
    _check_secret_key(app)

    #  Imported here rather than at module scope: views imports the lib
    #  layer, which imports models, which imports db from this module.
    from app import models  # noqa: F401  (registers the mappers)
    from app import views
    views.init_app(app, lm)

    return app


#  A module-level application so `from app import app` keeps working for
#  run.py, the WSGI entry point and the scripts.
app = create_app()

logger = app.logger
