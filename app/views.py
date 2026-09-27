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
from app import db
from flask import g
from app import models
from app import session_ids
from app.lib import a_index
from app.lib import a_login
from app.lib import a_child_login
from app.lib import a_finance
from flask_login import login_required
from flask import render_template
import logging


logger = logging.getLogger(__name__)


def load_user(id):
    """Resolve a stored session id back to a parent or a child.

    Security note, inherited from the original and still the point of this
    function: two tables act as identities, so an id must never be looked
    up against the wrong one. The kind is now carried explicitly in the
    stored value (see app/session_ids.py) instead of being inferred from
    its Python type, and the per-request context still uses two separate
    names -- g.user_id for a parent, g.kid_id for a child -- so a child id
    cannot be mistaken for a parent id downstream.

    A failure here returns None, i.e. anonymous, rather than raising.
    """
    logger.info("load_user triggered, id is %s" % str(id))
    kind, row_id = session_ids.parse(id)
    if kind is None:
        logger.warning("Unusable session id %r; treating as anonymous" % (id,))
        return None

    try:
        if kind == session_ids.CHILD:
            user = db.session.get(models.Kid, row_id)
            if user is None:
                return None
            g.is_child = True
            g.kid_id = user.id
            return user

        user = db.session.get(models.User, row_id)
        if user is None:
            return None
        g.user = user.email
        g.isgoogle = user.isgoogle
        g.user_id = user.id
        g.money_symbol = user.money_symbol
        return user
    except Exception:
        logger.exception("User loading failed")
        return None


def index():
    return a_index.process_view()


def login():
    return a_login.login()


def child_login():
    return a_child_login.login()


def support_login():
    return a_login.support_login()


def logout():
    return a_login.logout()


def do_google_token_signin():
    return a_login.do_google_token_signin()


def do_register():
    return a_login.register()


@login_required
def do_child_register1():
    return a_child_login.register_child1()


@login_required
def do_allowance():
    return a_finance.allowances()


@login_required
def do_remove_allowance():
    return a_finance.remove_allowance()


@login_required
def parent_account_review():
    return a_login.parent_account_review()


@login_required
def kid_account_review():
    return a_child_login.kid_account_review()


@login_required
def animals():
    return a_child_login.ajax_animals()


@login_required
def ledger():
    return a_finance.ledger()


@login_required
def delete_kid():
    return a_child_login.delete_kid()


@login_required
def delete_user():
    return a_login.delete_user()


def help():
    return render_template('help.html')

def bodi():
    return render_template('bodi.html')


#  (url rule, endpoint name, view, methods). Order and endpoint
#  names are load-bearing: templates and redirects address these
#  by name.
_ROUTES = (
    ('/', 'index', index, None),
    ('/index', 'index', index, None),
    ('/login', 'login', login, ('GET', 'POST')),
    ('/child_login', 'child_login', child_login, ('GET', 'POST')),
    ('/support', 'support_login', support_login, ('GET',)),
    ('/logout', 'logout', logout, ('GET', 'POST')),
    ('/google_signin', 'do_google_token_signin',
     do_google_token_signin, ('GET', 'POST')),
    ('/register', 'do_register', do_register, ('GET', 'POST')),
    ('/child_register1', 'do_child_register1',
     do_child_register1, ('GET', 'POST')),
    ('/allowance', 'do_allowance', do_allowance, ('GET', 'POST')),
    ('/remove_allowance', 'do_remove_allowance',
     do_remove_allowance, ('GET',)),
    ('/parent_account_review', 'parent_account_review',
     parent_account_review, ('GET', 'POST')),
    ('/kid_manage', 'kid_account_review', kid_account_review, ('GET', 'POST')),
    ('/animals', 'animals', animals, ('GET',)),
    ('/ledger', 'ledger', ledger, ('GET', 'POST')),
    ('/delete_kid', 'delete_kid', delete_kid, ('GET', 'POST')),
    ('/delete_account', 'delete_user', delete_user, ('GET', 'POST')),
    ('/help', 'help', help, None),
    ('/bodi', 'bodi', bodi, None),
)


def init_app(app, login_manager):
    '''Attach the Jinja routes and the user loader to an application.

    Registration goes through add_url_rule rather than @app.route so this
    module can be imported before an application exists -- which is what
    lets create_app() work at all. Endpoint names are the view function
    names, exactly as the decorators produced, so every url_for() call in
    the lib layer and in the templates keeps working untouched.
    '''
    login_manager.user_loader(load_user)
    for rule, endpoint, view, methods in _ROUTES:
        if methods is None:
            app.add_url_rule(rule, endpoint, view)
        else:
            app.add_url_rule(rule, endpoint, view, methods=list(methods))
