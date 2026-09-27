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
'''Encoding the two identity kinds into one Flask-Login session id.

Parents live in `user` and children in `kid`, but Flask-Login stores a
single value. Getting that wrong means resolving an id against the wrong
table, so the encoding is explicit and has one parser.

Historically a parent was stored as a bare ``"7"`` and a child as the tuple
``('child', '7')``. The tuple survived a round trip only because Flask's
TaggedJSONSerializer preserves tuples -- undocumented behaviour that a
Flask upgrade could remove, at which point a child session would decode to
a bare value and resolve against the parent table.

Both legacy forms are still accepted so that deploying this does not sign
everyone out. Remove that tolerance once the sessions have aged out; it is
covered by its own tests.
'''

PARENT = 'parent'
CHILD = 'child'

PARENT_PREFIX = 'p:'
CHILD_PREFIX = 'c:'


def parse(raw):
    '''(kind, id) for a stored session id, or (None, None) if unusable.

    Accepts the current prefixed strings and both legacy encodings.
    '''
    if raw is None:
        return None, None

    #  Legacy: a child was a ('child', '7') tuple. Flask hands it back as a
    #  tuple or, depending on serializer, a list.
    if isinstance(raw, (tuple, list)):
        if len(raw) == 2 and raw[0] == CHILD:
            return _kind_or_nothing(CHILD, raw[1])
        return None, None

    if isinstance(raw, int):
        return PARENT, raw

    if isinstance(raw, str):
        for prefix, kind in ((PARENT_PREFIX, PARENT), (CHILD_PREFIX, CHILD)):
            if raw.startswith(prefix):
                #  A well-formed prefix with an unusable id ("", "abc") is
                #  still unusable -- never hand a None row id downstream.
                return _kind_or_nothing(kind, raw[len(prefix):])
        #  Legacy: a parent was a bare numeric string.
        return _kind_or_nothing(PARENT, raw)

    return None, None


def _kind_or_nothing(kind, raw_id):
    parsed = _as_int(raw_id)
    return (kind, parsed) if parsed is not None else (None, None)


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
