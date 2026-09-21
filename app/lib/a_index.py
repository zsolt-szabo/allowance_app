from flask import render_template
from flask_login import current_user
from app import models
import app
from app.services import payout
import logging


logger = logging.getLogger(__name__)


def process_view():
    user = current_user
    name = ''
    kids = []
    is_child = False
    total_owed = 0
    monthly_outlay = 0
    money_symbol = ''
    allow = []
    if user is not None and user.get_id() is not None and \
            type(user.get_id()).__name__ != 'tuple':
        # User is Parent
        kids = models.Kid.query.filter(models.Kid.parent_id == user.id)
        name = user.firstname
        money_symbol = user.money_symbol
        for each_kid in kids.all():
            tl = models.Ledger.query.filter(
                models.Ledger.kid_id == each_kid.id). \
                order_by(models.Ledger.id.desc()).first()
            if tl is not None:
                total_owed += tl.total_acc1 + tl.total_acc2 + tl.total_acc3 + \
                              tl.total_acc4 + tl.total_acc5
            kallow = app.db.session.query(
                models.Allowance, models.AllowanceDays).filter(
                models.Allowance.id == models.AllowanceDays.allowance_id). \
                filter(models.Allowance.kid_id == each_kid.id).all()
            allow += kallow
            for pay in kallow:
                monthly_outlay += pay[0].amount
    elif user is not None and user.get_id() is not None:
        # User is Kid
        name = user.firstname
        kids = models.Kid.query.filter(models.Kid.id == user.id)
        is_child = True
        for each_kid in kids.all():
            tl = models.Ledger.query.filter(
                models.Ledger.kid_id == each_kid.id). \
                order_by(models.Ledger.id.desc()).first()
            if tl is not None:
                total_owed += tl.total_acc1 + tl.total_acc2 + tl.total_acc3 + \
                              tl.total_acc4 + tl.total_acc5
            kallow = app.db.session.query(
                models.Allowance, models.AllowanceDays).filter(
                models.Allowance.id == models.AllowanceDays.allowance_id). \
                filter(models.Allowance.kid_id == each_kid.id).all()
            allow += kallow
    if user is not None and user.get_id() is not None:
        check_and_update_allowances(allow)
    return render_template('index.html', title='Home', name=name,
                           is_child=is_child, kids=kids,
                           total_owed=total_owed, money_symbol=money_symbol,
                           monthly_outlay=monthly_outlay)


#  The payout engine now lives in app/services/payout.py. Re-exported so the
#  cron script, the dashboard and the characterization tests keep one name
#  for it while Stage 2 moves callers over.
check_and_update_allowances = payout.check_and_update_allowances
