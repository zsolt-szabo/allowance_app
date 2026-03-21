#!/usr/bin/env python
from app import app, db
from flask_migrate import migrate, upgrade

with app.app_context():
    migrate()
    upgrade()
    print('Database migrated.')
