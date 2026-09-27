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
'''Rendering a DomainError as JSON.

A service raises the same exception whoever called it. The Jinja handler
catches it and flashes the message; here it becomes

    {"error": {"code": "...", "message": "...", "fieldErrors": {...}}}

with the exception's own status. `message` is deliberately the same text
the Jinja screens have always flashed, so the wording users see does not
change as screens move across.

Only requests under /api get JSON. A DomainError escaping a Jinja handler
keeps Flask's normal HTML error page, because an SPA-shaped body would be
useless there.
'''
import logging

from flask import jsonify, request

from app.services import errors

logger = logging.getLogger(__name__)


def _is_api_request():
    return request.path.startswith('/api/')


def init_app(app):
    @app.errorhandler(errors.DomainError)
    def handle_domain_error(exc):
        if not _is_api_request():
            raise exc
        logger.info('API %s -> %s (%s)'
                    % (request.path, exc.code, exc.status))
        return jsonify(exc.as_dict()), exc.status

    @app.errorhandler(404)
    def handle_not_found(exc):
        if not _is_api_request():
            return exc
        return jsonify({'error': {'code': 'not_found',
                                  'message': 'No such endpoint',
                                  'fieldErrors': {}}}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(exc):
        if not _is_api_request():
            return exc
        return jsonify({'error': {'code': 'method_not_allowed',
                                  'message': 'Method not allowed here',
                                  'fieldErrors': {}}}), 405

    @app.errorhandler(400)
    def handle_bad_request(exc):
        if not _is_api_request():
            return exc
        #  CSRF rejections arrive here; say so rather than returning a
        #  bare 400 that a client cannot act on.
        description = getattr(exc, 'description', '') or ''
        is_csrf = 'CSRF' in description or 'csrf' in description
        return jsonify({'error': {
            'code': 'csrf_failed' if is_csrf else 'bad_request',
            'message': description or 'Bad request',
            'fieldErrors': {}}}), 400
