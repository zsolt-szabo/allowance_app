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
'''The two axes a kid's money is tracked on.

Every kid's money is described twice over, and the two descriptions must
always total the same amount:

  * 5 **sub-accounts** (``acct1..acct5``) -- what the money is *for*
    (Spending / Savings / Charity).  This is how the app does savings goals;
    there is no separate Goal model.
  * 7 **locations** (``location1..location7``) -- where the money physically
    *is* (a wallet, a piggy bank, a gift card).

The database columns are positional, and **the position is the identity**:
``acct3`` means the same sub-account across the whole of a kid's ledger
history.  So these slot numbers are not an implementation detail to be tidied
away -- they are the primary key of a bucket.  Everything here is 1-based to
match the column names.

Slot 5 (accounts) and slot 7 (locations) carry an extra responsibility: the
allowance payout engine gives them the rounding remainder so the two axes
cannot drift apart.  See app/lib/a_index.py.
'''

#: 1-based sub-account slots, in column order.
ACCOUNT_SLOTS = tuple(range(1, 6))

#: 1-based money-location slots, in column order.
LOCATION_SLOTS = tuple(range(1, 8))

#: The slots that absorb the payout rounding remainder.
ACCOUNT_REMAINDER_SLOT = ACCOUNT_SLOTS[-1]
LOCATION_REMAINDER_SLOT = LOCATION_SLOTS[-1]


def account_name(kid, slot):
    return getattr(kid, 'acct%s_name' % slot)


def account_used(kid, slot):
    return bool(getattr(kid, 'acct%s_used' % slot))


def account_comment(kid, slot):
    return getattr(kid, 'acct%s_comment' % slot)


def location_name(kid, slot):
    return getattr(kid, 'location%s_name' % slot)


def location_used(kid, slot):
    return bool(getattr(kid, 'location%s_used' % slot))


def location_comment(kid, slot):
    return getattr(kid, 'location%s_comment' % slot)


def active_accounts(kid):
    '''Slot numbers of the sub-accounts the parent has switched on.'''
    return [i for i in ACCOUNT_SLOTS if account_used(kid, i)]


def active_locations(kid):
    '''Slot numbers of the money locations the parent has switched on.'''
    return [j for j in LOCATION_SLOTS if location_used(kid, j)]


def account_totals(ledger_row):
    '''Running balance per sub-account, in slot order.'''
    return [getattr(ledger_row, 'total_acc%s' % i) or 0
            for i in ACCOUNT_SLOTS]


def location_totals(ledger_row):
    '''Running balance per money location, in slot order.'''
    return [getattr(ledger_row, 'total_loc%s' % j) or 0
            for j in LOCATION_SLOTS]


def account_changes(ledger_row):
    '''This entry's delta per sub-account, in slot order.'''
    return [getattr(ledger_row, 'change_acc%s' % i) or 0
            for i in ACCOUNT_SLOTS]


def location_changes(ledger_row):
    '''This entry's delta per money location, in slot order.'''
    return [getattr(ledger_row, 'change_loc%s' % j) or 0
            for j in LOCATION_SLOTS]


def grand_total(ledger_row):
    '''Total money the kid has, per the sub-account axis.

    Matches what the app displays today: a_finance sums the *account* totals
    and ignores the location totals, the two being equal by construction.
    '''
    return round(sum(account_totals(ledger_row)), 2)


def axes_agree(ledger_row):
    '''Whether this row satisfies the invariant the model depends on.

    Never asserted anywhere in the application, and violated on real data --
    see scripts/verify_prod_snapshot.py.
    '''
    return (round(sum(account_totals(ledger_row)), 2) ==
            round(sum(location_totals(ledger_row)), 2))
