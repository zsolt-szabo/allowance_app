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
'''Child accounts: their credentials, and their buckets.

The interesting logic here is what happens to an existing allowance when a
parent switches off a sub-account or money location it still pays into.
The allowance's percentages have to keep totalling exactly 100 -- the
acc_100 / loc_100 CheckConstraints enforce that at the database -- so the
closed bucket's share is redistributed.

Extracted from app/lib/a_child_login.py. The arithmetic is unchanged and
is pinned by tests/characterization/test_redistribution.py.
'''
import logging

from app import models
from app.domain import animals
from app.domain import buckets

logger = logging.getLogger(__name__)


def available_animal_pairs(firstname):
    '''(animal1, animal2) pairs still free for this nickname.

    A child is identified by (firstname, animal1, animal2), unique across
    the whole system, so registration needs to offer alternatives when a
    pair is taken.

    NOTE: this answers for any nickname, not just the caller's own kids, so
    it discloses which child logins exist. Preserved as-is; worth revisiting
    when this becomes a JSON endpoint.
    '''
    taken = {(kid.animal1, kid.animal2)
             for kid in models.Kid.query.filter(
                 models.Kid.firstname == firstname).all()}
    return animals.image_combo_set - taken


def redistribute_allowance(allowance, active_accounts, active_locations):
    '''Work out an allowance's new percentages after buckets are switched off.

    Params
    ------
    allowance:         models.Allowance to adjust
    active_accounts:   slot numbers that will remain active, 1..5
    active_locations:  slot numbers that will remain active, 1..7

    Returns (update_dict, account_orphaned, location_orphaned). The dict is
    the column update to apply; the flags say an axis could not be fixed
    because no funded bucket survived, and the caller must tell the parent
    to recreate the allowance.

    The rules, from the original's own comment:
      1. share the closed bucket's percentage across buckets that are still
         active AND non-zero;
      2. leave zero-percentage buckets alone -- they are taken to be
         deliberately ignored;
      3. this cannot work when the allowance only funded one bucket.

    Every surviving bucket after the first gets an even round(diff / n, 2),
    and the FIRST one absorbs `diff - amount_added`. That absorber is what
    makes the total land on exactly 100 rather than 99.99, which the
    CheckConstraint would reject.
    '''
    update_dict = {}

    tot_a = 0
    a_to_adjust = []
    for i in buckets.ACCOUNT_SLOTS:
        accX_per = getattr(allowance, 'account%s_perc' % i)
        if accX_per is not None and i in active_accounts and accX_per != 0:
            a_to_adjust.append(i)
            tot_a += accX_per
        else:
            update_dict["account%s_perc" % i] = 0

    tot_l = 0
    l_to_adjust = []
    for i in buckets.LOCATION_SLOTS:
        locX_per = getattr(allowance, 'location%s_perc' % i)
        if locX_per is not None and i in active_locations and locX_per != 0:
            l_to_adjust.append(i)
            tot_l += locX_per
        else:
            update_dict["location%s_perc" % i] = 0

    account_orphaned = False
    if tot_a != 100 and len(a_to_adjust) > 0:
        _spread(update_dict, allowance, 'account%s_perc', a_to_adjust, tot_a)
    elif tot_a != 100 and len(a_to_adjust) == 0:
        account_orphaned = True

    location_orphaned = False
    if tot_l != 100 and len(l_to_adjust) > 0:
        _spread(update_dict, allowance, 'location%s_perc', l_to_adjust, tot_l)
    elif tot_l != 100 and len(l_to_adjust) == 0:
        location_orphaned = True

    needs_update = tot_a != 100 or tot_l != 100
    if not needs_update:
        update_dict = {}
    return update_dict, account_orphaned, location_orphaned


def _spread(update_dict, allowance, key_template, to_adjust, current_total):
    '''Even split across survivors, with the first absorbing the remainder.'''
    diff = 100 - current_total
    split = round(diff / float(len(to_adjust)), 2)
    amount_added = 0
    for i in to_adjust[1:]:
        thekey = key_template % i
        sv = getattr(allowance, thekey)  # Start Value
        update_dict.setdefault(thekey, sv)
        update_dict[thekey] += split
        amount_added += split
    # Ensure we are absolutely 100% not 99.9
    thekey = key_template % to_adjust[0]
    sv = getattr(allowance, thekey)  # Start Value
    update_dict.setdefault(thekey, sv)
    update_dict[thekey] += (diff - amount_added)


def allowances_using_buckets(kid):
    '''{bucket_key: "nickname, nickname, "} for the kid's settings screen.

    Tells a parent which allowances pay into each bucket, so they can see
    what deactivating one would disturb.
    '''
    used = {}
    for allowance in models.Allowance.query.filter_by(kid_id=kid.id).all():
        for i in buckets.ACCOUNT_SLOTS:
            key = 'acct%s_name' % i
            used.setdefault(key, '')
            perc = getattr(allowance, 'account%s_perc' % i)
            if perc is not None and perc != 0:
                used[key] += '%s, ' % str(allowance.nickname)
        for j in buckets.LOCATION_SLOTS:
            key = 'location%s_name' % j
            used.setdefault(key, '')
            perc = getattr(allowance, 'location%s_perc' % j)
            if perc is not None and perc != 0:
                used[key] += '%s, ' % str(allowance.nickname)
    return used
