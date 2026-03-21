#!/usr/bin/env python
from app import app, db
from flask_migrate import init
import os

with app.app_context():
    db.create_all()
    migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')
    if not os.path.exists(migrations_dir):
        init()
        print('Migration repository created.')
    print('Database created.')
