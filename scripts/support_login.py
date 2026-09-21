#!/usr/bin/env python3
'''Mint a short-lived support login URL for one account.

Replaces the old shared master password.  Run it on the server (it needs the
application's SECRET_KEY and database), then paste the printed URL into a
browser to enter that account with the red TECH SUPPORT banner showing.

    ./scripts/support_login.py --email parent@example.com
    ./scripts/support_login.py --email parent@example.com --minutes 30 \
        --base-url https://kidallowance.net

The token names exactly one account, expires, and both minting and use are
written to the application log.
'''
import argparse
import os
import sys

from sqlalchemy.exc import OperationalError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_pkg                                        # noqa: E402
from app import models                                       # noqa: E402
from app.support import DEFAULT_TTL_MINUTES                  # noqa: E402
from app.support import generate_support_token               # noqa: E402


def describe_database():
    """The filesystem path behind the configured SQLAlchemy URI."""
    uri = app_pkg.app.config['SQLALCHEMY_DATABASE_URI']
    return uri[len('sqlite:///'):] if uri.startswith('sqlite:///') else uri


def rebind_database(path):
    """Repoint the app at a specific SQLite file.

    Flask-SQLAlchemy builds and caches its engine in init_app, so changing the
    config afterwards is not enough -- the extension has to be re-initialised.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        print('No such database file: %s' % path, file=sys.stderr)
        return False
    if os.path.getsize(path) == 0:
        print('Database file is empty (0 bytes): %s' % path, file=sys.stderr)
        return False

    app_pkg.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + path
    del app_pkg.app.extensions['sqlalchemy']
    app_pkg.db.init_app(app_pkg.app)
    return True


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--email', required=True,
                        help='email address of the parent account to enter')
    parser.add_argument('--minutes', type=int, default=DEFAULT_TTL_MINUTES,
                        help='how long the link stays valid '
                             '(default: %s)' % DEFAULT_TTL_MINUTES)
    parser.add_argument('--base-url', default='https://kidallowance.net',
                        help='site root to build the URL against')
    parser.add_argument('--database',
                        help='path to the app.db to read, overriding '
                             'config.py. On the server the live database is '
                             'kept outside the app directory, e.g. '
                             '/var/www/html/allowance_app_support/app.db')
    args = parser.parse_args()

    if args.database:
        if not rebind_database(args.database):
            return 1

    with app_pkg.app.app_context():
        database_path = describe_database()
        try:
            user = models.User.query.filter(
                models.User.email == args.email).first()
        except OperationalError as exc:
            if 'no such table' not in str(exc):
                raise
            print(file=sys.stderr)
            print('No kidallowance tables in: %s' % database_path,
                  file=sys.stderr)
            print(file=sys.stderr)
            print('That database is empty or missing. Point at the real one:',
                  file=sys.stderr)
            print('    %s --email %s \\' % (sys.argv[0], args.email),
                  file=sys.stderr)
            print('        --database /var/www/html/allowance_app_support/'
                  'app.db', file=sys.stderr)
            print(file=sys.stderr)
            print('Or create a local one for development: ./db_create.py',
                  file=sys.stderr)
            print(file=sys.stderr)
            return 1

        if user is None:
            print('No account found for %r in %s'
                  % (args.email, database_path), file=sys.stderr)
            return 1

        token = generate_support_token(user.id, user.email,
                                       minutes=args.minutes)
        app_pkg.app.logger.warning(
            'SUPPORT TOKEN MINTED for account id %s (%s), valid %s minutes'
            % (user.id, user.email, args.minutes))

    url = '%s/support?t=%s' % (args.base_url.rstrip('/'), token)
    print()
    print('  Account : %s (id %s)' % (user.email, user.id))
    print('  Valid   : %s minutes' % args.minutes)
    print('  URL     : %s' % url)
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
