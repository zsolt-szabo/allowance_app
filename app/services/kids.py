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
from app.services import errors

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


def delete_kid(kid):
    '''Delete a child and everything hanging off them.

    Hand-rolled cascade, deepest first: allowance_days, then allowances
    and ledger, then the kid. The models declare bare ForeignKeys with no
    ondelete, so nothing happens automatically.
    '''
    from app import db

    allowances = models.Allowance.query.filter_by(kid_id=kid.id)
    for allowance in allowances.all():
        models.AllowanceDays.query.filter_by(
            allowance_id=allowance.id).delete()
    models.Ledger.query.filter_by(kid_id=kid.id).delete()
    allowances.delete()
    models.Kid.query.filter_by(id=kid.id).delete()
    db.session.commit()
    logger.info('Deleted kid %s and all their money history' % kid.id)


def login_is_taken(firstname, animal1, animal2, exclude_kid_id=None):
    '''Whether this identifying triple already belongs to a child.

    The triple is unique across the whole system, not per parent -- the
    _kid_login constraint on Kid enforces that -- so two families cannot
    both have a "whipper/rabbit/rabbit".
    '''
    query = models.Kid.query.filter(
        models.Kid.firstname == firstname,
        models.Kid.animal1 == animal1,
        models.Kid.animal2 == animal2)
    if exclude_kid_id is not None:
        query = query.filter(models.Kid.id != exclude_kid_id)
    return query.count() > 0


def _apply_buckets(kwargs, accounts, locations):
    '''Fold bucket definitions into Kid column keyword arguments.'''
    for bucket in accounts:
        slot = bucket['index']
        kwargs['acct%s_name' % slot] = bucket.get('name')
        kwargs['acct%s_used' % slot] = bool(bucket.get('active'))
        kwargs['acct%s_comment' % slot] = bucket.get('comment')
    for bucket in locations:
        slot = bucket['index']
        kwargs['location%s_name' % slot] = bucket.get('name')
        kwargs['location%s_used' % slot] = bool(bucket.get('active'))
        kwargs['location%s_comment' % slot] = bucket.get('comment')
    return kwargs


def create_kid(parent_id, firstname, password, animals, accounts, locations):
    '''Register a child.

    Params
    ------
    parent_id:  owner
    firstname:  the nickname half of the login
    password:   stored in clear text, deliberately -- a parent has to be
                able to read it back to their child
    animals:    (animal1, animal2, animal3, animal4); the first two
                identify, the last two are part of the password
    accounts:   [{index, name, active, comment}] for slots 1..5
    locations:  [{index, name, active, comment}] for slots 1..7
    '''
    from app import db

    animal1, animal2, animal3, animal4 = animals
    if login_is_taken(firstname, animal1, animal2):
        raise errors.Conflict(
            'Cannot register this login combination, '
            'Please try again with different user name',
            code='kid.login_taken')

    kwargs = _apply_buckets(
        dict(firstname=firstname, parent_id=parent_id, pw=password,
             animal1=animal1, animal2=animal2,
             animal3=animal3, animal4=animal4),
        accounts, locations)

    kid = models.Kid(**kwargs)
    db.session.add(kid)
    db.session.commit()
    logger.info('Registered kid %s for parent %s' % (kid.id, parent_id))
    return kid


def update_kid(kid, firstname=None, password=None, animals=None,
               accounts=None, locations=None):
    '''Change a child's credentials or buckets.

    Switching a bucket off redistributes any allowance percentage aimed at
    it; see redistribute_allowance. That happens here rather than in the
    caller so both UIs cannot drift.

    Returns (kid, orphaned) where orphaned lists allowance nicknames whose
    distribution could not be repaired and which the parent must recreate.
    '''
    from app import db

    if animals is not None:
        animal1, animal2, animal3, animal4 = animals
        if login_is_taken(firstname or kid.firstname, animal1, animal2,
                          exclude_kid_id=kid.id):
            raise errors.Conflict(
                'Cannot register this login combination, '
                'Please try again with different user name',
                code='kid.login_taken')
        kid.animal1, kid.animal2 = animal1, animal2
        kid.animal3, kid.animal4 = animal3, animal4

    if firstname is not None:
        kid.firstname = firstname
    if password is not None:
        kid.pw = password

    orphaned = []
    if accounts is not None or locations is not None:
        new_accounts = accounts if accounts is not None else [
            {'index': i, 'name': getattr(kid, 'acct%s_name' % i),
             'active': buckets.account_used(kid, i),
             'comment': getattr(kid, 'acct%s_comment' % i)}
            for i in buckets.ACCOUNT_SLOTS]
        new_locations = locations if locations is not None else [
            {'index': j, 'name': getattr(kid, 'location%s_name' % j),
             'active': buckets.location_used(kid, j),
             'comment': getattr(kid, 'location%s_comment' % j)}
            for j in buckets.LOCATION_SLOTS]

        active_accounts = [b['index'] for b in new_accounts if b.get('active')]
        active_locations = [b['index'] for b in new_locations
                            if b.get('active')]

        #  Repair the allowances BEFORE the buckets change, so the
        #  percentages are computed against the allowance as it stands.
        for allowance in models.Allowance.query.filter_by(
                kid_id=kid.id).all():
            update_dict, acc_orphan, loc_orphan = redistribute_allowance(
                allowance, active_accounts, active_locations)
            if acc_orphan or loc_orphan:
                orphaned.append(allowance.nickname)
                continue
            if update_dict:
                models.Allowance.query.filter_by(
                    id=allowance.id).update(update_dict)

        kwargs = _apply_buckets({}, new_accounts, new_locations)
        for key, value in kwargs.items():
            setattr(kid, key, value)

    db.session.commit()
    return kid, orphaned
