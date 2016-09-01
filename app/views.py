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
from app import app, lm
from flask import g
import models
from lib import a_index
from lib import a_login
from lib import a_child_login
from lib import a_finance
from flask.ext.login import login_required


@lm.user_loader
def load_user(id):
    # TBD: tuple means child, this is not ideal
    # revisit this design  ('child', id)
    # Security Note: Since we are working with two
    # tables User/Kid, we need to ensure we never
    # accidentally take an ID from one table and retrieve
    # from another table (IE Kid logs in but a page thinks
    # its a parent).  This is protected by using two different
    # parameters with the g variable g.kid_id/g.user_id
    # Each page view will have to make determiniations
    # as to what to do when viewed as child or adult,
    # but the different variables will prevent accidental
    # viewing of other account information.
    print "load_user triggered, id is %s" % str(id)
    if type(id).__name__ == 'tuple':
        user = models.Kid.query.get(int(id[1]))
        g.is_child = True
        g.kid_id = user.id
    else:
        user = models.User.query.get(int(id))
    if not type(id).__name__ == 'tuple' and user is not None:
        g.user = user.email
        g.isgoogle = user.isgoogle
        g.user_id = user.id
        g.money_symbol = user.money_symbol
    return user


@app.route('/')
@app.route('/index')
def index():
    return a_index.process_view()


@app.route('/login', methods=['GET', 'POST'])
def login():
    return a_login.login()


@app.route('/child_login', methods=['GET', 'POST'])
def child_login():
    return a_child_login.login()


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    return a_login.logout()


@app.route('/google_signin', methods=['GET', 'POST'])
def do_google_token_signin():
    return a_login.do_google_token_signin()


@app.route('/register', methods=['GET', 'POST'])
def do_register():
    return a_login.register()


@app.route('/child_register1', methods=['GET', 'POST'])
@login_required
def do_child_register1():
    return a_child_login.register_child1()


@app.route('/allowance', methods=['GET', 'POST'])
@login_required
def do_allowance():
    return a_finance.allowances()


@app.route('/remove_allowance', methods=['GET'])
@login_required
def do_remove_allowance():
    return a_finance.remove_allowance()


@app.route('/parent_account_review', methods=['GET', 'POST'])
@login_required
def parent_account_review():
    return a_login.parent_account_review()


@app.route('/kid_manage', methods=['GET', 'POST'])
@login_required
def kid_account_review():
    return a_child_login.kid_account_review()


@app.route('/animals', methods=['GET'])
@login_required
def animals():
    return a_child_login.ajax_animals()


@app.route('/ledger', methods=['GET', 'POST'])
@login_required
def ledger():
    return a_finance.ledger()


@app.route('/delete_kid', methods=['GET', 'POST'])
@login_required
def delete_kid():
    return a_child_login.delete_kid()
