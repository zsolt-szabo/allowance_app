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
'''Errors the service layer raises instead of flashing and redirecting.

Today's handlers signal failure by calling ``flash("ERROR: ...")`` and
returning a falsy value, which means the only way to find out what went wrong
is to scrape the flash queue.  Services raise these instead, so the same rule
can serve a Jinja page (flash the message, redirect) and a JSON endpoint
(serialise the code, return a status) without the rule knowing which.

``message`` is deliberately kept byte-identical to the current flash text.
That lets the parity harness assert the same strings before and after the
port, and means users see unchanged wording.

``code`` is the machine-readable half, for the eventual API error envelope:

    {"error": {"code": "allowance.accounts_not_100",
               "message": "Allowance distribution among sub-accounts must "
                          "add up to 100%",
               "fieldErrors": {...}}}
'''


class DomainError(Exception):
    '''A rule was broken. Carries both a human message and a stable code.'''

    #: Default HTTP status for this class of error.
    status = 400
    code = 'error'

    def __init__(self, message, code=None, status=None, field_errors=None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status is not None:
            self.status = status
        #: {field_name: [message, ...]}
        self.field_errors = field_errors or {}

    def __str__(self):
        return self.message

    def as_dict(self):
        return {'error': {'code': self.code,
                          'message': self.message,
                          'fieldErrors': self.field_errors}}


class NotFound(DomainError):
    '''The thing does not exist, or does not belong to this actor.

    Deliberately does not distinguish those two cases: telling a parent that
    someone else's kid id exists would leak the other family's data.
    '''
    status = 404
    code = 'not_found'

    def __init__(self, what='resource', message=None, **kwargs):
        super().__init__(message or 'Could not find %s' % what, **kwargs)


class Forbidden(DomainError):
    '''The actor is real but is not allowed to do this.

    Most importantly: a child may subtract money but never add it.
    '''
    status = 403
    code = 'forbidden'


class Unauthenticated(DomainError):
    '''Nobody is signed in.'''
    status = 401
    code = 'unauthenticated'


class Conflict(DomainError):
    '''Collides with something that already exists.

    Chiefly the globally unique (firstname, animal1, animal2) child login.
    '''
    status = 409
    code = 'conflict'


class ValidationFailed(DomainError):
    '''Input was malformed or broke a cross-field rule.

    e.g. allowance percentages that do not total exactly 100.
    '''
    status = 400
    code = 'validation_failed'
