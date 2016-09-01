#!flaskenv/bin/python
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
'''
Check database integrity for rules which cannot be easily enforced by
database constraints.
'''

from app import db, models

the_kids = db.session.query(models.Kid).all()

# ###################################################################
# Ensure that allowance sub-accounts and locations are accounted for
# 100%.
# ###################################################################
print "-------- Allowance checks any errors found will be seen below --------"
for eachkid in the_kids:
    allowances = db.session.query(models.Allowance).filter(
        models.Allowance.kid_id == eachkid.id).all()
    for allowance in allowances:
        msg = ''
        tot_a = 0
        tot_l = 0
        if eachkid.acct1_used is True and allowance.account1_perc is not None:
            tot_a += allowance.account1_perc
        if eachkid.acct2_used is True and allowance.account2_perc is not None:
            tot_a += allowance.account2_perc
        if eachkid.acct3_used is True and allowance.account3_perc is not None:
            tot_a += allowance.account3_perc
        if eachkid.acct4_used is True and allowance.account4_perc is not None:
            tot_a += allowance.account4_perc
        if eachkid.acct5_used is True and allowance.account5_perc is not None:
            tot_a += allowance.account5_perc
        if tot_a != 100:
            msg += "Account percent for kid %s allowance %s is %s\n"
            msg = msg % (eachkid.firstname, allowance.nickname, tot_a)

        if eachkid.location1_used is True and allowance.location1_perc \
                is not None:
            tot_l += allowance.location1_perc
        if eachkid.location2_used is True and allowance.location2_perc \
                is not None:
            tot_l += allowance.location2_perc
        if eachkid.location3_used is True and allowance.location3_perc \
                is not None:
            tot_l += allowance.location3_perc
        if eachkid.location4_used is True and allowance.location4_perc \
                is not None:
            tot_l += allowance.location4_perc
        if eachkid.location5_used is True and allowance.location5_perc \
                is not None:
            tot_l += allowance.location5_perc
        if eachkid.location6_used is True and allowance.location6_perc \
                is not None:
            tot_l += allowance.location6_perc
        if eachkid.location7_used is True and allowance.location7_perc \
                is not None:
            tot_l += allowance.location7_perc
        if tot_l != 100:
            msg += "Location percent for kid %s allowance %s is %s\n"
            msg = msg % (eachkid.firstname, allowance.nickname, tot_l)
        if len(msg) > 0:
            print msg
