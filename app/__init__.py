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
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
from logging.handlers import RotatingFileHandler
from logging import Formatter
import config

app = Flask(__name__)
app.config.from_object('config')
app.jinja_env.globals.update(config=config)  # Config avail to Templates

db = SQLAlchemy(app)
migrate = Migrate(app, db)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

lm = LoginManager()
lm.login_view = 'login'
lm.session_protection = "basic"
lm.init_app(app)

# Create a rotating logfile for the application
handler = RotatingFileHandler(
    config.FLASK_LOG_LOCATION, maxBytes=config.FLASK_LOG_MAXSIZE,
    backupCount=config.FLASK_LOG_RETAIN)
handler.setFormatter(
    Formatter('[%(levelname)s][%(asctime)s] %(message)s'))
app.logger.addHandler(handler)

logger = app.logger

# Avoid circular ref, import here
from app import views, models
