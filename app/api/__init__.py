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
from typing import Annotated, get_args, get_origin

from flask import Blueprint
from spectree import SpecTree

api_bp = Blueprint('api', __name__)


def _schema_name(model):
    """Plain model names in the spec.

    spectree defaults to appending a hash of the module path
    (KidOut.3a64a9f) so that identically named models in different modules
    cannot collide. Those names become TypeScript type names, so the hash
    is worth dropping -- every model here lives in app/api/schemas.py and
    is already unique.

    Mirrors spectree.utils.get_model_key's name derivation, without the
    suffix; it is handed the model class, not a string.
    """
    origin = get_origin(model)
    if origin is Annotated:
        args = get_args(model)
        for metadata in reversed(args[1:]):
            title = getattr(metadata, 'title', None)
            if title:
                return str(title)
        return _schema_name(args[0])
    if origin is list:
        args = get_args(model)
        return (_schema_name(args[0]) if args else 'Any') + 'List'
    return model.__name__


spec = SpecTree(
    'flask',
    title='kidallowance API',
    version='0.1.0',
    path='apidoc',
    naming_strategy=_schema_name,
    security_schemes=[],
)


def init_app(app):
    """Mount the API on an application.

    The blueprint itself is fully configured at import time (below), not
    here: a Flask blueprint may only be set up once, and create_app can be
    called more than once -- the module-level app, plus one per test.
    """
    from app.api import errors

    errors.init_app(app)
    app.register_blueprint(api_bp, url_prefix='/api')


#  Import order matters. The endpoints attach themselves to api_bp, then
#  spectree adds the /apidoc routes to the same blueprint. Registering the
#  spec on the blueprint rather than on the app is what scopes the
#  description to /api: spectree filters by the blueprint's url_prefix,
#  and registering on the app would sweep in every Jinja route, emitting
#  meaningless paths and types into the generated TypeScript client.
from app.api import routes  # noqa: E402,F401  (attaches the endpoints)

spec.register(api_bp)
