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
'''Posting a manual ledger entry.

A transaction is a 5x7 grid of deltas: each cell is folded into both its
sub-account row and its money-location column, which is what keeps the two
axes describing the same money.

Extracted from app/lib/a_finance.py::handle_ledger_post. The arithmetic and
the traversal order are unchanged, deliberately:

  * cells are visited i = 1..5 outer, j = 1..7 inner, and each cell is
    rounded on its own before being accumulated. Rounding the accumulated
    sum instead would give different answers for sub-cent inputs, so the
    order is load-bearing and is pinned by
    tests/characterization/test_ledger_math.py.
  * the seed totals are rounded once, up front, exactly as before.

What did change is how failure is reported: the original flashed a message
and returned False (or, in two places, bare None), so the only way to learn
what went wrong was to read the flash queue. This raises DomainError with
the identical message text, which a Jinja handler can flash and a JSON
endpoint can serialise.
'''
import logging

from app import db
from app import models
from app.domain import buckets
from app.services import errors

logger = logging.getLogger(__name__)


def _round(value):
    '''Round to two digits. Named `r` in the original.'''
    return round(value, 2)


def _zero_if_none(value):
    '''Named `a` in the original.'''
    return 0 if value is None else value


class EmptyLedger:
    '''Zeroed stand-in for a kid with no ledger history yet.'''

    def __init__(self):
        for slot in buckets.ACCOUNT_SLOTS:
            setattr(self, 'total_acc%s' % slot, 0)
        for slot in buckets.LOCATION_SLOTS:
            setattr(self, 'total_loc%s' % slot, 0)


def post_ledger_entry(actor, kid, last_entry, cells, comment, no_comment,
                      adjuster_name, adjusted_by_parent):
    '''Append one transaction to a kid's ledger and return the new row.

    Params
    ------
    actor:               app.auth.Actor making the change
    kid:                 models.Kid the money belongs to
    last_entry:          the kid's most recent Ledger row, or None
    cells:               {(account_slot, location_slot): amount}; absent
                         cells count as zero
    comment:             free text, or None
    no_comment:          True if the user explicitly opted out of a comment
    adjuster_name:       who to record against the entry
    adjusted_by_parent:  Boolean flag stored on the row

    Raises DomainError on any broken rule; the caller decides how to show it.
    '''
    previous = last_entry if last_entry is not None else EmptyLedger()

    #  Preserved verbatim, including the operator precedence: `and` binds
    #  tighter than `or`, so a comment of None short-circuits and the
    #  no_comment opt-out is ignored. Browsers always submit the textarea so
    #  this is invisible today; it is pinned as a KNOWN_BUG test because a
    #  JSON client that omits the field will hit it.
    if comment is None or comment == "" and no_comment is not True:
        msg = "You need to select 'no comment' if you want to commit "
        msg += "without a comment"
        raise errors.ValidationFailed(msg, code='ledger.comment_required')

    loc_math = {'loc%s' % j: 0 for j in buckets.LOCATION_SLOTS}
    acc_math = {'acc%s' % i: 0 for i in buckets.ACCOUNT_SLOTS}
    all_entries = 0

    update = {'adjuster_name': adjuster_name,
              'adjusted_by_parent': adjusted_by_parent,
              'kid_id': kid.id,
              'comment': comment}
    for i in buckets.ACCOUNT_SLOTS:
        update['change_acc%s' % i] = 0
        update['total_acc%s' % i] = _round(
            getattr(previous, 'total_acc%s' % i))
    for j in buckets.LOCATION_SLOTS:
        update['change_loc%s' % j] = 0
        update['total_loc%s' % j] = _round(
            getattr(previous, 'total_loc%s' % j))

    for i in buckets.ACCOUNT_SLOTS:
        for j in buckets.LOCATION_SLOTS:
            entry = _zero_if_none(cells.get((i, j)))
            loc_math['loc%s' % j] += entry
            acc_math['acc%s' % i] += entry

            #  A deactivated bucket may be drained but not topped up.
            #  NOTE: `"'" + name` raises TypeError when the bucket has a NULL
            #  name, which is a 500. Preserved as-is and pinned by a
            #  KNOWN_BUG test; Stage 5 fixes it.
            if getattr(kid, "acct%s_used" % i) is False and entry > 0:
                msg = "'" + getattr(kid, "acct%s_name" % i)
                msg += "' is a deactivated account, you can only take "
                msg += "money out until the account is empty"
                raise errors.Forbidden(msg, code='ledger.account_deactivated')
            if getattr(kid, "location%s_used" % j) is False and entry > 0:
                msg = "'" + getattr(kid, "location%s_name" % j)
                msg += "' is a deactivated location, you can only take "
                msg += "money out until the location is empty"
                raise errors.Forbidden(msg, code='ledger.location_deactivated')

            all_entries += entry

            #  Each cell is rounded individually and accumulated; see the
            #  module docstring.
            update['change_acc%s' % i] += _round(entry)
            update['change_loc%s' % j] += _round(entry)
            update['total_acc%s' % i] += _round(entry)
            update['total_loc%s' % j] += _round(entry)

    #  Both axes are checked independently, locations first -- which is why
    #  an overdraw names the money storage rather than the sub-account.
    for ea_loc in loc_math:
        if loc_math[ea_loc] > 0 and actor.is_child:
            raise errors.Forbidden(
                "Only Parent can add money, kids can subtract",
                code='ledger.child_cannot_add')
        if _round(loc_math[ea_loc] + getattr(previous,
                                             'total_' + ea_loc)) < 0:
            msg = "You attempted to take too much from money storage '%s'"
            msg = msg % getattr(
                kid, ea_loc.replace('loc', 'location') + "_name")
            raise errors.ValidationFailed(
                msg, code='ledger.location_overdrawn')
    for ea_acc in acc_math:
        if acc_math[ea_acc] > 0 and actor.is_child:
            raise errors.Forbidden(
                "Only Parent can add money, kids can subtract",
                code='ledger.child_cannot_add')
        if _round(acc_math[ea_acc] + getattr(previous,
                                             'total_' + ea_acc)) < 0:
            msg = "You attempted to take too much from account '%s'"
            msg = msg % getattr(
                kid, ea_acc.replace('acc', 'acct') + "_name")
            raise errors.ValidationFailed(msg, code='ledger.account_overdrawn')

    #  NOTE: this tests the grand sum of the grid, so a transfer between
    #  buckets that nets to zero is refused. Pinned as a KNOWN_BUG test.
    if all_entries == 0:
        raise errors.ValidationFailed('No account changes to update',
                                      code='ledger.no_change')

    new_entry = models.Ledger(**update)
    db.session.add(new_entry)
    db.session.commit()
    return new_entry


def cells_from_form(form):
    '''{(account_slot, location_slot): amount} from a forms.Ledger instance.'''
    return {(i, j): getattr(form, 'acct%s_loc%s' % (i, j)).data
            for i in buckets.ACCOUNT_SLOTS
            for j in buckets.LOCATION_SLOTS}


def entries_for_kid(kid):
    '''A kid's ledger, newest first.

    NOTE: ordered by last_ledger_update, whereas app/services/payout.py
    orders the same rows by id. The two agree on all current data but are
    different definitions of "latest".
    '''
    return models.Ledger.query.filter(
        models.Ledger.kid_id == kid.id).order_by(
        models.Ledger.last_ledger_update.desc()).all()
