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
from werkzeug.security import generate_password_hash, \
    check_password_hash
from app import db
from datetime import datetime, timedelta


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(128))
    isgoogle = db.Column(db.Boolean(), default=False)
    email = db.Column(db.String(120), index=True, unique=True)
    money_symbol = db.Column(db.String(2), default='$')
    pw_hash = db.Column(db.String(120))

    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return unicode(self.id)  # python 2
        except NameError:
            return str(self.id)  # python 3

    def __repr__(self):
        return '<User %r>' % (self.firstname)

    def set_password(self, password):
        self.pw_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.pw_hash, password)


class Kid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(128), index=True)
    animal1 = db.Column(db.String(128))
    animal2 = db.Column(db.String(128))
    animal3 = db.Column(db.String(128))
    animal4 = db.Column(db.String(128))
    parent_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    pw = db.Column(db.String(120))
    acct1_name = db.Column(db.String(120), default="Spending Money")
    acct2_name = db.Column(db.String(120))
    acct3_name = db.Column(db.String(120))
    acct4_name = db.Column(db.String(120))
    acct5_name = db.Column(db.String(120))
    acct1_used = db.Column(db.Boolean(), default=True)
    acct2_used = db.Column(db.Boolean(), default=False)
    acct3_used = db.Column(db.Boolean(), default=False)
    acct4_used = db.Column(db.Boolean(), default=False)
    acct5_used = db.Column(db.Boolean(), default=False)
    acct1_comment = db.Column(db.String(512))
    acct2_comment = db.Column(db.String(512))
    acct3_comment = db.Column(db.String(512))
    acct4_comment = db.Column(db.String(512))
    acct5_comment = db.Column(db.String(512))
    location1_name = db.Column(db.String(120), default="Parents Wallet")
    location2_name = db.Column(db.String(120))
    location3_name = db.Column(db.String(120))
    location4_name = db.Column(db.String(120))
    location5_name = db.Column(db.String(120))
    location6_name = db.Column(db.String(120))
    location7_name = db.Column(db.String(120))
    location1_used = db.Column(db.Boolean(), default=True)
    location2_used = db.Column(db.Boolean(), default=False)
    location3_used = db.Column(db.Boolean(), default=False)
    location4_used = db.Column(db.Boolean(), default=False)
    location5_used = db.Column(db.Boolean(), default=False)
    location6_used = db.Column(db.Boolean(), default=False)
    location7_used = db.Column(db.Boolean(), default=False)
    location1_comment = db.Column(db.String(512))
    location2_comment = db.Column(db.String(512))
    location3_comment = db.Column(db.String(512))
    location4_comment = db.Column(db.String(512))
    location5_comment = db.Column(db.String(512))
    location6_comment = db.Column(db.String(512))
    location7_comment = db.Column(db.String(512))
    __table_args__ = (db.UniqueConstraint('firstname', 'animal1',
                                          'animal2', name='_kid_login'),
                      db.CheckConstraint(
                        'acct1_used > 0 OR acct2_used > 0 OR acct3_used > 0' +
                        ' OR acct4_used > 0 OR acct5_used> 0 ',
                        name='at_least_one_acc'),
                      db.CheckConstraint(
                       'location1_used > 0 OR location2_used > 0 OR ' +
                       'location3_used > 0 OR ' +
                       'location4_used > 0 OR location5_used > 0 OR ' +
                       'location6_used > 0 OR location7_used > 0',
                       name='at_least_one_location'
                        )
                      )

    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return ('child', unicode(self.id))  # python 2
        except NameError:
            return ('child', str(self.id))  # python 3

    def __repr__(self):
        return '<User %r>' % (self.firstname)


class Allowance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kid_id = db.Column(db.Integer, db.ForeignKey('kid.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    creation_date = db.Column(db.DateTime, nullable=False)
    nickname = db.Column(db.String, default='allowance')
    account1_perc = db.Column(db.Float)
    account2_perc = db.Column(db.Float)
    account3_perc = db.Column(db.Float)
    account4_perc = db.Column(db.Float)
    account5_perc = db.Column(db.Float)
    location1_perc = db.Column(db.Float)
    location2_perc = db.Column(db.Float)
    location3_perc = db.Column(db.Float)
    location4_perc = db.Column(db.Float)
    location5_perc = db.Column(db.Float)
    location6_perc = db.Column(db.Float)
    location7_perc = db.Column(db.Float)
    last_ledger_update = db.Column(db.DateTime)
    __table_args__ = (
        db.CheckConstraint(
            '(account1_perc + account2_perc + account3_perc + account4_perc ' +
            '+ account5_perc) = 100', name='acc_100'),
        db.CheckConstraint(
            '(location1_perc + location2_perc + location3_perc + ' +
            'location4_perc + location5_perc + location6_perc + ' +
            'location7_perc) = 100', name='loc_100')
        )

    def __init__(self, kid_id, amount, nickname, account1_perc=0,
                 account2_perc=0, account3_perc=0, account4_perc=0,
                 account5_perc=0, location1_perc=0,
                 location2_perc=0, location3_perc=0, location4_perc=0,
                 location5_perc=0, location6_perc=0, location7_perc=0):
        self.kid_id = kid_id
        self.amount = amount
        self.nickname = nickname
        self.creation_date = datetime.utcnow()
        self.account1_perc = account1_perc
        self.account2_perc = account2_perc
        self.account3_perc = account3_perc
        self.account4_perc = account4_perc
        self.account5_perc = account5_perc
        self.location1_perc = location1_perc
        self.location2_perc = location2_perc
        self.location3_perc = location3_perc
        self.location4_perc = location4_perc
        self.location5_perc = location5_perc
        self.location6_perc = location6_perc
        self.location7_perc = location7_perc
        self.last_ledger_update = datetime.utcnow() - \
            timedelta(days=1)


class AllowanceDays(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payout_day = db.Column(db.Integer,)
    allowance_id = db.Column(db.Integer, db.ForeignKey('allowance.id'))
    __table_args__ = (
        db.UniqueConstraint('id', 'payout_day', name='_allowance'),
        db.CheckConstraint('payout_day < 29', name='cont_payout_day'))


class Ledger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kid_id = db.Column(db.Integer, db.ForeignKey('kid.id'), nullable=False)
    last_ledger_update = db.Column(db.DateTime, index=True,)
    adjusted_by_parent = db.Column(db.Boolean, nullable=False)
    adjuster_name = db.Column(db.String, nullable=False, default="not given")
    total_acc1 = db.Column(db.Integer, default=0)
    total_acc2 = db.Column(db.Integer, default=0)
    total_acc3 = db.Column(db.Integer, default=0)
    total_acc4 = db.Column(db.Integer, default=0)
    total_acc5 = db.Column(db.Integer, default=0)
    total_loc1 = db.Column(db.Integer, default=0)
    total_loc2 = db.Column(db.Integer, default=0)
    total_loc3 = db.Column(db.Integer, default=0)
    total_loc4 = db.Column(db.Integer, default=0)
    total_loc5 = db.Column(db.Integer, default=0)
    total_loc6 = db.Column(db.Integer, default=0)
    total_loc7 = db.Column(db.Integer, default=0)
    change_acc1 = db.Column(db.Integer, default=0)
    change_acc2 = db.Column(db.Integer, default=0)
    change_acc3 = db.Column(db.Integer, default=0)
    change_acc4 = db.Column(db.Integer, default=0)
    change_acc5 = db.Column(db.Integer, default=0)
    change_loc1 = db.Column(db.Integer, default=0)
    change_loc2 = db.Column(db.Integer, default=0)
    change_loc3 = db.Column(db.Integer, default=0)
    change_loc4 = db.Column(db.Integer, default=0)
    change_loc5 = db.Column(db.Integer, default=0)
    change_loc6 = db.Column(db.Integer, default=0)
    change_loc7 = db.Column(db.Integer, default=0)
    comment = db.Column(db.String,)

    def __str__(self):
        msg = "KID:%s, ADJUSTER_NAME:%s" % (self.kid_id, self.adjuster_name)
        msg += ", LAST_L_UPDT:%s \n" % self.last_ledger_update
        msg += "    TOTACC(%s,%s," % (self.total_acc1, self.total_acc2)
        msg += "%s,%s," % (self.total_acc3, self.total_acc4)
        msg += "%s)\n" % self.total_acc5
        msg += "    TOTLOC(%s,%s," % (self.total_loc1, self.total_loc2)
        msg += "%s,%s," % (self.total_loc3, self.total_loc4)
        msg += "%s,%s," % (self.total_loc5, self.total_loc6)
        msg += "%s)\n" % self.total_loc7
        msg += "    CHANGEACC(%s,%s," % (self.change_acc1, self.change_acc2)
        msg += "%s,%s," % (self.change_acc3, self.change_acc4)
        msg += "%s)\n" % self.change_acc5
        msg += "    CHANGELOC(%s,%s," % (self.change_loc1, self.change_loc2)
        msg += "%s,%s," % (self.change_loc3, self.change_loc4)
        msg += "%s,%s" % (self.change_loc5, self.change_loc6)
        msg += "%s)\n" % self.change_loc7
        return msg

    def __init__(self, kid_id, adjusted_by_parent, adjuster_name,
                 total_acc1=0, total_acc2=0, total_acc3=0,
                 total_acc4=0, total_acc5=0, total_loc1=0,
                 total_loc2=0, total_loc3=0, total_loc4=0,
                 total_loc5=0, total_loc6=0, total_loc7=0,
                 change_acc1=0, change_acc2=0, change_acc3=0,
                 change_acc4=0, change_acc5=0, change_loc1=0,
                 change_loc2=0, change_loc3=0, change_loc4=0,
                 change_loc5=0, change_loc6=0, change_loc7=0,
                 comment=''):
        self.kid_id = kid_id
        self.last_ledger_update = datetime.utcnow()
        self.adjusted_by_parent = adjusted_by_parent
        self.adjuster_name = adjuster_name
        self.total_acc1 = total_acc1
        self.total_acc2 = total_acc2
        self.total_acc3 = total_acc3
        self.total_acc4 = total_acc4
        self.total_acc5 = total_acc5
        self.total_loc1 = total_loc1
        self.total_loc2 = total_loc2
        self.total_loc3 = total_loc3
        self.total_loc4 = total_loc4
        self.total_loc5 = total_loc5
        self.total_loc6 = total_loc6
        self.total_loc7 = total_loc7
        self.change_acc1 = change_acc1
        self.change_acc2 = change_acc2
        self.change_acc3 = change_acc3
        self.change_acc4 = change_acc4
        self.change_acc5 = change_acc5
        self.change_loc1 = change_loc1
        self.change_loc2 = change_loc2
        self.change_loc3 = change_loc3
        self.change_loc4 = change_loc4
        self.change_loc5 = change_loc5
        self.change_loc6 = change_loc6
        self.change_loc7 = change_loc7
        self.comment = comment
