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
'''Who is making this request, and which kids may they touch.

Two separate tables act as identities -- ``User`` (a parent) and ``Kid`` (a
child) -- sharing one Flask-Login session.  The original design keeps them
apart by storing them under deliberately different names, ``g.user_id`` versus
``g.kid_id``, so that a child id can never be mistaken for a parent id.  The
comment in app/views.py explains the intent.

``Actor`` preserves that property and makes it checkable instead of implicit:
``parent_id`` is ``None`` for a child, so code that reaches for a parent id
when a child is signed in gets ``None`` rather than a plausible-looking
number.  It also fixes a real bug class -- today a child hitting a parent-only
handler raises ``AttributeError: user_id`` and returns a 500, because
``g.user_id`` was simply never set.

``resolve_kid`` is the important function here.  The ownership check it
performs is currently written out by hand in five places (a_finance.allowances,
a_finance.ledger twice, a_child_login.kid_account_review,
a_child_login.delete_kid).  It is correct in all five, which is luck rather
than design; there should be one of it, with one set of tests.
'''
import functools
import logging

from flask import g

from app import models
from app.services import errors

logger = logging.getLogger(__name__)

PARENT = 'parent'
CHILD = 'child'


class Actor:
    '''The authenticated identity behind the current request.

    Immutable on purpose: nothing downstream should be able to promote a child
    into a parent by assignment.
    '''

    __slots__ = ('kind', 'parent_id', 'kid_id')

    def __init__(self, kind, parent_id=None, kid_id=None):
        object.__setattr__(self, 'kind', kind)
        object.__setattr__(self, 'parent_id', parent_id)
        object.__setattr__(self, 'kid_id', kid_id)

    def __setattr__(self, name, value):
        raise AttributeError('Actor is immutable')

    @classmethod
    def parent(cls, parent_id):
        return cls(PARENT, parent_id=parent_id)

    @classmethod
    def child(cls, kid_id):
        return cls(CHILD, kid_id=kid_id)

    @property
    def is_parent(self):
        return self.kind == PARENT

    @property
    def is_child(self):
        return self.kind == CHILD

    def __repr__(self):
        if self.is_parent:
            return '<Actor parent id=%s>' % self.parent_id
        return '<Actor child id=%s>' % self.kid_id

    def __eq__(self, other):
        if not isinstance(other, Actor):
            return NotImplemented
        return (self.kind, self.parent_id, self.kid_id) == \
            (other.kind, other.parent_id, other.kid_id)

    def __hash__(self):
        return hash((self.kind, self.parent_id, self.kid_id))


def current_actor():
    '''The Actor for this request, or None when nobody is signed in.

    Reads the request context that Flask-Login's user_loader populates as a
    side effect (app/views.py:load_user).  Stage 2 replaces that with an
    explicit loader; until then this is the single place that knows the shape
    of it.
    '''
    if getattr(g, 'is_child', False) is True and getattr(g, 'kid_id', None):
        return Actor.child(g.kid_id)
    user_id = getattr(g, 'user_id', None)
    if user_id is not None:
        return Actor.parent(user_id)
    return None


def require_actor():
    '''The current Actor, or raise Unauthenticated.'''
    actor = current_actor()
    if actor is None:
        raise errors.Unauthenticated('You must be signed in')
    return actor


def require_parent():
    '''The current Actor, which must be a parent.

    A child reaching a parent-only operation is a clean 403, not a 500.
    '''
    actor = require_actor()
    if not actor.is_parent:
        raise errors.Forbidden('Only a parent can do this')
    return actor


def parent_required(view):
    '''Decorator form of :func:`require_parent` for view functions.'''
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        require_parent()
        return view(*args, **kwargs)
    return wrapper


def resolve_kid(actor, kid_id):
    '''The Kid with this id, if this actor is allowed to see it.

    A parent may reach any kid whose ``parent_id`` is theirs; a child may
    reach only their own row.  Anything else is NotFound rather than
    Forbidden, so that probing ids cannot confirm another family's data.
    '''
    query = models.Kid.query.filter(models.Kid.id == kid_id)
    if actor.is_parent:
        query = query.filter(models.Kid.parent_id == actor.parent_id)
    else:
        query = query.filter(models.Kid.id == actor.kid_id)

    kid = query.one_or_none()
    if kid is None:
        logger.warning('%r denied access to kid id %s' % (actor, kid_id))
        raise NotFoundKid()
    return kid


def resolve_kid_by_login(actor, firstname, animal1, animal2):
    '''Same ownership rules, addressing the kid by their login triple.

    The Jinja screens identify a kid in the URL as
    ``firstname:animal1:animal2``.  Stage 2 replaces that with the numeric id;
    this exists so the transitional handlers have one implementation to call.
    '''
    query = models.Kid.query.filter(
        models.Kid.firstname == firstname,
        models.Kid.animal1 == animal1,
        models.Kid.animal2 == animal2)
    if actor.is_parent:
        query = query.filter(models.Kid.parent_id == actor.parent_id)
    else:
        query = query.filter(models.Kid.id == actor.kid_id)

    kid = query.one_or_none()
    if kid is None:
        logger.warning('%r denied access to kid (%s:%s:%s)'
                       % (actor, firstname, animal1, animal2))
        raise NotFoundKid()
    return kid


def parse_kid_triple(kid_string):
    '''Split a ``firstname:animal1:animal2`` URL fragment.

    Raises ValidationFailed rather than returning a partial list, which is how
    a_finance currently ends up dereferencing None.
    '''
    if not kid_string or kid_string.count(':') != 2:
        raise errors.ValidationFailed(
            'Failed to extract child info given, error reported!',
            code='kid.bad_reference')
    return tuple(kid_string.split(':'))


class NotFoundKid(errors.NotFound):
    '''Wording preserved from the current flash message.'''
    code = 'kid.not_found'

    def __init__(self):
        super().__init__(message='Problem getting child data, error logged')
