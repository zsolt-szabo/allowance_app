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
import sqlite3

from flask import Flask
from flask_login import LoginManager
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
    _configure_logging(app)

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
