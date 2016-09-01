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
import re
import config
import app
from app import forms
from app import models
from app import db
from flask import redirect
from flask import url_for
import traceback
import datetime

from flask import render_template, request, flash, g, session
# Import the helper functions
# Import the configuration file you downloaded from Google Developer Console
server_config_json = config.SERVER_CONFIG_JSON

login_manager = app.lm


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
        self.change_acc1 = 0
        self.change_acc2 = 0
        self.change_acc3 = 0
        self.change_acc4 = 0
        self.change_acc5 = 0
        self.change_loc1 = 0
        self.change_loc2 = 0
        self.change_loc3 = 0
        self.change_loc4 = 0
        self.change_loc5 = 0
        self.change_loc6 = 0
        self.change_loc7 = 0
        self.adjuster_name = "Automated Entry"
        self.comment = ''
        self.last_ledger_update = datetime.datetime.utcnow()


def c(val):
    '''Convenience function convert to float'''
    if val is None:
        return 0
    else:
        return float(val)


def remove_allowance():
    allow_id = '<undefined>'
    user_id = '<undefined>'
    try:
        allow_id = int(request.args.get('allow_id'))
    except:
        msg = traceback.format_exc()
        flash('ERROR: error occurred removing this allowance- logged.')
        app.logging.warn(msg + " allowance id %s" % allow_id)
        return redirect(url_for('do_allowance'))

    # ####### for security reasons ensure allowance to delete
    # ####### belongs to logged in parent (via child)
    user_allowed = False
    current_allowances = []
    try:
        current_allowances = models.Allowance.query.join(
            models.Kid).filter(models.Kid.parent_id == g.user_id).all()
        user_id = g.user_id
    except:
        import traceback
        msg = traceback.format_exc()
        msg += "Failure deleting allowance %s" % allow_id

    for allowance in current_allowances:
        if allowance.id == allow_id:
            user_allowed = True
            # ##### Find and delete allowance pay days
            allowance_dates = models.AllowanceDays.query.filter(
                models.AllowanceDays.allowance_id == allow_id).all()
            for each_date in allowance_dates:
                models.AllowanceDays.query.filter_by(id=each_date.id).delete()
                db.session.commit()
            models.Allowance.query.filter_by(id=allowance.id).delete()
            db.session.commit()

    if not user_allowed:
        flash('Unable to understand allowance Id given for removal')
        app.logger.error('Attempt to remove allowance %s by user %s failed'
                         % (allow_id, user_id))
    return redirect(url_for('do_allowance'))


def allowances():
    form = forms.Allowance()
    # ################################################## #
    # ##### Precollect layout data for get and post #### #
    # ################################################## #
    kid_string = request.args.get('kid')
    kid_data = None
    if kid_string is not None and kid_string.count(':') == 2:
        kid_data = kid_string.split(':')
        session['kid_data'] = kid_data
    elif 'kid_data' in session:
        kid_data = session['kid_data']  # TBD, Beginnings of memory consume
    else:
        app.logger.warning("Alert, we should not be here: 3112")

    # ###### Security g.user_id prevents parent from hacking kid_id to get
    # ###### kid_id information that does not belong to them.

    # ###### Security g.user_id prevents parent from hacking kid_id to get
    # ###### kid_id information that does not belong to them.
    if hasattr(g, 'is_child') and g.is_child is True:
        current_allowances = models.Allowance.query.join(
            models.Kid).filter(
            models.Kid.firstname == kid_data[0],
            models.Kid.animal1 == kid_data[1],
            models.Kid.animal2 == kid_data[2],
            models.Kid.id == g.kid_id).all()
        kid_info = models.Kid.query.filter(
            models.Kid.firstname == kid_data[0],
            models.Kid.animal1 == kid_data[1],
            models.Kid.animal2 == kid_data[2],
            models.Kid.id == g.kid_id).all()
    else:
        current_allowances = models.Allowance.query.join(
            models.Kid).filter(
            models.Kid.firstname == kid_data[0],
            models.Kid.animal1 == kid_data[1],
            models.Kid.animal2 == kid_data[2],
            models.Kid.parent_id == g.user_id).all()

        kid_info = models.Kid.query.filter(
            models.Kid.firstname == kid_data[0],
            models.Kid.animal1 == kid_data[1],
            models.Kid.animal2 == kid_data[2],
            models.Kid.parent_id == g.user_id).all()

    if len(kid_info) == 0:
        msg = "ERROR: Problem getting child data, error logged"
        flash(msg)
        app.logger.error(msg)
        return redirect(url_for('index'))

    # Form is dynamic with respect to whether account is used
    for i in range(1, 6):
        if kid_info[0].__dict__['acct%s_used' % i] is True:
            form.__dict__['check_acct%s_used' % i] = True
            form.__dict__['label_acct%s' % i] = \
                kid_info[0].__dict__['acct%s_name' % i]
        else:
            form.__dict__['check_acct%s_used' % i] = False
            form.__dict__['acct%s_perc' % i].data = 0
    # Form is dynamic with respect to whether location is used
    for i in range(1, 8):
        if kid_info[0].__dict__['location%s_used' % i] is True:
            form.__dict__['check_location%s_used' % i] = True
            form.__dict__['label_location%s' % i] = \
                kid_info[0].__dict__['location%s_name' % i]
        else:
            form.__dict__['location%s_used' % i] = False
            form.__dict__['location%s_perc' % i].data = 0

    # Get dates for allowance and tag it on to current_allowances as .DATES
    allow_data = []
    for each_allow in current_allowances:
        dates = models.AllowanceDays.query.filter(
            models.AllowanceDays.allowance_id == each_allow.id)
        each_allow.DATES = [each.payout_day for each in dates.all()]
        allow_data.append(each_allow)

    # ################ User Submitted post ############# #
    if request.method == "POST":
        if form.validate_on_submit() and not \
                (hasattr(g, 'is_child') and g.is_child is True):
            # First establish our kid_id is legit and belongs to parent
            kid = models.Kid.query.filter(
                models.Kid.firstname == kid_data[0],
                models.Kid.animal1 == kid_data[1],
                models.Kid.animal2 == kid_data[2],
                models.Kid.parent_id == g.user_id).all()
            if len(kid) == 0:
                flash('Unknown child selected error')
                return redirect(url_for('index'))
            elif len(kid) > 1:
                app.logger.error(
                    'ALERT, we should not be here EVER %s: 3289' % kid[0].id)

            m = form   # ref helps make code more concise
            total_accounts = c(m.acct1_perc.data) + c(m.acct2_perc.data)
            total_accounts += c(m.acct3_perc.data) + c(m.acct4_perc.data)
            total_accounts += c(m.acct5_perc.data)
            total_location = c(m.location1_perc.data)
            total_location += c(m.location2_perc.data)
            total_location += c(m.location3_perc.data)
            total_location += c(m.location4_perc.data)
            total_location += c(m.location5_perc.data)
            total_location += c(m.location6_perc.data)
            total_location += c(m.location7_perc.data)

            msg = None
            if total_accounts != 100:
                msg = "Allowance distribution among sub-accounts must add up "
                msg += "to 100%"
            if total_location != 100:
                msg = "Allowance storage (where) must add up "
                msg += "to 100%"
            if msg is not None:
                flash("ERROR: " + msg)
                return render_template(
                    'allowance.html',
                    title='Allowance',
                    form=form,
                    allow_data=allow_data,
                    kid_info=kid_info[0]), 401

            allow = models.Allowance(
                kid_id=kid[0].id, amount=form.amount.data,
                nickname=m.nickname.data, account1_perc=m.acct1_perc.data,
                account2_perc=m.acct2_perc.data,
                account3_perc=m.acct3_perc.data,
                account4_perc=m.acct4_perc.data,
                account5_perc=m.acct5_perc.data,
                location1_perc=m.location1_perc.data,
                location2_perc=m.location2_perc.data,
                location3_perc=m.location3_perc.data,
                location4_perc=m.location4_perc.data,
                location5_perc=m.location5_perc.data,
                location6_perc=m.location6_perc.data,
                location7_perc=m.location7_perc.data,
                )
            db.session.add(allow)
            db.session.commit()

            for each_date in form.payout_days.data:
                errmsg = ''
                try:
                    allowance_date = models.AllowanceDays(
                        payout_day=each_date, allowance_id=allow.id)
                    db.session.add(allowance_date)
                    db.session.commit()
                except:
                    errmsg += traceback.format_exc()
                    errmsg += 'ALLOWANCE ID: %s, DATE: %s' % \
                        (allow.id, each_date)
                if len(errmsg) > 0:
                    flash('ERROR: problem detected adding allowance dates ' +
                          'sorry for the inconvenience')
                    app.logger.error(errmsg)
            return redirect(url_for('do_allowance'))
        else:
            for e_field in form.errors.keys():
                msglist = ''
                for emsg in form.errors[e_field]:
                    msglist += emsg + ", "
                flash('ERROR:(%s) %s' % (e_field, msglist[:-2]))
                return render_template(
                    'allowance.html',
                    title='Allowance',
                    form=form,
                    allow_data=allow_data,
                    kid_info=kid_info[0]), 401
            msg = "We should not be here! "
            app.logger.warn(msg + 'Someone try to post as kid?' + str(dir(g)))
            return msg

    # ################ Page get request ############# #
    else:
        return render_template(
            'allowance.html',
            title='Allowance', form=form, allow_data=allow_data,
            kid_info=kid_info[0])


def a(n):
    '''Shortcut to handle nonetypes'''
    if n is None:
        return 0
    else:
        return n


def populate_hidden_arrays(hidden_columns, hidden_locs, kid):
    '''Helper function for when no ledger data exists yet'''
    app.logger.info(
        "Child has no ledger data yet, determining usable accounts")
    for i in xrange(1, 6):
        cmd1 = "if kid.acct%s_used is False:\n" % i
        cmd1 += "    hidden_columns[%s] = True" % i
        app.logger.debug("Executing:\n" + cmd1)
        exec(cmd1)
    for i in xrange(1, 8):
        cmd1 = "if kid.location%s_used is False:\n" % i
        cmd1 += "    hidden_locs[%s] = True" % i
        app.logger.debug("Executing:\n" + cmd1)
        exec(cmd1)


def handle_ledger_post(kid, form, ledger, adjuster_name, adjusted_by_parent):
    '''Helper function for ledger() function
    Params
    ------
    kid:                 models.Kid object
    form:                forms.Ledger() object
    adjuster_name:       name of adjuster
    adjusted_by_parent:  Boolean
    '''
    # ALL DATA MUST BE ROUNDED  INCLUDING ALLOWANCE UPDATES
    acct_patt = re.compile('acct(\d)_')
    if form.validate_on_submit():
        loc_math = {'loc1': 0, 'loc2': 0, 'loc3': 0, 'loc4': 0, 'loc5': 0,
                    'loc6': 0, 'loc7': 0}
        acc_math = {'acc1': 0, 'acc2': 0, 'acc3': 0, 'acc4': 0, 'acc5': 0}
        all_entries = 0
        # Check that we do not go negative on any of our storage

        if len(ledger) > 0:
            l = ledger[0]  # Shortcut variable
        else:
            l = fakeLedger()
        ledger_update_data = {
            'change_acc1': 0, 'change_acc2': 0, 'change_acc3': 0,
            'change_acc4': 0, 'change_acc5': 0,
            'total_acc1': l.total_acc1, 'total_acc2': l.total_acc2,
            'total_acc3': l.total_acc3, 'total_acc4': l.total_acc4,
            'total_acc5': l.total_acc5,
            'change_loc1': 0, 'change_loc2': 0, 'change_loc3': 0,
            'change_loc4': 0, 'change_loc5': 0, 'change_loc6': 0,
            'change_loc7': 0,
            'total_loc1': l.total_loc1, 'total_loc2': l.total_loc2,
            'total_loc3': l.total_loc3, 'total_loc4':  l.total_loc4,
            'total_loc5':  l.total_loc5, 'total_loc6':  l.total_loc6,
            'total_loc7':  l.total_loc7,
            'adjuster_name': adjuster_name,
            'adjusted_by_parent': adjusted_by_parent, 'kid_id': kid.id,
            'comment': form.comment.data
            }
        for i in xrange(1, 6):
            for j in xrange(1, 8):
                entry = a(getattr(form, "acct%s_loc%s" % (i, j)).data)
                loc_math['loc%s' % j] += entry
                acc_math['acc%s' % i] += entry
                if getattr(kid, "acct%s_used" % i) is False and entry > 0:
                    msg = "'" + getattr(kid, "acct%s_name" % i)
                    msg += "' is a deactivated account, you can only take "
                    msg += "money out until the account is empty"
                    flash("ERROR: " + msg)
                    return
                if getattr(kid, "location%s_used" % j) is False and entry > 0:
                    msg = "'" + getattr(kid, "location%s_name" % j)
                    msg += "' is a deactivated location, you can only take "
                    msg += "money out until the location is empty"
                    flash("ERROR: " + msg)
                    return

                all_entries += entry

                ledger_update_data['change_acc%s' % i] += entry
                ledger_update_data['change_loc%s' % j] += entry
                ledger_update_data['total_acc%s' % i] += entry
                ledger_update_data['total_loc%s' % j] += entry
        for ea_loc in loc_math:
            if loc_math[ea_loc] > 0 and hasattr(g, 'is_child') and \
                    g.is_child is True:
                flash("ERROR: Only Parent can add money, kids can subtract")
                return False
            if loc_math[ea_loc] + getattr(l, 'total_' + ea_loc) < 0:
                msg = "You attempted to take too much from money storage '%s'"
                msg = msg % getattr(
                    kid, ea_loc.replace('loc', 'location') + "_name")
                flash("ERROR: " + msg)
                return False
        for ea_acc in acc_math:
            if acc_math[ea_acc] > 0 and hasattr(g, 'is_child') and \
                    g.is_child is True:
                flash("ERROR: Only Parent can add money, kids can subtract")
                return False
            if acc_math[ea_acc] + getattr(l, 'total_' + ea_acc) < 0:
                msg = "You attempted to take too much from account '%s'"
                msg = msg % getattr(
                    kid, ea_acc.replace('acc', 'acct') + "_name")
                flash("ERROR: " + msg)
                return False
        if all_entries == 0:
            flash('No account changes to update')
            return False
        # TODO
        # Link at each ledger transaction to show storage
        new_entry = models.Ledger(**ledger_update_data)
        db.session.add(new_entry)
        db.session.commit()
        return True
    else:
        for e_field in form.errors.keys():
            msglist = ''
            for emsg in form.errors[e_field]:
                msglist += emsg + ", "
                e_name = e_field
                m = acct_patt.search(e_field)
                if m is not None:
                    e_name = getattr(kid, "acct%s_name" % m.group(1))
            flash('ERROR:(%s) %s' % (e_name, msglist[:-2]))
        return False


def ledger():
    ###################################
    #  ALERT we are using g.id which wont work
    #        when logged in as a kid.  We must
    #        fix this
    ###################################
    form = forms.Ledger()
    kid_string = request.args.get('kid')
    kid_data = None
    hidden_columns = {}
    hidden_locs = {}
    kid_arr = []

    if kid_string is not None and kid_string.count(':') == 2:
        kid_data = kid_string.split(':')
        session['kid_data'] = kid_data
    elif 'kid_data' in session:
        kid_data = session['kid_data']  # TBD, Beginnings of memory consume
    else:
        app.logger.warning("Alert, we should not be here: 3412")
        flash("ERROR: Failed to extract child info given, error reported!")
        return redirect(url_for('index'))

    # ###### Security g.user_id prevents parent from hacking kid_id to get
    # ###### kid_id information that does not belong to them.
    if hasattr(g, 'is_child') and g.is_child is True:
        kid_arr = models.Kid.query.filter(
            models.Kid.firstname == kid_data[0],
            models.Kid.animal1 == kid_data[1],
            models.Kid.animal2 == kid_data[2],
            models.Kid.id == g.kid_id).all()
    else:
        kid_arr = models.Kid.query.filter(
            models.Kid.firstname == kid_data[0],
            models.Kid.animal1 == kid_data[1],
            models.Kid.animal2 == kid_data[2],
            models.Kid.parent_id == g.user_id
            ).all()
    if len(kid_arr) == 0:
            msg = "Failed to find kid %s " % str(kid_data)
            flash("ERROR: " + msg)
            user_type = 'parent'
            user = "<notdefined>"
            if hasattr(g, 'is_child') and g.is_child is True:
                user_type = 'kid'
                user = g.kid_id
            else:
                user = g.user_id
            app.logger.warning(msg + " for %s id %s" % (user_type, user))
            return redirect(url_for('index'))

    kid = kid_arr[0]
    parent = models.User.query.filter(models.User.id == kid.parent_id).all()[0]
    adjuster_name = None

    def get_ledger(kid_data, g):
        if hasattr(g, 'is_child') and g.is_child is True:
            ledger = models.Ledger.query.join(
                models.Kid).filter(
                models.Kid.firstname == kid_data[0],
                models.Kid.animal1 == kid_data[1],
                models.Kid.animal2 == kid_data[2],
                models.Kid.id == g.kid_id). \
                order_by(models.Ledger.last_ledger_update.desc()).all()
        else:
            ledger = models.Ledger.query.join(
                models.Kid).filter(
                models.Kid.firstname == kid_data[0],
                models.Kid.animal1 == kid_data[1],
                models.Kid.animal2 == kid_data[2],
                models.Kid.parent_id == g.user_id). \
                order_by(models.Ledger.last_ledger_update.desc()).all()
        return ledger

    ledger = get_ledger(kid_data, g)
    adjusted_by_parent = False

    if hasattr(g, 'is_child') and g.is_child is True:
        adjuster_name = kid.firstname
    else:
        adjuster_name = parent.firstname
        adjusted_by_parent = True

    # ################ User Submitted post ############# #
    # TBD must be adjusted for when kid logs in
    if request.method == "POST":
        if handle_ledger_post(
                kid, form, ledger, adjuster_name=adjuster_name,
                adjusted_by_parent=adjusted_by_parent):
            return redirect(url_for('ledger'))
    # ################ Finish Post Submission ########## #

    total_all = 0
    display_account_totals = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    if len(ledger) > 0:
        total_all = a(ledger[0].total_acc1) + a(ledger[0].total_acc2) + \
            a(ledger[0].total_acc3) + a(ledger[0].total_acc4) + \
            a(ledger[0].total_acc5)
        display_account_totals = {
            1: a(ledger[0].total_acc1), 2: a(ledger[0].total_acc2),
            3: a(ledger[0].total_acc3), 4: a(ledger[0].total_acc4),
            5: a(ledger[0].total_acc5)}

        if kid.acct1_used is False and \
                (ledger[0].total_acc1 is None or ledger[0].total_acc1 == 0):
            hidden_columns[1] = True
        if kid.acct2_used is False and \
                (ledger[0].total_acc2 is None or ledger[0].total_acc2 == 0):
            hidden_columns[2] = True
        if kid.acct3_used is False and \
                (ledger[0].total_acc3 is None or ledger[0].total_acc3 == 0):
            hidden_columns[3] = True
        if kid.acct4_used is False and \
                (ledger[0].total_acc4 is None or ledger[0].total_acc4 == 0):
            hidden_columns[4] = True
        if kid.acct5_used is False and \
                (ledger[0].total_acc5 is None or ledger[0].total_acc5 == 0):
            hidden_columns[5] = True

        if kid.location1_used is False and \
                (ledger[0].total_loc1 is None or ledger[0].total_loc1 == 0):
            hidden_locs[1] = True
        if kid.location2_used is False and \
                (ledger[0].total_loc2 is None or ledger[0].total_loc2 == 0):
            hidden_locs[2] = True
        if kid.location3_used is False and \
                (ledger[0].total_loc3 is None or ledger[0].total_loc3 == 0):
            hidden_locs[3] = True
        if kid.location4_used is False and \
                (ledger[0].total_loc4 is None or ledger[0].total_loc4 == 0):
            hidden_locs[4] = True
        if kid.location5_used is False and \
                (ledger[0].total_loc5 is None or ledger[0].total_loc5 == 0):
            hidden_locs[5] = True
        if kid.location6_used is False and \
                (ledger[0].total_loc6 is None or ledger[0].total_loc6 == 0):
            hidden_locs[6] = True
        if kid.location7_used is False and \
                (ledger[0].total_loc7 is None or ledger[0].total_loc7 == 0):
            hidden_locs[7] = True
    else:
        populate_hidden_arrays(hidden_columns, hidden_locs, kid)

    if len(ledger) == 0:
        ledger = [fakeLedger()]
    return render_template(
        'ledger.html', title='Ledger', ledger=ledger, kid_data=kid_data,
        kid=kid, hidden_columns=hidden_columns, parent=parent,
        total_all=total_all, hidden_locs=hidden_locs, form=form,
        display_account_totals=display_account_totals)
