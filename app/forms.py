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
from flask.ext.wtf import Form
from wtforms import widgets
from wtforms import StringField, PasswordField, \
    BooleanField, SelectField, SelectMultipleField, FloatField, \
    HiddenField, TextAreaField
from wtforms.validators import Required, Length, Email, NumberRange, \
    Optional
import app
import config
import glob
import copy
import os

images = [(os.path.basename(each).split('_')[1][:-4],
           'static/' + os.path.basename(each))
          for each in glob.glob(config.basedir +
                                "/app/static/animal[0-9][0-9]_*.png")]
combo_list = []
for i in images:
    for j in images:
        combo_list.append((i[0], j[0]))
image_combo_set = set(combo_list)

days_of_month = []
for i in range(1, 29):
    days_of_month.append((str(i), str(i)))

app.logger.info('Loaded kid images %s' % str(images))


class RequiredIf(Required):
    # a validator which makes a field required if
    # another field is set and has a truthy value

    def __init__(self, other_field_name, *args, **kwargs):
        self.other_field_name = other_field_name
        super(RequiredIf, self).__init__(*args, **kwargs)

    def __call__(self, form, field):
        other_field = form._fields.get(self.other_field_name)
        if other_field is None:
            raise Exception('no field named "%s" in form'
                            % self.other_field_name)
        if bool(other_field.data):
            super(RequiredIf, self).__call__(form, field)


class LoginForm(Form):
    email = StringField(
        'Email', validators=[Required(), Length(1, 64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('remember_me', default=False)


class ChildLogin(Form):
    animal1 = SelectField(u'animal1', choices=images,
                          validators=[Required(), Length(3, 99)])
    animal2 = SelectField(u'animal2', choices=copy.copy(images),
                          validators=[Required(), Length(3, 99)])
    animal3 = SelectField(u'animal3', choices=copy.copy(images),
                          validators=[Required(), Length(3, 99)])
    animal4 = SelectField(u'animal4', choices=copy.copy(images),
                          validators=[Required(), Length(3, 99)])
    firstname = StringField('firstname', id='firstname',
                            validators=[Length(1, 80)])

    password = StringField('Password', validators=[Required(), Length(2, 80)])


class Register(Form):
    email = StringField('Email', validators=[Required(), Length(1, 64),
                                             Email()])
    password1 = PasswordField('Password', validators=[Required()])
    password2 = PasswordField('Password', validators=[Required()])
    firstname = StringField('First Name',
                            validators=[Length(1, 80)])
    captcha = StringField('Captcha Answer',
                          validators=[Required(), Length(1, 20)])
    money_symbol = StringField(
        'Money Symbol', default="$",
        validators=[Required(),
                    Length(min=1, max=2,
                           message="Must be one or two characters")])
    # Used when updating
    oldpassword = PasswordField('Password')


class AccountUpdate(Form):
    email = StringField('Email', validators=[Required(), Length(1, 64),
                                             Email()])
    password1 = PasswordField('Password')
    password2 = PasswordField('Password')
    firstname = StringField('First Name',
                            validators=[Length(1, 80)])
    money_symbol = StringField(
        'Money Symbol', default="$",
        validators=[Required(),
                    Length(min=1, max=2,
                           message="Must be one or two characters")])
    # Used when updating
    oldpassword = PasswordField('Password')


class RegisterChild1(Form):
    animal1 = SelectField(u'animal1', choices=images,
                          validators=[Required(), Length(3, 99)])
    animal2 = SelectField(u'animal2', choices=copy.copy(images),
                          validators=[Required(), Length(3, 99)])
    animal3 = SelectField(u'animal3', choices=copy.copy(images),
                          validators=[Required(), Length(3, 99)])
    animal4 = SelectField(u'animal4', choices=copy.copy(images),
                          validators=[Required(), Length(3, 99)])
    firstname = StringField('firstname', id='firstname',
                            validators=[Length(1, 80)])

    password = StringField('Password', validators=[Required(), Length(2, 80)])
    acct1_name = StringField('Account', id='acct1_name', default="Spending",
                             validators=[RequiredIf('acct1_used'),
                                         Optional(),  Length(1, 80)])
    acct1_used = BooleanField('Active', id='acct1_used', default=True)
    acct1_comment = StringField('Description', id='acct1_comment',
                                validators=[Length(0, 512)])

    location1_name = StringField('Where is Money', id='location1_name',
                                 default="Mom/Dad's wallet",
                                 validators=[Optional(),
                                             RequiredIf('location1_used',),
                                             Length(1, 80)])
    location1_used = BooleanField('Active', id='location1_used', default=True)
    location1_comment = StringField('Description', id='location1_comment',
                                    validators=[Length(0, 512)])
    initial_animal1 = HiddenField(id='initial_animal1')
    initial_animal2 = HiddenField(id='initial_animal2')

    app.logger.info('Constructing remaining fields in RegisterChild1("Form")')
    for i in xrange(2, 6):
        field = "acct%s_name = StringField('Account', id='acct%s_name', "
        field += "validators=[RequiredIf('acct%s_used'), Optional(), "
        field += "Length(2, 80)])"
        field = field % (i, i, i)
        app.logger.info("\n" + field)
        exec(field)
        field = "acct%s_used = BooleanField('Active', id='acct%s_used')"
        field = field % (i, i)
        app.logger.info("\n" + field)
        exec(field)
        field = "acct%s_comment = StringField('Description', "
        field += "id='acct%s_comment', validators="
        field += "[Optional(), Length(1, 80)])"
        field = field % (i, i)
        app.logger.info("\n" + field)
        exec(field)
    for i in xrange(2, 8):
        field = "location%i_name = StringField('Where is Money', id="
        field += "'location%s_name', validators=[Optional(), Length(1, 80)])"
        field = field % (i, i)
        app.logger.info("\n" + field)
        exec(field)
        field = "location%s_used = BooleanField('Active', id="
        field += "'location%s_used')"
        field = field % (i, i)
        app.logger.info("\n" + field)
        exec(field)
        field = "location%s_comment = StringField('Description', id="
        field += "'location%s_comment', validators=[Optional(), "
        field += "Length(0, 512)])"
        field = field % (i, i)
        app.logger.info("\n" + field)
        exec(field)


# Custom setup for our checkbox
class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()
    params = widgets.html_params(style="width: 10px;")


class Allowance(Form):
    amount = FloatField('amount', validators=[NumberRange(
        min=.01, max=500,
        message='Accepted value range for amount is .01 to 500')])
    payout_days = MultiCheckboxField(u'payout_days', choices=days_of_month,
                                     validators=[Required()])
    nickname = StringField(
        '(nickname) Way to remind you what <br>is being payed ' +
        'out in the ledger', default='Allowance')
    acct1_perc = FloatField(
        'account_perc1',
        validators=[Optional(), NumberRange(min=0, max=100)], default=100)
    acct2_perc = FloatField(
        'account_perc2',
        validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    acct3_perc = FloatField(
        'account_perc3',
        validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    acct4_perc = FloatField(
        'account_perc4',
        validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    acct5_perc = FloatField(
        'account_perc5',
        validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    location1_perc = FloatField(
        'location_perc1', validators=[Optional(), NumberRange(min=0, max=100)],
        default=100)
    location2_perc = FloatField(
        'location_perc2', validators=[Optional(), NumberRange(min=0, max=100)],
        default=0)
    location3_perc = FloatField(
        'location_perc3', validators=[Optional(), NumberRange(min=0, max=100)],
        default=0)
    location4_perc = FloatField(
        'location_perc4', validators=[Optional(), NumberRange(min=0, max=100)],
        default=0)
    location5_perc = FloatField(
        'location_perc5', validators=[Optional(), NumberRange(min=0, max=100)],
        default=0)
    location6_perc = FloatField(
        'location_perc6', validators=[Optional(), NumberRange(min=0, max=100)],
        default=0)
    location7_perc = FloatField(
        'location_perc7', validators=[Optional(), NumberRange(min=0, max=100)],
        default=0)


class Ledger(Form):
    acct1_loc1 = FloatField(
        'acc1_loc1',
        validators=[Optional(), NumberRange(min=-1000, max=1000)],
        render_kw={"placeholder": "0"})
    acct1_loc2 = FloatField(
        'acc1_loc2',
        validators=[Optional(), NumberRange(min=-1000, max=1000)],
        render_kw={"placeholder": "0"})
    acct1_loc3 = FloatField(
        'acc1_loc3',
        validators=[Optional(), NumberRange(min=-1000, max=1000)],
        render_kw={"placeholder": "0"})
    acct1_loc4 = FloatField(
        'acc1_loc4',
        validators=[Optional(), NumberRange(min=-1000, max=1000)],
        render_kw={"placeholder": "0"})
    acct1_loc5 = FloatField(
        'acc1_loc5',
        validators=[Optional(), NumberRange(min=-1000, max=1000)],
        render_kw={"placeholder": "0"})
    acct1_loc6 = FloatField(
        'acc1_loc6',
        validators=[Optional(), NumberRange(min=-1000, max=1000)],
        render_kw={"placeholder": "0"})
    acct1_loc7 = FloatField(
        'acc1_loc7',
        validators=[Optional(), NumberRange(min=-1000, max=1000)],
        render_kw={"placeholder": "0"})
    comment = TextAreaField(
        'comment', id='comment', validators=[Optional(),
                                             Length(min=1, max=200)])

    app.logger.info('Constructing remaining fields in Ledger("Form")')
    for i in range(2, 6):
        for j in range(1, 8):
            field = "acct%s_loc%s = FloatField('acct%s_loc%s'," % (i, j, i, j)
            field += "validators=[Optional(), NumberRange(min=-1000, max=1000"
            field += ')], render_kw={"placeholder": "0"})'
            app.logger.info("\n" + field)
            exec(field)


class ChildDelete(Form):
    really_means_it = BooleanField('Yes! really delete')
