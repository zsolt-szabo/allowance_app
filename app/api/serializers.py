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
'''Turning positional database columns into JSON.

The schema is not changing, so the columns stay acct1..acct5 and
location1..location7. This module is the one place that flattening is
converted into arrays, and back.

Two decisions worth stating, because they are easy to get subtly wrong:

  * **Arrays carry their own index.** A bucket is emitted as
    ``{"index": 3, ...}`` rather than relying on array position. The
    position in the database IS the bucket's identity -- acct3 means the
    same sub-account across a kid's entire ledger history -- so a client
    that sorted or filtered an array could otherwise silently write to the
    wrong column.

  * **Slots are 1-based, array positions are 0-based.** Every conversion
    runs through ACCOUNT_SLOTS / LOCATION_SLOTS rather than open-coding
    the offset, because an off-by-one here is the likeliest brand-new bug
    this whole port can introduce. tests/test_serializers.py round-trips
    it.
'''
from app.domain import buckets


def _money(value):
    '''Amounts are floats in whole currency units, rounded to 2dp.

    Integer cents would be better but needs a schema change, which is out
    of scope for this port.
    '''
    return round(value or 0, 2)


def _isoformat(value):
    return value.isoformat() if value is not None else None


def account_buckets(kid):
    return [{'index': i,
             'name': buckets.account_name(kid, i),
             'active': buckets.account_used(kid, i),
             'comment': buckets.account_comment(kid, i)}
            for i in buckets.ACCOUNT_SLOTS]


def location_buckets(kid):
    return [{'index': j,
             'name': buckets.location_name(kid, j),
             'active': buckets.location_used(kid, j),
             'comment': buckets.location_comment(kid, j)}
            for j in buckets.LOCATION_SLOTS]


def kid_summary(kid, balance=None):
    '''Enough to list a kid and link to their screens.'''
    return {'id': kid.id,
            'firstname': kid.firstname,
            'loginAnimals': [kid.animal1, kid.animal2],
            'balance': _money(balance)}


def kid_detail(kid, include_password=False):
    '''The full child record.

    ``password`` is omitted unless explicitly asked for, and the caller
    must only ask when the actor is the owning parent. Kid.pw is stored in
    clear text so a parent can read it back to their child; that is a
    deliberate product decision, but it should not travel in every
    response.
    '''
    detail = {'id': kid.id,
              'firstname': kid.firstname,
              'loginAnimals': [kid.animal1, kid.animal2],
              'passwordAnimals': [kid.animal3, kid.animal4],
              'accounts': account_buckets(kid),
              'locations': location_buckets(kid)}
    if include_password:
        detail['password'] = kid.pw
    return detail


def allowance(row):
    '''One allowance, with its payout days and both percentage splits.'''
    days = getattr(row, 'DATES', None)
    return {'id': row.id,
            'kidId': row.kid_id,
            'nickname': row.nickname,
            'amount': _money(row.amount),
            'createdAt': _isoformat(row.creation_date),
            'payoutDays': sorted(days) if days is not None else [],
            'accountPercents': [getattr(row, 'account%s_perc' % i) or 0
                                for i in buckets.ACCOUNT_SLOTS],
            'locationPercents': [getattr(row, 'location%s_perc' % j) or 0
                                 for j in buckets.LOCATION_SLOTS]}


def ledger_entry(row):
    '''One ledger row: the deltas and the running totals after them.'''
    return {'id': row.id,
            'kidId': row.kid_id,
            'timestamp': _isoformat(row.last_ledger_update),
            'adjusterName': row.adjuster_name,
            'adjustedByParent': bool(row.adjusted_by_parent),
            'comment': row.comment,
            'accountTotals': [_money(v)
                              for v in buckets.account_totals(row)],
            'locationTotals': [_money(v)
                               for v in buckets.location_totals(row)],
            'accountChanges': [_money(v)
                               for v in buckets.account_changes(row)],
            'locationChanges': [_money(v)
                                for v in buckets.location_changes(row)]}


def cells_from_payload(cells):
    '''[{account, location, amount}] -> {(slot, slot): amount}.

    The wire format is sparse because most of the 5x7 grid is empty in any
    real transaction, and because a per-cell validation error needs an
    address to point at.
    '''
    return {(cell['account'], cell['location']): cell['amount']
            for cell in cells}


def percents_to_slots(values, slots):
    '''A dense percentage array -> {slot: value}, 1-based.'''
    return {slot: values[index] for index, slot in enumerate(slots)}
