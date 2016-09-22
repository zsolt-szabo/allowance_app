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
import app
from app import forms
from app import models
from app import db
from flask import redirect
from flask import url_for
import random
import json
import sqlalchemy
import traceback
from flask.ext.login import login_user
from flask import render_template, request, flash, g

login_manager = app.lm

acct_choices = [('acct1_name', 'acct1_used', 'acct1_comment'),
                ('acct2_name', 'acct2_used', 'acct2_comment'),
                ('acct3_name', 'acct3_used', 'acct3_comment'),
                ('acct4_name', 'acct4_used', 'acct4_comment'),
                ('acct5_name', 'acct5_used', 'acct5_comment')]
loc_choices = [('location1_name', 'location1_used', 'location1_comment'),
               ('location2_name', 'location2_used', 'location2_comment'),
               ('location3_name', 'location3_used', 'location3_comment'),
               ('location4_name', 'location4_used', 'location4_comment'),
               ('location5_name', 'location5_used', 'location5_comment'),
               ('location6_name', 'location6_used', 'location6_comment'),
               ('location7_name', 'location7_used', 'location7_comment')]


def ajax_animals():
    '''Supports javascript when creating child account to support
       javascript to help keep user selecting login/animal1/animal2
       which already exists
    '''
    child_login = request.args.get('firstname')
    animals = models.Kid.query.filter(
        models.Kid.firstname == child_login).all()
    used_animals = []
    for each_combo in animals:
        used_animals.append((each_combo.animal1, each_combo.animal2))
    total_remaining = forms.image_combo_set - set(used_animals)
    total_remaining_dict = {}
    for each_key in total_remaining:
        total_remaining_dict[each_key[0] + "," + each_key[1]] = 'hello'
    return json.dumps([total_remaining_dict])


def kid_account_review():
    form = forms.RegisterChild1()
    if request.method == "POST" and not \
            (hasattr(g, 'is_child') and g.is_child is True):
        kid_list = models.Kid.query.filter(
            db.and_(models.Kid.firstname == form.firstname.data,
                    models.Kid.animal1 == form.initial_animal1.data,
                    models.Kid.animal2 == form.initial_animal2.data,
                    models.Kid.parent_id == g.user_id)).all()

        # Attempt to register existing user
        if len(kid_list) == 0:
            flash('ERROR: You cannot access this child ' +
                  'as the child does not exist for you.')
            app.logger.warning("user %s NOT ALLOWED to " % g.user_id +
                               "administer existing user (%s:%s:%s)" %
                               (form.firstname.data,
                                form.initial_animal1.data,
                                form.initial_animal2.data))
            return redirect(url_for('index'))

        # We should never be here
        if len(kid_list) > 1:
            app.logger.warning(
                "Alert, query for kid user " +
                "returns more than one set of records" +
                "(%s:%s:%s)" %
                (form.firstname.data, form.animal1.data, form.animal2.data))
        f = form  # Shortcut to save space for form.

        allowances = models.Allowance.query.filter_by(
            kid_id=kid_list[0].id).all()
        if f.validate_on_submit():
            ##################################################################
            #   BEGIN Check and adjust all related allowances
            # Logic: 1) for all accounts/locations that have a non-zero
            #           balance, distribute the percentage from the closed
            #           account
            #        2) Leave accounts alone that have zero as it seems to
            #           be purposefully ignored by user
            #        3) This can be problematic for accounts only distributing
            #           to one bucket.
            ##################################################################

            for ea_allow in allowances:
                tot_a = 0  # Total of all sub account percentages
                a_to_adjust = []
                tot_l = 0  # Total of all location percentages
                l_to_adjust = []
                a_line = 'tot_a += ea_allow.account%s_perc'
                l_line = 'tot_l += ea_allow.location%s_perc'
                # Redistribute allowance among remaining accounts
                update_dict = {}

                for i in range(1, 6):
                    # allowance percentage definied, not 0 and active
                    accX_per = ea_allow.__getattribute__('account%s_perc' % i)
                    if accX_per is not None and \
                            f.__dict__['acct%s_used' % i].data is True and \
                            accX_per != 0:
                        a_to_adjust.append(i)
                        stmt = a_line % i
                        exec(stmt)  # tot_a += each_allow.accountX_perc
                    else:
                        update_dict["account%s_perc" % i] = 0

                for i in range(1, 8):
                    # location percentage definied, not 0 and active
                    locX_per = \
                        ea_allow.__getattribute__('location%s_perc' % i)
                    if locX_per is not None and \
                            f.__dict__['location%s_used' % i].data is \
                            True and locX_per != 0:
                        l_to_adjust.append(i)
                        stmt = l_line % i
                        exec(stmt)  # tot_l += each_allow.locationX_perc
                    else:
                        update_dict["location%s_perc" % i] = 0

                if tot_a != 100 and len(a_to_adjust) > 0:
                    diff = 100 - tot_a
                    split = round(diff / float(len(a_to_adjust)), 2)
                    amount_added = 0
                    for i in a_to_adjust[1:]:
                        thekey = "account%s_perc" % i
                        sv = ea_allow.__dict__[thekey]  # Start Value
                        update_dict.setdefault(thekey, sv)
                        update_dict[thekey] += split
                        amount_added += split
                    # Ensure we are absolutely 100% not 99.9
                    thekey = "account%s_perc" % a_to_adjust[0]
                    sv = ea_allow.__dict__[thekey]  # Start Value
                    update_dict.setdefault(thekey, sv)
                    update_dict[thekey] += (diff - amount_added)
                elif tot_a != 100 and len(a_to_adjust) == 0:
                    msg = "ERROR: Could not fix allowance distribution for "
                    msg += "sub-accounts @ '%s'.  Please " % ea_allow.nickname
                    msg += "remove and recreate."
                    flash(msg)

                if tot_l != 100 and len(l_to_adjust) > 0:
                    diff = 100 - tot_l
                    split = round(diff / float(len(l_to_adjust)), 2)
                    amount_added = 0
                    for i in l_to_adjust[1:]:
                        thekey = "location%s_perc" % i
                        sv = ea_allow.__dict__[thekey]  # Start Value
                        update_dict.setdefault(thekey, sv)
                        update_dict[thekey] += split
                        amount_added += split
                    # Ensure we are absolutely 100% not 99.9
                    thekey = "location%s_perc" % l_to_adjust[0]
                    sv = ea_allow.__dict__[thekey]  # Start Value
                    update_dict.setdefault(thekey, sv)
                    update_dict[thekey] += (diff - amount_added)
                elif tot_l != 100 and len(l_to_adjust) == 0:
                    msg = "ERROR: Could not fix storage distribution for "
                    msg += "locations @ '%s'.  Please remove and recreate." \
                           % ea_allow.nickname
                    flash(msg)

                if tot_a != 100 or tot_l != 100:
                    update_me = models.Allowance.query.filter_by(
                        id=ea_allow.id)
                    try:
                        update_me.update(update_dict)
                        db.session.commit()
                    except:
                        msg = traceback.format_exc()
                        msg += str(update_dict) + "\n"
                        msg += "update for allow: %s, kid %s" % (
                            ea_allow.id, kid_list[0].id)
                        app.logger.error(msg)
                        flash("ERROR: please remove problem allowances/" +
                              "location on allowance page and try again")
                        return render_template('child_account.html',
                                               title='Child Account',
                                               form=form,
                                               acct_choices=acct_choices,
                                               loc_choices=loc_choices), 401
                    msg = "Allowance %i adjusted for kid %s " % (
                        ea_allow.id, kid_list[0].id)
                    app.logger.info("Allowance adjusted ")

            ##################################################################
            #   END Check and adjust all related allowances
            ##################################################################

            update_dict = dict(
                firstname=f.firstname.data, pw=f.password.data,
                animal1=f.animal1.data, animal2=f.animal2.data,
                animal3=f.animal3.data, animal4=f.animal4.data,
                acct1_name=f.acct1_name.data,
                acct2_name=f.acct2_name.data,
                acct3_name=f.acct3_name.data,
                acct4_name=f.acct4_name.data,
                acct5_name=f.acct5_name.data,
                acct1_used=f.acct1_used.data,
                acct2_used=f.acct2_used.data,
                acct3_used=f.acct3_used.data,
                acct4_used=f.acct4_used.data,
                acct5_used=f.acct5_used.data,
                acct1_comment=f.acct1_comment.data,
                acct2_comment=f.acct2_comment.data,
                acct3_comment=f.acct3_comment.data,
                acct4_comment=f.acct4_comment.data,
                acct5_comment=f.acct5_comment.data,

                location1_name=f.location1_name.data,
                location2_name=f.location2_name.data,
                location3_name=f.location3_name.data,
                location4_name=f.location4_name.data,
                location5_name=f.location5_name.data,
                location6_name=f.location6_name.data,
                location7_name=f.location7_name.data,
                location1_used=f.location1_used.data,
                location2_used=f.location2_used.data,
                location3_used=f.location3_used.data,
                location4_used=f.location4_used.data,
                location5_used=f.location5_used.data,
                location6_used=f.location6_used.data,
                location7_used=f.location7_used.data,
                location1_comment=f.location1_comment.data,
                location2_comment=f.location2_comment.data,
                location3_comment=f.location3_comment.data,
                location4_comment=f.location4_comment.data,
                location5_comment=f.location5_comment.data,
                location6_comment=f.location6_comment.data,
                location7_comment=f.location7_comment.data,
                               )

            # TODO: use of initial_animaX is not ideal, as multiple
            # form submits when mistakes are made but animals are
            # changing will cause a break.  Revisit and fix
            k = models.Kid.query.filter_by(
                firstname=form.firstname.data,
                animal1=form.initial_animal1.data,
                animal2=form.initial_animal2.data,
                parent_id=g.user_id)
            if k.count() == 0:
                msg = "Issue updating child account unfortunately "
                msg += "it did not update.  Support has been notified."
                flash(msg)
                app.logger.warning(
                    msg + "::" + form.firstname.data + ":" + str(g.user_id) +
                    ":" + form.initial_animal1.data + ":" +
                    form.initial_animal2.data)
            else:
                try:
                    k.update(update_dict)
                    db.session.commit()
                    flash("Child info updated")
                except sqlalchemy.exc.IntegrityError as e:
                    msg = "ERROR: occurred on database side, more than likely"
                    msg += " due to the requirement 1 storage and 1 account "
                    msg += " must always be selected." + e.message
                    flash(msg)
                    return render_template('child_account.html',
                                           title='Child Account',
                                           form=form,
                                           acct_choices=acct_choices,
                                           loc_choices=loc_choices), 401
        return redirect(url_for('index'))
    # #################################################
    else:  # We are at the http GET section of the code.
        kid_data = request.args.get('kid')
        kid_list = []
        if kid_data is not None:
            kid_split = kid_data.split(":")
            if len(kid_split) == 3:
                if hasattr(g, 'is_child') and g.is_child is True:
                    kid_list = models.Kid.query.filter(
                        db.and_(
                            models.Kid.firstname == kid_split[0],
                            models.Kid.animal1 == kid_split[1],
                            models.Kid.animal2 == kid_split[2]),
                        models.Kid.id == g.kid_id).all()
                else:
                    kid_list = models.Kid.query.filter(
                        db.and_(
                            models.Kid.firstname == kid_split[0],
                            models.Kid.animal1 == kid_split[1],
                            models.Kid.animal2 == kid_split[2]),
                        models.Kid.parent_id == g.user_id).all()
            if len(kid_list) == 0:
                msg = 'Nothing found for kid account review '
                flash(msg)
                app.logger.warning(
                    msg + ' (%s:%s:%s)' %
                    (kid_split[0], kid_split[1], kid_split[2]))
                return redirect(url_for('index'))
            # We should never be here
            if len(kid_list) > 1:
                app.logger.warning(
                    "Alert, query for kid user " +
                    "returns more than one set of records" +
                    "(%s:%s:%s)" % (kid_split[0], kid_split[1], kid_split[2]))
        else:
            app.logger.warning('argument for populating kid data was empty')
            flash('No kid data given for review.')
            return redirect(url_for('index'))

        #  Add dictionary to form 'used_by_allowance' so we can mark accounts
        #  and locations if they are used.
        if len(kid_list) > 0:
            allowances = models.Allowance.query.filter_by(
                kid_id=kid_list[0].id).all()
        form.used_by_allowance = {}
        for ea_allow in allowances:
            for i in range(1, 6):
                stmnt = 'form.used_by_allowance.setdefault("acct%s_name", "")'
                stmnt = stmnt % i
                exec(stmnt)
                accX_per = ea_allow.__getattribute__('account%s_perc' % i)
                if accX_per is not None and accX_per != 0:
                    stmnt = 'form.used_by_allowance["acct%s_name"] += "%s, "'
                    stmnt = stmnt % (i, str(ea_allow.nickname))
                    exec(stmnt)
            for i in range(1, 8):
                stmnt = \
                    'form.used_by_allowance.setdefault("location%s_name", "")'
                stmnt = stmnt % i
                exec(stmnt)
                locX_per = ea_allow.__getattribute__('location%s_perc' % i)
                if locX_per is not None and locX_per != 0:
                    stmnt = \
                        'form.used_by_allowance["location%s_name"] += "%s, "'
                    stmnt = stmnt % (i, str(ea_allow.nickname))
                    exec(stmnt)

        form.animal1.data = kid_list[0].animal1
        form.animal2.data = kid_list[0].animal2
        form.animal3.data = kid_list[0].animal3
        form.animal4.data = kid_list[0].animal4

        form.initial_animal1.data = kid_list[0].animal1
        form.initial_animal2.data = kid_list[0].animal2

        form.firstname.data = kid_list[0].firstname
        form.password.data = kid_list[0].pw
        form.acct1_name.data = kid_list[0].acct1_name
        form.acct2_name.data = kid_list[0].acct2_name
        form.acct3_name.data = kid_list[0].acct3_name
        form.acct4_name.data = kid_list[0].acct4_name
        form.acct5_name.data = kid_list[0].acct5_name
        form.acct1_used.data = kid_list[0].acct1_used
        form.acct2_used.data = kid_list[0].acct2_used
        form.acct3_used.data = kid_list[0].acct3_used
        form.acct4_used.data = kid_list[0].acct4_used
        form.acct5_used.data = kid_list[0].acct5_used
        form.acct1_comment.data = kid_list[0].acct1_comment
        form.acct2_comment.data = kid_list[0].acct2_comment
        form.acct3_comment.data = kid_list[0].acct3_comment
        form.acct4_comment.data = kid_list[0].acct4_comment
        form.acct5_comment.data = kid_list[0].acct5_comment

        form.location1_name.data = kid_list[0].location1_name
        form.location2_name.data = kid_list[0].location2_name
        form.location3_name.data = kid_list[0].location3_name
        form.location4_name.data = kid_list[0].location4_name
        form.location5_name.data = kid_list[0].location5_name
        form.location6_name.data = kid_list[0].location6_name
        form.location7_name.data = kid_list[0].location7_name
        form.location1_used.data = kid_list[0].location1_used
        form.location2_used.data = kid_list[0].location2_used
        form.location3_used.data = kid_list[0].location3_used
        form.location4_used.data = kid_list[0].location4_used
        form.location5_used.data = kid_list[0].location5_used
        form.location6_used.data = kid_list[0].location6_used
        form.location7_used.data = kid_list[0].location7_used
        form.location1_comment.data = kid_list[0].location1_comment
        form.location2_comment.data = kid_list[0].location2_comment
        form.location3_comment.data = kid_list[0].location3_comment
        form.location4_comment.data = kid_list[0].location4_comment
        form.location5_comment.data = kid_list[0].location5_comment
        form.location6_comment.data = kid_list[0].location6_comment
        form.location7_comment.data = kid_list[0].location7_comment
        if hasattr(g, 'is_child') and g.is_child is True:
            return render_template('child_account_readonly.html',
                                   title='Child Account',
                                   form=form,
                                   acct_choices=acct_choices,
                                   loc_choices=loc_choices)
        else:
            return render_template('child_account.html',
                                   title='Child Account',
                                   form=form,
                                   acct_choices=acct_choices,
                                   loc_choices=loc_choices)


def register_child1():
    form = forms.RegisterChild1()
    random.shuffle(form.animal1.choices)
    random.shuffle(form.animal2.choices)
    random.shuffle(form.animal3.choices)
    random.shuffle(form.animal4.choices)

    # ##########################
    # POST
    # ##########################
    if request.method == "POST":
        animal1 = form.animal1.data
        animal2 = form.animal2.data
        animal3 = form.animal3.data
        animal4 = form.animal4.data
        password = form.password.data
        firstname = form.firstname.data

        acct1_name = form.acct1_name.data
        acct1_used = form.acct1_used.data
        acct1_comment = form.acct1_comment.data
        location1_name = form.location1_name.data
        location1_used = form.location1_used.data
        location1_comment = form.location1_comment.data

        acct2_name = form.acct2_name.data
        acct2_used = form.acct2_used.data
        acct2_comment = form.acct2_comment.data
        location2_name = form.location2_name.data
        location2_used = form.location2_used.data
        location2_comment = form.location2_comment.data

        acct3_name = form.acct3_name.data
        acct3_used = form.acct3_used.data
        acct3_comment = form.acct3_comment.data
        location3_name = form.location3_name.data
        location3_used = form.location3_used.data
        location3_comment = form.location3_comment.data

        acct4_name = form.acct4_name.data
        acct4_used = form.acct4_used.data
        acct4_comment = form.acct4_comment.data
        location4_name = form.location4_name.data
        location4_used = form.location4_used.data
        location4_comment = form.location4_comment.data

        acct5_name = form.acct5_name.data
        acct5_used = form.acct5_used.data
        acct5_comment = form.acct5_comment.data
        location5_name = form.location5_name.data
        location5_used = form.location5_used.data
        location5_comment = form.location5_comment.data

        location6_name = form.location6_name.data
        location6_used = form.location6_used.data
        location6_comment = form.location6_comment.data

        location7_name = form.location7_name.data
        location7_used = form.location7_used.data
        location7_comment = form.location7_comment.data

        kid_list = models.Kid.query.filter(
            db.and_(models.Kid.firstname == firstname,
                    models.Kid.animal1 == animal1,
                    models.Kid.animal2 == animal2)).all()

        # Attempt to register existing user
        if len(kid_list) > 0:
            flash('ERROR: Cannot register this login combination, ' +
                  'Please try again with different user name')
            app.logger.warning("Front end failed to prevent registration of" +
                               " existing user (%s:%s:%s)" %
                               (firstname, animal1, animal2))
            return redirect(url_for('index'))

        # We should never be here
        if len(kid_list) > 1:
            app.logger.warning(
                "Alert, query for kid user " +
                "returns more than one set of records" +
                "(%s:%s:%s)" % (firstname, animal1, animal2))

        # ########################################
        # SUCCESS: register user validation passes
        if form.validate_on_submit():
            kid = models.Kid(
                firstname=firstname,
                animal1=animal1,
                animal2=animal2,
                animal3=animal3,
                animal4=animal4,
                parent_id=g.user_id,
                pw=password,
                acct1_name=acct1_name,
                acct1_used=acct1_used,
                acct1_comment=acct1_comment,

                acct2_name=acct2_name,
                acct2_used=acct2_used,
                acct2_comment=acct2_comment,

                acct3_name=acct3_name,
                acct3_used=acct3_used,
                acct3_comment=acct3_comment,

                acct4_name=acct4_name,
                acct4_used=acct4_used,
                acct4_comment=acct4_comment,

                acct5_name=acct5_name,
                acct5_used=acct5_used,
                acct5_comment=acct5_comment,

                location1_name=location1_name,
                location1_used=location1_used,
                location1_comment=location1_comment,

                location2_name=location2_name,
                location2_used=location2_used,
                location2_comment=location2_comment,

                location3_name=location3_name,
                location3_used=location3_used,
                location3_comment=location3_comment,

                location4_name=location4_name,
                location4_used=location4_used,
                location4_comment=location4_comment,

                location5_name=location5_name,
                location5_used=location5_used,
                location5_comment=location5_comment,

                location6_name=location6_name,
                location6_used=location6_used,
                location6_comment=location6_comment,

                location7_name=location7_name,
                location7_used=location7_used,
                location7_comment=location7_comment,
                )
            db.session.add(kid)
            try:
                db.session.commit()
            except sqlalchemy.exc.IntegrityError as e:
                msg = "ERROR: occurred on database side, more than likely"
                msg += " due to the requirement 1 storage and 1 account "
                msg += " must always be selected." + e.message
                flash(msg)
                return render_template('child_register.html',
                                       title='Child Register',
                                       form=form,
                                       acct_choices=acct_choices,
                                       loc_choices=loc_choices), 401
            flash("Kid added")
            return redirect(url_for('index'))

        # ########################################
        # FAILED: validation failed, give feedback
        else:
            for e_field in form.errors.keys():
                msglist = ''
                for emsg in form.errors[e_field]:
                    msglist += emsg + ", "
                flash('ERROR:(%s) %s' % (e_field, msglist[:-2]))
            return render_template('child_register.html',
                                   title='Child Register',
                                   form=form,
                                   acct_choices=acct_choices,
                                   loc_choices=loc_choices), 401

        app.logger.warning("Alert, we should not be here: 3646")
    # ##########################
    # GET
    # ##########################
    else:
        return render_template('child_register.html',
                               title='Child Register',
                               form=form,
                               acct_choices=acct_choices,
                               loc_choices=loc_choices)


def login():
    form = forms.ChildLogin()
    if form.validate_on_submit():
        child_l = models.Kid.query.filter(
            models.Kid.firstname == form.firstname.data,
            models.Kid.animal1 == form.animal1.data,
            models.Kid.animal2 == form.animal2.data,
            models.Kid.pw == form.password.data,
            models.Kid.animal3 == form.animal3.data,
            models.Kid.animal4 == form.animal4.data).all()
        if len(child_l) > 0:
            g.is_child = True
            login_user(child_l[0])
            return redirect(url_for('index'))
        else:
            flash('ERROR: User/Password combination not found')
            return render_template('child_login.html',
                                   title='Child Sign In',
                                   form=form), 401
    else:
        for e_field in form.errors.keys():
            msglist = ''
            for emsg in form.errors[e_field]:
                msglist += emsg + ", "
            flash('ERROR:(%s) %s' % (e_field, msglist[:-2]))
        return render_template('child_login.html',
                               title='Child Sign In',
                               form=form,), 401

    return render_template('child_login.html',
                           title='Child Sign In',
                           form=form)


def delete_kid():
    form = forms.UserDelete()
    kid_data = request.args.get('kid')
    if kid_data is not None:
        kid_split = kid_data.split(":")
        if len(kid_split) == 3:
            kid_query = models.Kid.query.filter_by(
                    firstname=kid_split[0],
                    animal1=kid_split[1],
                    animal2=kid_split[2],
                    parent_id=g.user_id)
        else:
            app.logger.warning('Could not split kid_data:  %s' % kid_data)
            flash('Kelly cohlos recieved.')
            return redirect(url_for('index'))
    else:
        app.logger.warning('argument for populating kid data was empty')
        flash('Kelly cohlos recieved.')
        return redirect(url_for('index'))

    if request.method == "POST":
        kid_list = kid_query.all()
        if form.validate_on_submit():
            if form.really_means_it.data is None or \
                    form.really_means_it.data is False:
                flash("ERROR: You must click the box declaring" +
                      " you really mean it")
                return render_template('child_delete.html',
                                       title='Delete child data',
                                       kid_name=kid_split[0],
                                       form=form,), 401
            if len(kid_list) == 1:
                kid = kid_list[0]
                allowdays = None
                allowances = models.Allowance.query.filter_by(
                    kid_id=kid.id)
                for ea_allow in allowances.all():
                    allowdays = models.AllowanceDays.query.filter_by(
                        allowance_id=ea_allow.id)
                    if allowdays:
                        allowdays.delete()
                ledger = models.Ledger.query.filter_by(kid_id=kid.id)
                allowances.delete()
                ledger.delete()
                kid_query.delete()
                app.db.session.commit()
                flash('Child data for "%s" deleted.' % kid_split[0])
            elif len(kid_list) > 1:
                msg = "Issue deleting child, problem logged to be fixed"
                app.logger.warn(msg + "len kidlist %s for %s" %
                                (len(kid_list), ))
                flash("ERROR: " + msg)
            else:
                flash('Child not found, nothing to delete.')
        else:
            for e_field in form.errors.keys():
                msglist = ''
                for emsg in form.errors[e_field]:
                    msglist += emsg + ", "
                flash('ERROR:(%s) %s' % (e_field, msglist[:-2]))
            return render_template('child_delete.html',
                                   title='Delete child data',
                                   kid_name=kid_split[0],
                                   form=form,), 401

        return redirect(url_for('index'))

    else:
        return render_template('child_delete.html', form=form,
                               kid_name=kid_split[0],
                               title="Delete child data")
