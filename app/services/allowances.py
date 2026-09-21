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
'''Creating, listing and deleting allowances.

An allowance says: pay this amount on these days of the month, split this
way across the sub-accounts and this way across the money locations. Both
splits must total exactly 100.

"Exactly" is not a stylistic choice. The database carries CheckConstraints
``acc_100`` and ``loc_100`` comparing a sum of floats to 100, so a split
that rounds to 99.99 is rejected by SQLite at INSERT time rather than
caught here. That is also why the redistribution code elsewhere makes one
bucket absorb the leftover rather than dividing evenly.

Extracted from app/lib/a_finance.py. The percentage arithmetic and the
message text are unchanged.
'''
import logging

from app import db
from app import models
from app.domain import buckets
from app.services import errors

logger = logging.getLogger(__name__)


def _zero_if_none(value):
    '''Named `c` in the original.'''
    return 0 if value is None else value


def list_for_kid(kid):
    '''A kid's allowances, each tagged with a .DATES list of payout days.

    The attribute is attached to the model instance rather than returned
    alongside it, matching what allowance.html iterates over today.
    '''
    allowances = models.Allowance.query.filter(
        models.Allowance.kid_id == kid.id).all()
    for allowance in allowances:
        days = models.AllowanceDays.query.filter(
            models.AllowanceDays.allowance_id == allowance.id).all()
        allowance.DATES = [day.payout_day for day in days]
    return allowances


def validate_percentages(account_percs, location_percs):
    '''Both splits must total exactly 100, or raise ValidationFailed.

    Inactive buckets have already been forced to zero by the caller, so a
    percentage aimed at a switched-off bucket shows up here as a shortfall.
    '''
    total_accounts = sum(_zero_if_none(p) for p in account_percs)
    total_location = sum(_zero_if_none(p) for p in location_percs)

    #  Checked in this order, and only the last failure is reported --
    #  preserved from the original, where `msg` was overwritten.
    msg = None
    if total_accounts != 100:
        msg = "Allowance distribution among sub-accounts must add up "
        msg += "to 100%"
    if total_location != 100:
        msg = "Allowance storage (where) must add up "
        msg += "to 100%"
    if msg is not None:
        raise errors.ValidationFailed(msg, code='allowance.percentages')


def create(kid, amount, nickname, payout_days, account_percs,
           location_percs):
    '''Create an allowance and its payout days.

    Params
    ------
    kid:             models.Kid the allowance belongs to
    amount:          paid per payout day, not per month
    nickname:        free text; shown on the allowance and ledger screens
    payout_days:     iterable of days-of-month, 1..28
    account_percs:   5 values, in slot order, totalling 100
    location_percs:  7 values, in slot order, totalling 100

    NOTE: not atomic. The allowance is committed first and each payout day
    after it, so a failure part-way leaves an allowance with some of its
    days missing. Preserved from the original; the caller flashes a warning.
    '''
    validate_percentages(account_percs, location_percs)

    allowance = models.Allowance(
        kid_id=kid.id, amount=amount, nickname=nickname,
        **{'account%s_perc' % i: account_percs[i - 1]
           for i in buckets.ACCOUNT_SLOTS},
        **{'location%s_perc' % j: location_percs[j - 1]
           for j in buckets.LOCATION_SLOTS})
    db.session.add(allowance)
    db.session.commit()

    failures = []
    for day in payout_days:
        try:
            db.session.add(models.AllowanceDays(
                payout_day=day, allowance_id=allowance.id))
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception('ALLOWANCE ID: %s, DATE: %s'
                             % (allowance.id, day))
            failures.append(day)

    return allowance, failures


def delete(allowance):
    '''Remove an allowance and its payout days.

    Ledger entries it has already produced are deliberately left alone:
    that money was really paid out, and the history has to stay truthful.
    '''
    models.AllowanceDays.query.filter_by(allowance_id=allowance.id).delete()
    models.Allowance.query.filter_by(id=allowance.id).delete()
    db.session.commit()
