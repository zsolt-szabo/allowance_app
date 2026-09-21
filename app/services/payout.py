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
'''The allowance payout engine.

Moved here VERBATIM from app/lib/a_index.py. Not one arithmetic expression
was retyped: this is the most valuable and least replaceable code in the
repository, and the characterization tests in
tests/characterization/test_payout_math.py pin its behaviour -- including
the parts that are wrong -- precisely so that moving it can be shown to
have changed nothing.

Two behaviours worth knowing before touching anything here:

  * **Remainder absorption.** Accounts 1-4 and locations 1-6 are computed
    from their percentages; account 5 and location 7 receive whatever is
    left over. That is what stops the sub-account axis and the location
    axis disagreeing. It only works for residue that lands in those two
    slots, which is why percentages that do not divide into whole cents can
    still break the invariant.

  * **Catch-up.** The engine walks every calendar day since the allowance's
    last_ledger_update watermark, so a job that has not run for a month
    pays out each missed day retroactively, one ledger row each. Successive
    rows in one run chain off the previous *uncommitted* row.

Known defects pinned by test_KNOWN_BUG_* tests and scheduled for Stage 5:
update_occurred is a batch-wide flag never reset per allowance; duplicate
(allowance_id, payout_day) rows pay twice; this runs on every dashboard
load as well as from cron, with no lock.
'''
import logging
from datetime import date, datetime, timedelta, timezone

from app import db
from app import models

logger = logging.getLogger(__name__)


def run_payouts():
    '''Process every allowance in the system.

    Exactly the query allowance_payout_cron.py has always run, kept here so
    the cron script and the dashboard cannot drift apart.
    '''
    rows = db.session.query(models.Allowance, models.AllowanceDays).filter(
        models.Allowance.id == models.AllowanceDays.allowance_id).all()
    return check_and_update_allowances(rows)


def check_and_update_allowances(allowances=[]):
    '''
    returns True if any allowances were added to the ledger, otherwise
        returns false.
    Date Comparison logic.  Allowance has a last_ledger_update field.
      When determining if number of days since we last updated, we strip
      out the time field from today as well as the last update
    Params
    ------
    allowances:  Array of tuples (models.Allowance, models.AllowanceDays)
    '''
    if type(allowances).__name__ != 'list':
        raise Exception("Argument must be of type 'list'")
    msg = ''
    for each in allowances:
        msg += "All_ID: %s,  ALL_Day_ID: %s\n" % (each[0].id, each[1].id)
    logger.debug(msg)
    today_now = datetime.now(timezone.utc)
    today = date(today_now.year, today_now.month, today_now.day)
    update_occurred = False

    if len(allowances) > 0:
        last_allow_id = None
        for each_payout in allowances:
            a = each_payout[0]  # models.Allowance
            d = each_payout[1]  # models.AllowanceDays
            if last_allow_id != a.id and last_allow_id is not None:
                #  Commit all changes for the last allowance entered
                msg = "ID switched from %s " % last_allow_id
                msg += "to %s so we are commiting" % a.id
                logger.debug(msg)
                update_allow_ts = models.Allowance.query.filter_by(
                    id=last_allow_id).first()
                update_allow_ts.last_ledger_update = today
                db.session.commit()

                ll = models.Ledger.query.filter(
                    models.Ledger.kid_id == a.kid_id). \
                    order_by(models.Ledger.id.desc()).first()

                last_update = date(
                    a.last_ledger_update.year, a.last_ledger_update.month,
                    a.last_ledger_update.day)
                day_count = today - last_update
                day_array = range(1, day_count.days + 1)
                last_allow_id = a.id

            elif last_allow_id is None:
                last_allow_id = a.id
                ll = models.Ledger.query.filter(
                    models.Ledger.kid_id == a.kid_id). \
                    order_by(models.Ledger.id.desc()).first()
                last_update = date(
                    a.last_ledger_update.year, a.last_ledger_update.month,
                    a.last_ledger_update.day)
                day_count = today - last_update
                day_array = range(1, day_count.days + 1)

            class fakeLedger:
                def __init__(self):
                    self.total_acc1 = 0
                    self.total_acc2 = 0
                    self.total_acc3 = 0
                    self.total_acc4 = 0
                    self.total_acc5 = 0
                    self.total_loc1 = 0
                    self.total_loc2 = 0
                    self.total_loc3 = 0
                    self.total_loc4 = 0
                    self.total_loc5 = 0
                    self.total_loc6 = 0
                    self.total_loc7 = 0
            if ll is None:
                ll = fakeLedger()

            def r(n):
                '''Shortcut for rounding to two digits'''
                return round(n, 2)

            # Update allowance data to be committed by walking from last
            # day updated until today
            for day in day_array:
                each_date = last_update + timedelta(days=day)
                if each_date.day == d.payout_day:
                    comment = "Payout for '%s' date: %s" % \
                        (a.nickname, each_date.strftime("%Y-%m-%d"))
                    # Remainder variables used to ensure we don't have
                    # rounding disconnects between account $$ and location $$
                    remainder_a = \
                        a.amount - ((a.account1_perc + a.account2_perc +
                                     a.account3_perc +
                                     a.account4_perc) / 100.0 * a.amount)
                    remainder_l = \
                        a.amount - ((a.location1_perc + a.location2_perc +
                                     a.location3_perc + a.location4_perc +
                                     a.location5_perc + a.location6_perc) /
                                    100.0 * a.amount)
                    msg = "acc5 to add: %s" % remainder_a
                    msg += "   location7 to add %s" % remainder_l
                    logger.debug(msg)

                    ledge_entry = models.Ledger(
                        kid_id=a.kid_id, adjusted_by_parent=True,
                        adjuster_name='ALLOWANCE',

                        total_acc1=r(ll.total_acc1 + a.amount *
                                     a.account1_perc / 100.0),
                        change_acc1=r(a.amount * a.account1_perc / 100.0),
                        total_acc2=r(ll.total_acc2 + a.amount *
                                     a.account2_perc / 100.0),
                        change_acc2=r(a.amount * a.account2_perc / 100.0),
                        total_acc3=r(ll.total_acc3 + a.amount *
                                     a.account3_perc / 100.0),
                        change_acc3=r(a.amount * a.account3_perc / 100.0),
                        total_acc4=r(ll.total_acc4 + a.amount *
                                     a.account4_perc / 100.0),
                        change_acc4=r(a.amount * a.account4_perc / 100.0),

                        total_acc5=r(ll.total_acc5 + remainder_a),
                        change_acc5=r(remainder_a),

                        total_loc1=r(
                            ll.total_loc1 + a.amount * a.location1_perc /
                            100.0),
                        change_loc1=r(a.amount * a.location1_perc /
                                      100.0),
                        total_loc2=r(ll.total_loc2 + a.amount *
                                     a.location2_perc / 100.0),
                        change_loc2=r(a.amount * a.location2_perc / 100.0),
                        total_loc3=r(ll.total_loc3 + a.amount *
                                     a.location3_perc / 100.0),
                        change_loc3=r(a.amount * a.location3_perc / 100.0),
                        total_loc4=r(ll.total_loc4 + a.amount *
                                     a.location4_perc / 100.0),
                        change_loc4=r(a.amount * a.location4_perc / 100.0),
                        total_loc5=r(ll.total_loc5 + a.amount *
                                     a.location5_perc / 100.0),
                        change_loc5=r(a.amount * a.location5_perc / 100.0),
                        total_loc6=r(
                            ll.total_loc6 + a.amount * a.location6_perc /
                            100.0),
                        change_loc6=r(a.amount * a.location6_perc /
                                      100.0),

                        total_loc7=r(ll.total_loc7 + remainder_l),
                        change_loc7=r(remainder_l),
                        comment=comment)
                    ll = ledge_entry  # We cannot query our database again for
                    # ll because we have not commited, so
                    # use the modified value
                    logger.debug(ll)
                    db.session.add(ledge_entry)
                    update_occurred = True
            #  Final Commit for the last allowance entered
            # TODO, we used to update this field regardless if an update
            # occurred.  This created a bug where the last check was
            # less than 24 hours from the next check, thus the check would
            # not happen for the next day even if it needed a payout since
            # < 24 is not one day.  I think I have fixed this issue by only
            # working with dates instead of datetimes, but for now, I will
            # not remove the update_occurred check.  This results in us
            # needlessly looping over all days since last payout which could
            # result in performance issues.  This shall be revisited once
            # data has been collected.
            if update_occurred is True:
                msg = "Final allowance commit for id %s" % a.id
                update_allow_ts = models.Allowance.query.filter_by(
                    id=a.id).first()
                update_allow_ts.last_ledger_update = datetime.combine(
                    today, datetime.min.time())
                db.session.commit()
        return update_occurred
