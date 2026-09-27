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
'''The JSON API.

Mounted at /api alongside the Jinja screens, which keep working unchanged
until the SPA replaces them. Nothing here re-implements a rule: every
endpoint calls the same service the Jinja handler calls, so during the
transition there is exactly one copy of each rule.
'''
from flask import Blueprint
from spectree import SpecTree

api_bp = Blueprint('api', __name__)


def _schema_name(name, route=None, **kwargs):
    '''Plain model names in the spec.

    spectree defaults to appending a hash (Kid.3a64a9f) to avoid
    collisions. Those names end up in the generated TypeScript, so keep
    them readable; our model names are already unique.
    '''
    return name


spec = SpecTree(
    'flask',
    title='kidallowance API',
    version='0.1.0',
    path='apidoc',
    naming_strategy=_schema_name,
    security_schemes=[],
)


def init_app(app):
    '''Mount the API on an application.'''
    from app.api import routes  # noqa: F401  (registers the endpoints)
    from app.api import errors

    errors.init_app(app)
    app.register_blueprint(api_bp, url_prefix='/api')
    spec.register(app)
