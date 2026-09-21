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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_pkg                                        # noqa: E402
from app import models                                       # noqa: E402
from app.support import DEFAULT_TTL_MINUTES                  # noqa: E402
from app.support import generate_support_token               # noqa: E402


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
    args = parser.parse_args()

    with app_pkg.app.app_context():
        user = models.User.query.filter(
            models.User.email == args.email).first()
        if user is None:
            print("No account found for %r" % args.email, file=sys.stderr)
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
