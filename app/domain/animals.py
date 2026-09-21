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
'''The animal pictures that make up a child's credentials.

These SVGs are not decoration: they are the alphabet of a child's login.  A
child signs in with

    nickname + animal1 + animal2      (which child this is)
    password + animal3 + animal4      (proof it is really them)

so the set of available animals defines the credential space.  The identifying
triple ``(firstname, animal1, animal2)`` is globally unique -- see the
``_kid_login`` constraint on Kid -- which is why the registration screen has to
be able to tell a parent which pairs are still free.

Discovered by globbing ``app/static/animal[0-9][0-9]_*.svg``, so adding an
animal is a matter of dropping in a correctly named file.  Note only the SVGs
count; the handful of legacy ``.png`` twins are ignored.
'''
import glob
import logging
import os

import config

logger = logging.getLogger(__name__)

ANIMAL_GLOB = '/app/static/animal[0-9][0-9]_*.svg'


def _load_animals():
    '''[(name, static_path)] for every animal SVG.

    The name comes from the filename: ``animal01_tiger.svg`` -> ``tiger``.
    '''
    return [(os.path.basename(each).split('_')[1][:-4],
             'static/' + os.path.basename(each))
            for each in glob.glob(config.basedir + ANIMAL_GLOB)]


#: [(name, static_path)]. Used directly as WTForms SelectField choices.
images = _load_animals()

#: Every ordered (animal1, animal2) pair -- the identifying half of a child
#: login. len(images) ** 2 combinations.
image_combo_set = set((first[0], second[0])
                      for first in images for second in images)

logger.info('Loaded kid images %s' % str(images))


def animal_names():
    return [name for name, _path in images]


def image_url(name):
    '''Static path for an animal, or None if there is no such animal.'''
    for animal_name, path in images:
        if animal_name == name:
            return path
    return None
