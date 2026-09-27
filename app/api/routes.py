# Copyright (C) 2016  name of Zsolt Szabo zsoltman@hotmail.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
'''JSON endpoints.

Every handler here is thin on purpose: resolve the actor, resolve the kid
through the one ownership check, call a service, serialise. No rule is
re-implemented, so while both UIs are live there is one copy of each.

Errors are not caught: services raise DomainError and app/api/errors.py
turns it into the JSON envelope with the right status.
'''
import logging

from flask import current_app, jsonify, request, session
from flask_login import login_user, logout_user
from flask_wtf.csrf import generate_csrf
from spectree import Response

from app import auth
from app import db
from app import models
from app.api import api_bp, schemas, serializers, spec
from app.domain import animals as animal_domain
from app.domain import buckets
from app.services import allowances as allowance_service
from app.services import captcha as captcha_service
from app.services import errors
from app.services import kids as kid_service
from app.services import ledger as ledger_service
from app.services import parents as parent_service
from app.services import payout as payout_service

logger = logging.getLogger(__name__)

AUTH = 'auth'
KIDS = 'kids'
MONEY = 'money'


def _actor_payload(actor):
    if actor.is_parent:
        user = db.session.get(models.User, actor.parent_id)
        return {'kind': 'parent', 'id': actor.parent_id,
                'firstname': user.firstname if user else None,
                'moneySymbol': user.money_symbol if user else None}
    kid = db.session.get(models.Kid, actor.kid_id)
    parent = (db.session.get(models.User, kid.parent_id)
              if kid is not None else None)
    return {'kind': 'child', 'id': actor.kid_id,
            'firstname': kid.firstname if kid else None,
            'moneySymbol': parent.money_symbol if parent else None}


def _parent_payload(user):
    return {'id': user.id, 'email': user.email,
            'firstname': user.firstname,
            'moneySymbol': user.money_symbol,
            'isGoogle': bool(user.isgoogle)}


def _confirmed():
    """Whether the caller passed ?confirm=true on a destructive route."""
    return request.args.get('confirm', '').lower() == 'true'


def _money_symbol_for(kid):
    parent = db.session.get(models.User, kid.parent_id)
    return parent.money_symbol if parent else '$'


# --- session --------------------------------------------------------------

@api_bp.route('/csrf', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.CsrfOut), tags=[AUTH])
def csrf_token():
    '''A CSRF token for a JSON client to send back as X-CSRFToken.'''
    return jsonify(token=generate_csrf())


@api_bp.route('/auth/session', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.SessionOut), tags=[AUTH])
def session_info():
    '''Who is signed in. 200 even when nobody is, so the SPA can decide
    which of the three landing states to render without treating "logged
    out" as an error.'''
    actor = auth.current_actor()
    if actor is None:
        return jsonify(authenticated=False, actor=None)
    return jsonify(authenticated=True, actor=_actor_payload(actor))


@api_bp.route('/auth/parent/login', methods=['POST'])
@spec.validate(json=schemas.ParentLoginIn,
               resp=Response(HTTP_200=schemas.SessionOut,
                             HTTP_401=schemas.ErrorResponse), tags=[AUTH])
def parent_login():
    body = request.context.json
    user = parent_service.authenticate(body.email, body.password)
    login_user(user)
    return jsonify(authenticated=True,
                   actor=_actor_payload(auth.Actor.parent(user.id)))


@api_bp.route('/auth/child/login', methods=['POST'])
@spec.validate(json=schemas.ChildLoginIn,
               resp=Response(HTTP_200=schemas.SessionOut,
                             HTTP_401=schemas.ErrorResponse), tags=[AUTH])
def child_login():
    body = request.context.json
    kid = models.Kid.query.filter(
        models.Kid.firstname == body.firstname,
        models.Kid.animal1 == body.animal1,
        models.Kid.animal2 == body.animal2,
        models.Kid.pw == body.password,
        models.Kid.animal3 == body.animal3,
        models.Kid.animal4 == body.animal4).first()
    if kid is None:
        raise errors.Unauthenticated('Child login not found',
                                     code='auth.bad_child_login')
    login_user(kid)
    return jsonify(authenticated=True,
                   actor=_actor_payload(auth.Actor.child(kid.id)))


@api_bp.route('/auth/logout', methods=['POST'])
@spec.validate(resp=Response(HTTP_200=schemas.OkOut), tags=[AUTH])
def logout():
    '''POST, not GET: logging out is a state change and must not be
    reachable from an <img> tag.'''
    logout_user()
    return jsonify(ok=True)


@api_bp.route('/auth/captcha', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.CaptchaOut), tags=[AUTH])
def get_captcha():
    """Issue a registration captcha and remember the answer.

    Kept in the session exactly as the Jinja flow does, so both
    registration paths validate against the same stored value.
    """
    cap = captcha_service.get_captcha()
    session['cap_solution'] = cap.solution
    return jsonify(operation=cap.operation,
                   firstDigits=['/' + p for p in cap.firstnum_links],
                   secondDigits=['/' + p for p in cap.secondnum_links])


@api_bp.route('/parents', methods=['POST'])
@spec.validate(json=schemas.ParentCreateIn,
               resp=Response(HTTP_201=schemas.ParentOut,
                             HTTP_409=schemas.ErrorResponse), tags=[AUTH])
def register_parent():
    """Register, and sign the new parent in."""
    body = request.context.json
    expected = session.pop('cap_solution', None)
    if expected is None or \
            body.captcha != str(expected).replace(' ', ''):
        raise errors.ValidationFailed('Captcha values did not match',
                                      code='parent.bad_captcha',
                                      field_errors={'captcha': ['incorrect']})

    user = parent_service.create(email=body.email, firstname=body.firstname,
                                 password=body.password,
                                 money_symbol=body.moneySymbol)
    login_user(user)
    return jsonify(_parent_payload(user)), 201


@api_bp.route('/me', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.ParentOut,
                             HTTP_403=schemas.ErrorResponse), tags=[AUTH])
def get_me():
    actor = auth.require_parent()
    return jsonify(_parent_payload(
        db.session.get(models.User, actor.parent_id)))


@api_bp.route('/me', methods=['PATCH'])
@spec.validate(json=schemas.ParentUpdateIn,
               resp=Response(HTTP_200=schemas.ParentOut,
                             HTTP_403=schemas.ErrorResponse), tags=[AUTH])
def update_me():
    """Change your own name, currency symbol or password.

    A password change needs the current one. The shared demo account is
    not allowed to change either its address or its password, since
    everyone is invited to sign in as it.
    """
    actor = auth.require_parent()
    user = db.session.get(models.User, actor.parent_id)
    body = request.context.json

    if body.newPassword:
        if parent_service.is_demo_account(user.id):
            raise errors.Forbidden(
                'The evaluation account cannot change its password',
                code='parent.demo_immutable')
        if user.isgoogle:
            raise errors.Forbidden(
                'This account signs in with Google',
                code='parent.google_managed')
        if not body.oldPassword or not user.check_password(body.oldPassword):
            raise errors.Unauthenticated(
                'Old password did not match',
                code='parent.bad_old_password')
        user.set_password(body.newPassword)

    if body.firstname is not None:
        user.firstname = body.firstname
    if body.moneySymbol is not None:
        user.money_symbol = body.moneySymbol
    db.session.commit()
    return jsonify(_parent_payload(user))


@api_bp.route('/me', methods=['DELETE'])
@spec.validate(resp=Response(HTTP_200=schemas.OkOut,
                             HTTP_403=schemas.ErrorResponse), tags=[AUTH])
def delete_me():
    """Delete your account and every child record under it.

    Confirmation is ?confirm=true rather than a body: request bodies on
    DELETE are poorly supported and are not parsed here.
    """
    actor = auth.require_parent()
    if not _confirmed():
        raise errors.ValidationFailed(
            'You must click the box declaring you really mean it',
            code='parent.not_confirmed',
            field_errors={'confirm': ['required']})

    user = db.session.get(models.User, actor.parent_id)
    logout_user()
    parent_service.delete_with_children(user)
    return jsonify(ok=True)


@api_bp.route('/kids/<int:kid_id>', methods=['DELETE'])
@spec.validate(resp=Response(HTTP_200=schemas.OkOut,
                             HTTP_404=schemas.ErrorResponse), tags=[KIDS])
def delete_kid(kid_id):
    """Delete a child and all their money history.

    Confirmation is ?confirm=true; see delete_me.
    """
    actor = auth.require_parent()
    kid = auth.resolve_kid(actor, kid_id)
    if not _confirmed():
        raise errors.ValidationFailed(
            'You must click the box declaring you really mean it',
            code='kid.not_confirmed',
            field_errors={'confirm': ['required']})
    kid_service.delete_kid(kid)
    return jsonify(ok=True)


# --- dashboard ------------------------------------------------------------

@api_bp.route('/dashboard', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.DashboardOut,
                             HTTP_401=schemas.ErrorResponse), tags=[KIDS])
def dashboard():
    '''The home screen: a parent sees their kids, a child sees themselves.'''
    actor = auth.require_actor()

    if actor.is_parent:
        kids = models.Kid.query.filter(
            models.Kid.parent_id == actor.parent_id).all()
    else:
        kids = [auth.resolve_kid(actor, actor.kid_id)]

    #  Parity with the Jinja index, which calls the payout engine on every
    #  page load. Without this the SPA would silently stop paying
    #  allowances for any family that never opens the old UI.
    #
    #  Must happen BEFORE the balances are read: a payout made here has to
    #  be reflected in the totals this same response reports.
    if current_app.config.get('PAYOUT_ON_DASHBOARD_READ'):
        due = []
        for kid in kids:
            due.extend(payout_service.due_rows_for_kid(kid))
        if due:
            payout_service.check_and_update_allowances(due)
            db.session.commit()

    summaries = []
    total_owed = 0.0
    monthly_outlay = 0.0
    for kid in kids:
        last = ledger_service.latest_entry(kid)
        balance = buckets.grand_total(last) if last is not None else 0
        total_owed += balance
        summaries.append(serializers.kid_summary(kid, balance))
        for row in allowance_service.list_for_kid(kid):
            monthly_outlay += (row.amount or 0) * len(row.DATES)

    payload = _actor_payload(actor)
    return jsonify(actor=payload,
                   kids=summaries,
                   totalOwed=round(total_owed, 2),
                   monthlyOutlay=round(monthly_outlay, 2),
                   moneySymbol=payload.get('moneySymbol') or '$')


# --- kids -----------------------------------------------------------------

@api_bp.route('/kids', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.KidListOut,
                             HTTP_401=schemas.ErrorResponse), tags=[KIDS])
def list_kids():
    actor = auth.require_actor()
    if actor.is_parent:
        kids = models.Kid.query.filter(
            models.Kid.parent_id == actor.parent_id).all()
    else:
        kids = [auth.resolve_kid(actor, actor.kid_id)]
    out = []
    for kid in kids:
        last = ledger_service.latest_entry(kid)
        out.append(serializers.kid_summary(
            kid, buckets.grand_total(last) if last is not None else 0))
    return jsonify(kids=out)


@api_bp.route('/kids', methods=['POST'])
@spec.validate(json=schemas.KidCreateIn,
               resp=Response(HTTP_201=schemas.KidOut,
                             HTTP_409=schemas.ErrorResponse), tags=[KIDS])
def create_kid():
    """Register a child under the signed-in parent."""
    actor = auth.require_parent()
    body = request.context.json

    kid = kid_service.create_kid(
        parent_id=actor.parent_id,
        firstname=body.firstname,
        password=body.password,
        animals=tuple(body.loginAnimals) + tuple(body.passwordAnimals),
        accounts=[b.model_dump() for b in body.accounts],
        locations=[b.model_dump() for b in body.locations])
    return jsonify(serializers.kid_detail(kid)), 201


@api_bp.route('/kids/<int:kid_id>', methods=['PATCH'])
@spec.validate(json=schemas.KidUpdateIn,
               resp=Response(HTTP_200=schemas.KidUpdateOut,
                             HTTP_404=schemas.ErrorResponse), tags=[KIDS])
def update_kid(kid_id):
    """Change a child's credentials or buckets.

    Switching a bucket off redistributes any allowance percentage pointed
    at it. Allowances that could not be repaired -- because nothing funded
    survived -- come back in orphanedAllowances for the parent to
    recreate, which is what the Jinja screen flashes.
    """
    actor = auth.require_parent()
    kid = auth.resolve_kid(actor, kid_id)
    body = request.context.json

    animals = None
    if body.loginAnimals is not None or body.passwordAnimals is not None:
        login_pair = body.loginAnimals or [kid.animal1, kid.animal2]
        password_pair = body.passwordAnimals or [kid.animal3, kid.animal4]
        animals = tuple(login_pair) + tuple(password_pair)

    kid, orphaned = kid_service.update_kid(
        kid,
        firstname=body.firstname,
        password=body.password,
        animals=animals,
        accounts=([b.model_dump() for b in body.accounts]
                  if body.accounts is not None else None),
        locations=([b.model_dump() for b in body.locations]
                   if body.locations is not None else None))
    return jsonify(kid=serializers.kid_detail(kid),
                   orphanedAllowances=orphaned)


@api_bp.route('/kids/available-animal-pairs', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.AnimalPairsOut,
                             HTTP_401=schemas.ErrorResponse), tags=[KIDS])
def available_animal_pairs():
    '''Animal pairs still free for a nickname, for the registration screen.'''
    auth.require_parent()
    firstname = request.args.get('firstname', '')
    pairs = kid_service.available_animal_pairs(firstname)
    return jsonify(firstname=firstname,
                   availablePairs=sorted([a, b] for a, b in pairs))


@api_bp.route('/kids/<int:kid_id>', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.KidOut,
                             HTTP_404=schemas.ErrorResponse), tags=[KIDS])
def get_kid(kid_id):
    '''A child's settings.

    The password is only included for the owning parent, and only on
    request -- it is stored in clear text so a parent can read it back to
    their child, but it should not travel in every response.
    '''
    actor = auth.require_actor()
    kid = auth.resolve_kid(actor, kid_id)
    wants_password = request.args.get('includePassword') == 'true'
    return jsonify(serializers.kid_detail(
        kid, include_password=wants_password and actor.is_parent))


@api_bp.route('/animals', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.AnimalListOut), tags=[KIDS])
def list_animals():
    '''The animal alphabet a child login is built from.'''
    return jsonify(animals=[{'key': name, 'imageUrl': '/' + path}
                            for name, path in animal_domain.images])


# --- allowances -----------------------------------------------------------

@api_bp.route('/kids/<int:kid_id>/allowances', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.AllowanceListOut,
                             HTTP_404=schemas.ErrorResponse), tags=[MONEY])
def list_allowances(kid_id):
    actor = auth.require_actor()
    kid = auth.resolve_kid(actor, kid_id)
    rows = allowance_service.list_for_kid(kid)
    return jsonify(allowances=[serializers.allowance(r) for r in rows])


@api_bp.route('/kids/<int:kid_id>/allowances', methods=['POST'])
@spec.validate(json=schemas.AllowanceCreateIn,
               resp=Response(HTTP_201=schemas.AllowanceOut,
                             HTTP_403=schemas.ErrorResponse), tags=[MONEY])
def create_allowance(kid_id):
    '''Children may view allowances but never create them.'''
    actor = auth.require_parent()
    kid = auth.resolve_kid(actor, kid_id)
    body = request.context.json

    row, failed_days = allowance_service.create(
        kid=kid, amount=body.amount, nickname=body.nickname,
        payout_days=body.payoutDays,
        account_percs=body.accountPercents,
        location_percs=body.locationPercents)
    if failed_days:
        logger.error('Allowance %s: payout days not stored: %s'
                     % (row.id, failed_days))
    row.DATES = [d for d in body.payoutDays if d not in failed_days]
    return jsonify(serializers.allowance(row)), 201


@api_bp.route('/allowances/<int:allowance_id>', methods=['DELETE'])
@spec.validate(resp=Response(HTTP_200=schemas.OkOut,
                             HTTP_404=schemas.ErrorResponse), tags=[MONEY])
def delete_allowance(allowance_id):
    '''DELETE, not GET.

    The Jinja screen still removes an allowance with a GET, which means an
    <img src> can delete one. That route goes away at cutover.
    '''
    actor = auth.require_parent()
    row = auth.resolve_allowance(actor, allowance_id)
    allowance_service.delete(row)
    return jsonify(ok=True)


# --- ledger ---------------------------------------------------------------

@api_bp.route('/kids/<int:kid_id>/ledger', methods=['GET'])
@spec.validate(resp=Response(HTTP_200=schemas.LedgerOut,
                             HTTP_404=schemas.ErrorResponse), tags=[MONEY])
def get_ledger(kid_id):
    actor = auth.require_actor()
    kid = auth.resolve_kid(actor, kid_id)
    entries = ledger_service.entries_for_kid(kid)
    newest = entries[0] if entries else None
    visible_accounts, visible_locations = ledger_service.visible_slots(
        kid, newest)

    return jsonify(
        kid=serializers.kid_detail(kid),
        entries=[serializers.ledger_entry(e) for e in entries],
        grandTotal=buckets.grand_total(newest) if newest else 0,
        moneySymbol=_money_symbol_for(kid),
        visibleAccounts=visible_accounts,
        visibleLocations=visible_locations)


@api_bp.route('/kids/<int:kid_id>/ledger/entries', methods=['POST'])
@spec.validate(json=schemas.LedgerEntryIn,
               resp=Response(HTTP_201=schemas.LedgerEntryOut,
                             HTTP_403=schemas.ErrorResponse), tags=[MONEY])
def post_ledger_entry(kid_id):
    '''Add or subtract money. A child may only subtract.'''
    actor = auth.require_actor()
    kid = auth.resolve_kid(actor, kid_id)
    body = request.context.json

    if actor.is_parent:
        adjuster = db.session.get(models.User, actor.parent_id).firstname
    else:
        adjuster = kid.firstname

    entry = ledger_service.post_ledger_entry(
        actor=actor,
        kid=kid,
        last_entry=ledger_service.latest_entry(kid),
        cells=serializers.cells_from_payload(
            [c.model_dump() for c in body.cells]),
        #  Normalised to a string on purpose. The service reads
        #      if comment is None or comment == "" and no_comment is not True
        #  and `and` binds tighter than `or`, so a None comment short-
        #  circuits and defeats the noComment opt-out. A browser always
        #  submits the textarea so Jinja never hits it; a JSON client that
        #  omits the field would. The service keeps its behaviour, which is
        #  pinned by test_KNOWN_BUG_no_comment_is_ignored_when_comment_
        #  field_is_absent, and is fixed properly in Stage 5.
        comment=body.comment or '',
        no_comment=body.noComment,
        adjuster_name=adjuster,
        adjusted_by_parent=actor.is_parent)
    return jsonify(serializers.ledger_entry(entry)), 201


# --- cron -----------------------------------------------------------------

@api_bp.route('/payouts/run', methods=['POST'])
@spec.validate(resp=Response(HTTP_200=schemas.OkOut,
                             HTTP_403=schemas.ErrorResponse), tags=[MONEY])
def run_payouts():
    '''Trigger the allowance payout sweep.

    Guarded by a shared secret rather than a session, because the caller
    is cron. Disabled unless PAYOUT_TRIGGER_TOKEN is configured.
    '''
    expected = current_app.config.get('PAYOUT_TRIGGER_TOKEN')
    supplied = request.headers.get('X-Payout-Token')
    if not expected or not supplied or supplied != expected:
        raise errors.Forbidden('Not permitted', code='payouts.forbidden')
    payout_service.run_payouts()
    return jsonify(ok=True)
