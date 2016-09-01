import os
import getpass

WTF_CSRF_ENABLED = True
SECRET_KEY = 'you-should-change-this-to-something-secure-and-different'

basedir = os.path.abspath(os.path.dirname(__file__))

SERVER_CONFIG_JSON = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                  'gitkit-server-config.json')

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')

SQLALCHEMY_TRACK_MODIFICATIONS = True

FLASK_LOG_LEVEL = 'DEBUG'
FLASK_LOG_LOCATION = basedir + "/allowance_app.log"
FLASK_LOG_MAXSIZE = 100000000
FLASK_LOG_RETAIN = 10

ENABLE_GOOGLE_LOGIN = False
