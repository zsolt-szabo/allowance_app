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
from flask.ext.login import login_user
from flask.ext.login import logout_user
from flask import g
from flask import redirect
from flask import url_for
import random
import requests

from flask import render_template, request, session, flash

login_manager = app.lm

goog_pw = config.GOOG_PW


def get_captcha():
    class captcha:
        c = {1: 'a', 2: 'b', 3: 'c', 4: 'd', 5: 'e', 6: 'f',
             7: 'g', 8: 'h', 9: 'i'}
        operations = [
            'add both sets of numbers',
            'subtract the second set of numbers from the first',
            'write all the numbers you see in order (including both sets)',
            'write second set in reverse order, then first set in reverse ' +
            'order.']

        def __init__(self, firstnum, secondnum,
                     firstnum_links, secondnum_links):
            self.firstnum = firstnum
            self.secondnum = secondnum
            self.firstnum_links = firstnum_links
            self.secondnum_links = secondnum_links
            self.solution = None
            self.operation = None

    num1_links = []
    num2_links = []
    firstnum = str(random.randint(1, 9))
    tmp = str(random.randint(1, 9))
    for each_num in xrange(2):
        if random.choice([True, False]):
            firstnum += str(random.randint(1, 9))
        if random.choice([True, False]):
            tmp += str(random.randint(1, 9))

    if int(firstnum) > int(tmp):
        secondnum = tmp
    else:
        secondnum = firstnum
        firstnum = tmp

    for ea_char in firstnum:
        num1_links.append("static/%s.png" % captcha.c[int(ea_char)])
    for ea_char in secondnum:
        num2_links.append("static/%s.png" % captcha.c[int(ea_char)])

    cap = captcha(firstnum, secondnum, num1_links, num2_links)

    operation = random.randint(0, 3)
    cap.operation = captcha.operations[operation]
    if operation == 0:
        cap.solution = int(firstnum) + int(secondnum)
    elif operation == 1:
        cap.solution = int(firstnum) - int(secondnum)
    elif operation == 2:
        cap.solution = int(firstnum + secondnum)
    else:
        cap.solution = secondnum[::-1] + firstnum[::-1]

    return cap


def login():
    form = forms.LoginForm()
    g.force_google_logout = session.pop('force_google_logout', None)
    if request.method == "POST" and form.validate_on_submit():
        user_list = models.User.query.filter(
            models.User.email == form.email.data).all()
        if len(user_list) > 0:
            user = user_list[0]
            if user.check_password(form.password.data):
                login_user(user)
                g.user = user.email
                g.isgoogle = user.isgoogle
                return redirect(url_for('index'))
            else:
                flash('ERROR: User/Password combination not found')
                return render_template('login.html',
                                       title='Sign In',
                                       form=form), 401
        else:
            flash('ERROR: User/Password combination not found')
            # greturn redirect(request.args.get('next') or url_for('index'))
            return render_template(
                'login.html', title='Login', form=form), 401

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
            app.logger.warning("Alert, query for email  %s " % email +
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


def logout():
    logout_user()
    g.user = None
    g.isgoogle = False
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
    app.logger.info(google_log)
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
                app.logger.info('Logged in google user %s' %
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
            app.logger.info('Created new google user %s in the system' %
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
            app.logger.warning("Alert, query for email  %s " % email +
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
            print form.captcha.data, str(cap_answer)
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
            user = models.User(email=email,
                               firstname=firstname,
                               money_symbol=money_symbol)
            user.set_password(password1)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            g.user = user.email
            g.isgoogle = False

            return render_template(
                'index.html', title='Home',
                name=user.firstname)
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

        app.logger.warning("Alert, we should not be here: 2546")
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
                kids = models.Kid.query.filter_by(parent_id=user.id)
                allowdays = None
                for each_kid in kids.all():
                    allowances = models.Allowance.query.filter_by(
                        kid_id=each_kid.id)
                    for ea_allow in allowances.all():
                        allowdays = models.AllowanceDays.query.filter_by(
                            allowance_id=ea_allow.id)
                        if allowdays:
                            allowdays.delete()
                    ledger = models.Ledger.query.filter_by(kid_id=each_kid.id)

                    allowances.delete()
                    ledger.delete()

                logout_user()
                g.user = None
                g.isgoogle = False
                kids.delete()
                user_query.delete()
                app.db.session.commit()
                flash('User deleted.')
            elif len(user_list) > 1:
                msg = "Issue deleting user, problem logged to be fixed"
                app.logger.warn(msg + "len userlist %s for %s" %
                                (len(user_list), ))
                flash("ERROR: " + msg)
            else:
                flash('ERROR: This user not found?!?!, nothing to delete?')
                app.logger.warn("WE SHOULD NEVER be here! a88987")
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
