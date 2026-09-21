# Copyright (C) 2016  name of Zsolt Szabo zsoltman@hotmail.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
'''Parent accounts.

Extracted from app/lib/a_login.py. Passwords are hashed by werkzeug via
User.set_password / User.check_password -- note this is the only identity
in the system that is hashed; Kid.pw is stored in clear text so a parent
can read their child's password back to them.

The deletion cascade is hand-rolled because the models declare bare
ForeignKeys with no relationship() and no ondelete, so nothing happens
automatically. Order matters: allowance_days, then allowances and ledger,
then kids, then the user. Getting it wrong leaves orphans that
scripts/verify_prod_snapshot.py will report.
'''
import logging

import config
from app import db
from app import models
from app.services import errors

logger = logging.getLogger(__name__)


def is_demo_account(user_id):
    '''The shared evaluation account advertised on the landing page.

    It is deliberately undeletable, and cannot change its email or
    password, because everyone is invited to sign in as it.
    '''
    return user_id == config.ANON_C


def find_by_email(email):
    return models.User.query.filter(models.User.email == email).first()


def authenticate(email, password):
    '''The signed-in parent for these credentials, or raise.

    Since the TECH_SUPPORT master password was removed, a real password is
    the only way into an account through this path; support staff use a
    signed, expiring token instead (see app/support.py).
    '''
    user = find_by_email(email)
    if user is None or not user.check_password(password):
        raise errors.Unauthenticated(
            'User/Password combination not found', code='auth.bad_login')
    return user


def create(email, firstname, password, money_symbol):
    '''Register a new parent.

    Raises Conflict if the address is taken. The caller checks this first
    too, to render a friendlier page, but the rule belongs here.
    '''
    if find_by_email(email) is not None:
        raise errors.Conflict(
            'Cannot register this email, '
            'if you own it you can attempt to recover',
            code='parent.email_taken')

    user = models.User(email=email, firstname=firstname,
                       money_symbol=money_symbol)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def delete_with_children(user):
    '''Delete a parent and everything hanging off them.

    Hand-rolled cascade, deepest first: a kid's allowance_days, then its
    allowances and ledger, then the kids, then the parent.
    '''
    if is_demo_account(user.id):
        raise errors.Forbidden(
            'Come on!  Did you want to delete the evaluation user?',
            code='parent.demo_undeletable')

    kids = models.Kid.query.filter_by(parent_id=user.id)
    for each_kid in kids.all():
        allowances = models.Allowance.query.filter_by(kid_id=each_kid.id)
        for ea_allow in allowances.all():
            models.AllowanceDays.query.filter_by(
                allowance_id=ea_allow.id).delete()
        models.Ledger.query.filter_by(kid_id=each_kid.id).delete()
        allowances.delete()
    kids.delete()
    models.User.query.filter_by(id=user.id).delete()
    db.session.commit()
    logger.info('Deleted parent account %s and all child data' % user.id)
