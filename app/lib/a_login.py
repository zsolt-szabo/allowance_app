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
import config
import app
from app import forms
from app import models
from app import db
from app import support
from app.services import captcha
from app.services import parents
from app.services import errors
from flask_login import login_user
from flask_login import logout_user
from flask import g
from flask import redirect
from flask import url_for
import random
import requests

from flask import render_template, request, session, flash
import logging

logger = logging.getLogger(__name__)


login_manager = app.lm

goog_pw = config.GOOG_PW


#  The captcha generator moved to app/services/captcha.py. Re-exported so
#  the register handler keeps one name for it.
get_captcha = captcha.get_captcha


def login():
    form = forms.LoginForm()
    g.force_google_logout = session.pop('force_google_logout', None)
    if request.method == "POST" and form.validate_on_submit():
        #  THIS SHOULD BE THE ONLY PLACE WE ALLOW LOGIN PASSWORD FOR ADULT
        #  Support staff no longer log in with a shared master password;
        #  see app/support.py and scripts/support_login.py.
        #
        #  parents.authenticate gives the same answer for "no such email"
        #  and "wrong password", so the login form cannot be used to find
        #  out which addresses have accounts.
        try:
            user = parents.authenticate(form.email.data, form.password.data)
        except errors.DomainError as exc:
            flash('ERROR: ' + exc.message)
            # greturn redirect(request.args.get('next') or url_for('index'))
            return render_template('login.html',
                                   title='Sign In',
                                   form=form), 401

        login_user(user)
        g.user = user.email
        g.isgoogle = user.isgoogle
        g.user_id = user.id
        g.money_symbol = user.money_symbol
        return redirect(url_for('index'))

    return render_template('login.html',
                           title='Sign In',
                           form=form,
                           enable_google=config.ENABLE_GOOGLE_LOGIN)


def parent_account_review():
    form = forms.AccountUpdate()
    user_list = []
    if hasattr(g, 'user_id'):
        user_list = models.User.query.filter(models.User.id == g.user_id).all()
    # If we can't get user, we cannot update
    if len(user_list) == 0:
        flash('User was not found are you logged in?')
        return render_template(
            'index.html', title='Home', user=user_list[0].firstname), 401
    # ##########################
    # POST
    # ##########################
    if request.method == "POST":
        email = form.email.data
        password1 = form.password1.data
        password2 = form.password2.data
        firstname = form.firstname.data
        money_symbol = form.money_symbol.data
        if (user_list[0].email != form.email.data or len(password1)) > 0 \
                and g.isgoogle:
            flash('ERROR: Cannot change email or password for google account')
            return render_template('register.html',
                                   title='Account',
                                   form=form,
                                   nocap=True), 401
        # We cannot force google user to sign in so we don't double check
        # The safety mechanism for the google user is they are also unable
        # to change their email address or google password.
        if not g.isgoogle and \
                not user_list[0].check_password(form.oldpassword.data):
            flash("ERROR: original password did not match")
            return redirect(url_for('parent_account_review'))

        # We should never be here
        if len(user_list) > 1:
            logger.warning("Alert, query for email  %s " % email +
                           "returns more than one set of records")

        # Passwords don't match
        if password1 != password2:
            flash('ERROR: Passwords did not match')
            return render_template('register.html',
                                   title='Account',
                                   form=form,
                                   nocap=True), 401
        if form.validate_on_submit():
            if g.user_id == config.ANON_C:
                update_dict = dict(money_symbol=money_symbol,
                                   firstname=firstname)
            else:
                update_dict = dict(email=email,
                                   money_symbol=money_symbol,
                                   firstname=firstname)
            models.User.query.filter_by(
                id=g.user_id).update(update_dict)
            db.session.commit()

            if len(password1) > 0 and not g.isgoogle and \
                    g.user_id != config.ANON_C:
                update_user = models.User.query.filter_by(
                    id=g.user_id)
                update_user[0].set_password(password1)
                db.session.commit()
            flash('User info updated')
            return redirect(url_for('index'))
        else:
            for e_field in form.errors.keys():
                msglist = ''
                for emsg in form.errors[e_field]:
                    msglist += emsg + ", "
                flash('ERROR:(%s) %s' % (e_field, msglist[:-2]))
            return render_template('register.html',
                                   title='Account',
                                   form=form,
                                   nocap=True), 401
    else:
        form.email.data = user_list[0].email
        form.firstname.data = user_list[0].firstname
        form.money_symbol.data = user_list[0].money_symbol
        for e_field in form.errors.keys():
            msglist = ''
            for emsg in form.errors[e_field]:
                msglist += emsg + ", "
            flash('ERROR:(%s) %s' % (e_field, msglist[:-2]))
        return render_template('register.html',
                               title='Account',
                               form=form,
                               nocap=True), 401


def support_login():
    '''Spend a short-lived support token minted by scripts/support_login.py.

    Replaces the old shared master password: this grants access to exactly one
    account, expires, and is logged.  The session is flagged so base.html shows
    the red TECH SUPPORT banner, exactly as before.
    '''
    token = request.args.get('t') or request.form.get('t')
    try:
        payload = support.consume_support_token(token)
    except support.SupportTokenError as exc:
        logger.warning('Rejected support token: %s' % exc)
        flash('ERROR: %s' % exc)
        return redirect(url_for('login'))

    user = db.session.get(models.User, payload['user_id'])
    if user is None or user.email != payload.get('email'):
        logger.warning(
            'Support token for user id %s no longer matches an account'
            % payload.get('user_id'))
        flash('ERROR: Support token does not match an existing account')
        return redirect(url_for('login'))

    login_user(user)
    g.user = user.email
    g.isgoogle = user.isgoogle
    g.user_id = user.id
    g.money_symbol = user.money_symbol
    session['TechSupport'] = True
    logger.warning(
        'SUPPORT LOGIN: entered account id %s (%s) via support token'
        % (user.id, user.email))
    return redirect(url_for('index'))


def logout():
    logout_user()
    g.user = None
    g.isgoogle = False
    if 'TechSupport' in session:
        del session['TechSupport']
    return redirect(url_for('index'))


def do_google_token_signin():
    '''Means user is signing in with google, google javascript will post the
       following information.
    '''
    traits = ['id_token', 'given_name', 'family_name', 'image_url', 'email']
    google_log = "GOOGLE LOGIN:\n"
    for each in traits:
        if each in request.form:
            google_log += each + ':' + request.form[each] + "\n"
    logger.info(google_log)
    check = None
    if 'id_token' in request.form:
        check = requests.get(
            'https://' +
            'www.googleapis.com/oauth2/v3/tokeninfo?id_token=%s' %
            request.form['id_token'])
    # Check from google that this token is legit.
    if check is not None and check.status_code == 200:
        user_list = models.User.query.filter(
            models.User.email == request.form['email']).all()
        if len(user_list) > 0:
            if user_list[0].isgoogle is True:
                user = user_list[0]
                login_user(user)
                g.user = user.email
                g.isgoogle = user.isgoogle
                g.user_id = user.id
                g.money_symbol = user.money_symbol
                logger.info('Logged in google user %s' %
                            user_list[0].email)
            else:
                msg = "ERROR:  %s uses a standard login " % request.form[each]
                msg += "NOT google authentication, please use standard "
                msg += "login form"
                flash(msg)
                logout_user()
                g.user = None
                session['force_google_logout'] = True
        else:
            user = models.User(email=request.form['email'],
                               firstname=request.form['given_name'],
                               isgoogle=True)
            # Google user will get an internal password, but we will make
            # it tough to guess
            suffix = random.randint(1000, 10000)
            user.set_password(goog_pw + str(suffix))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            g.user = user.email
            g.isgoogle = user.isgoogle
            g.user_id = user.id
            g.money_symbol = user.money_symbol
            logger.info('Created new google user %s in the system' %
                        user.email)

    return "google user logged in"


def register():
    form = forms.Register()
    # ##########################
    # POST
    # ##########################
    if request.method == "POST":
        cap_answer = session.pop('cap_solution', None)
        email = form.email.data
        password1 = form.password1.data
        password2 = form.password2.data
        firstname = form.firstname.data
        money_symbol = form.money_symbol.data
        user_list = models.User.query.filter(models.User.email == email).all()

        # Attempt to register existing user
        if len(user_list) > 0:
            flash('Cannot register this email, ' +
                  'if you own it you can attempt to recover')
            return render_template(
                'index.html', title='Home', user=user_list[0].firstname), 401

        # We should never be here
        if len(user_list) > 1:
            logger.warning("Alert, query for email  %s " % email +
                           "returns more than one set of records")

        # Passwords don't match
        if password1 != password2:
            flash('ERROR: Passwords did not match')
            cap = get_captcha()
            form.captcha.data = None
            session['cap_solution'] = cap.solution
            return render_template('register.html',
                                   title='Register',
                                   form=form,
                                   cap=cap), 401
        if form.captcha.data != str(cap_answer).replace(' ', ''):
            #  This used to print the submitted value and the expected
            #  answer to stdout on every failed captcha.
            logger.info('Captcha mismatch on registration attempt')
            flash('ERROR:  Captcha values did not match')
            cap = get_captcha()
            form.captcha.data = None
            session['cap_solution'] = cap.solution
            return render_template('register.html',
                                   title='Register',
                                   form=form,
                                   cap=cap), 401
        # ########################################
        # SUCCESS: register user validation passes
        if form.validate_on_submit():
            user = parents.create(email=email, firstname=firstname,
                                  password=password1,
                                  money_symbol=money_symbol)
            login_user(user)
            g.user = user.email
            g.isgoogle = False
            g.user_id = user.id
            g.money_symbol = user.money_symbol

            return render_template(
                'index.html', title='Home',
                name=user.firstname, total_owed=0,
                monthly_outlay=0)
        # ########################################
        # FAILED: validation failed, give feedback
        else:
            for e_field in form.errors.keys():
                msglist = ''
                for emsg in form.errors[e_field]:
                    msglist += emsg + ", "
                flash('ERROR:(%s) %s' % (e_field, msglist[:-2]))
            cap = get_captcha()
            form.captcha.data = None
            session['cap_solution'] = cap.solution
            return render_template('register.html',
                                   title='Sign In',
                                   form=form,
                                   cap=cap), 401

        logger.warning("Alert, we should not be here: 2546")
    # ##########################
    # GET
    # ##########################
    else:
        cap = get_captcha()
        session['cap_solution'] = cap.solution
        return render_template('register.html',
                               title='Sign In',
                               form=form,
                               cap=cap)


def delete_user():
    if g.user_id == config.ANON_C:
        flash(
            "ERROR: Come on!  Did you want to delete the evaluation user?")
        return redirect(url_for('index'))
    form = forms.UserDelete()
    user_query = models.User.query.filter_by(id=g.user_id)
    user_list = user_query.all()

    if request.method == "POST":
        if form.validate_on_submit():
            if form.really_means_it.data is None or \
                    form.really_means_it.data is False and \
                    len(user_list) > 0:
                flash("ERROR: You must click the box declaring" +
                      " you really mean it")
                return render_template('adult_delete.html',
                                       title='Delete Yourself',
                                       user_name=user_list[0].firstname,
                                       form=form,), 401
            if len(user_list) == 1:
                user = user_list[0]
                logout_user()
                g.user = None
                g.isgoogle = False
                parents.delete_with_children(user)
                flash('User deleted.')
            elif len(user_list) > 1:
                msg = "Issue deleting user, problem logged to be fixed"
                logger.warning(msg + "len userlist %s for %s" %
                               (len(user_list), ))
                flash("ERROR: " + msg)
            else:
                flash('ERROR: This user not found?!?!, nothing to delete?')
                logger.warning("WE SHOULD NEVER be here! a88987")
        else:
            user_name = '<user not found>'
            try:
                user_name = user_list[0]
            except:
                pass  # User not logged in? wont matter.

            for e_field in form.errors.keys():
                msglist = ''
                for emsg in form.errors[e_field]:
                    msglist += emsg + ", "
                flash('ERROR:(%s) %s' % (e_field, msglist[:-2]))
            return render_template('adult_delete.html',
                                   title='Delete yourself.',
                                   user_name=user.firstname,
                                   form=form,), 401

        return redirect(url_for('index'))

    else:
        user_name = '<user not found>'
        try:
            user_name = user_list[0]
        except:
            pass  # User not logged in? wont matter.
        return render_template('adult_delete.html', form=form,
                               user_name=user_name,
                               title="Delete child data")
