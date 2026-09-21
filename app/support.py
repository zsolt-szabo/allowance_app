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
'''Short-lived support tokens.

Replaces the former ``config.TECH_SUPPORT`` master password, which was a single
standing string that logged you into *any* parent account, never expired, and
left no audit trail.

A support token instead:
  * names exactly one account,
  * expires (15 minutes by default),
  * is minted from a shell on the server, so it requires host access rather
    than knowledge of a string, and
  * is logged when it is minted and when it is used.

Mint one with ``scripts/support_login.py``; spend it by visiting /support?t=...
'''
from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import app

# Namespaces the signature so a support token can never be confused with any
# other thing signed by the same SECRET_KEY.
SUPPORT_SALT = 'kidallowance-support-login'
DEFAULT_TTL_MINUTES = 15
# Hard ceiling; no support token may outlive this regardless of request.
MAX_TTL_MINUTES = 24 * 60


class SupportTokenError(Exception):
    '''Raised when a token is missing, malformed, forged or expired.'''


def _serializer():
    return URLSafeTimedSerializer(app.config['SECRET_KEY'],
                                  salt=SUPPORT_SALT)


def generate_support_token(user_id, email, minutes=DEFAULT_TTL_MINUTES):
    '''Sign a token granting temporary access to one specific account.

    The email is carried along so the token is rejected if the account is
    renumbered or the address reassigned between minting and use.  The lifetime
    is carried too, so the expiry the operator asked for is the expiry the
    server actually enforces.
    '''
    minutes = max(1, min(int(minutes), MAX_TTL_MINUTES))
    return _serializer().dumps({'user_id': int(user_id),
                                'email': email,
                                'ttl': minutes})


def consume_support_token(token):
    '''Verify a token and return its payload, or raise SupportTokenError.'''
    if not token:
        raise SupportTokenError('No support token supplied')
    try:
        # Validate the signature against a hard ceiling first, then enforce
        # the tighter lifetime the token itself asked for.
        payload, issued_at = _serializer().loads(
            token, max_age=MAX_TTL_MINUTES * 60, return_timestamp=True)
    except SignatureExpired:
        raise SupportTokenError('Support token has expired')
    except BadSignature:
        raise SupportTokenError('Support token is not valid')

    if not isinstance(payload, dict) or 'user_id' not in payload:
        raise SupportTokenError('Support token payload is malformed')

    ttl_minutes = min(int(payload.get('ttl', DEFAULT_TTL_MINUTES)),
                      MAX_TTL_MINUTES)
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - issued_at
    if age > timedelta(minutes=ttl_minutes):
        raise SupportTokenError('Support token has expired')

    return payload
