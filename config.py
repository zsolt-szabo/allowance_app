import os

WTF_CSRF_ENABLED = True

#  CSRF tokens are sent as a header by JSON clients; forms keep using the
#  hidden field that FlaskForm already renders.
WTF_CSRF_HEADERS = ['X-CSRFToken', 'X-CSRF-Token']

#  The placeholder that ships in the repo. create_app refuses to start if
#  this is still the effective value, so an unconfigured deployment fails
#  loudly instead of signing cookies with a public key.
INSECURE_SECRET_KEY = 'you-should-change-this-to-something-secure-and-different'

#  NOTE: keep this on one line and byte-identical to INSECURE_SECRET_KEY
#  above. local_deployment_params.py rewrites it at deploy time by matching
#  the literal text, and aborts the deploy if the pattern is not found.
#  The environment override and the placeholder check live in create_app.
SECRET_KEY = 'you-should-change-this-to-something-secure-and-different'

#  Session cookie hardening. SECURE is off by default so the dev server on
#  plain http still works; the deployment runs behind TLS and should set
#  KIDALLOWANCE_SECURE_COOKIES=1.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = os.environ.get('KIDALLOWANCE_SECURE_COOKIES') == '1'
REMEMBER_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_SAMESITE = 'Lax'
REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE


basedir = os.path.abspath(os.path.dirname(__file__))

SERVER_CONFIG_JSON = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                  'gitkit-server-config.json')

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')

#  Deprecated and pure overhead; the app never used the signals.
SQLALCHEMY_TRACK_MODIFICATIONS = False

FLASK_LOG_LEVEL = 'DEBUG'
FLASK_LOG_LOCATION = basedir + "/allowance_app.log"
FLASK_LOG_MAXSIZE = 100000000
FLASK_LOG_RETAIN = 10

ENABLE_GOOGLE_LOGIN = False

#  The Jinja dashboard runs the allowance payout sweep on every page
#  load, as well as from cron. The JSON dashboard does the same while both
#  UIs are live, so behaviour does not depend on which one a family uses.
#  Turn this off once the cron job is proven, and payouts become
#  cron-only -- which is where they belong.
PAYOUT_ON_DASHBOARD_READ = True

ANON_C = 9999999999  # The database id for anonymous@coward.com

# Tech support no longer uses a shared master password.  Mint a short-lived,
# single-account token instead:  ./scripts/support_login.py --email <address>

#  Prepend to system password for google user, change for your
#  your local copy and don't check it in.
GOOG_PW = "a1a2google_userb6b8xzxxzyaa15332TuyvkbarU879"
GOOG_CLIENT_ID = "CONFIG_FOR_GOOGLE"
GOOG_CALLBACK_URL = "CONFIG_FOR_GOOGLE"
