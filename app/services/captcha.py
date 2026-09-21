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
'''The home-grown registration captcha.

Two numbers are shown as strings of digit images (static/a.png .. i.png map
to the digits 1..9), together with one of four randomly chosen instructions
-- add them, subtract them, read all the digits in order, or read both sets
backwards. The expected answer is held server-side in the session.

Moved verbatim from app/lib/a_login.py. It is pure generation: no request,
no database, no session, which makes it straightforward to test and to
serve from a JSON endpoint later.

Note the digit alphabet only covers 1-9; zero never appears, so no number
generated here contains one.
'''
import logging
import random

logger = logging.getLogger(__name__)


def get_captcha():
    class captcha:
        c = {1: 'a', 2: 'b', 3: 'c', 4: 'd', 5: 'e', 6: 'f',
             7: 'g', 8: 'h', 9: 'i'}
        operations = [
            'add both sets of numbers',
            'subtract the second set of numbers from the first',
            'write all the numbers you see in order (including both sets)',
            'write second set in reverse order, then first set in reverse ' +
            'order.']

        def __init__(self, firstnum, secondnum,
                     firstnum_links, secondnum_links):
            self.firstnum = firstnum
            self.secondnum = secondnum
            self.firstnum_links = firstnum_links
            self.secondnum_links = secondnum_links
            self.solution = None
            self.operation = None

    num1_links = []
    num2_links = []
    firstnum = str(random.randint(1, 9))
    tmp = str(random.randint(1, 9))
    for each_num in range(2):
        if random.choice([True, False]):
            firstnum += str(random.randint(1, 9))
        if random.choice([True, False]):
            tmp += str(random.randint(1, 9))

    if int(firstnum) > int(tmp):
        secondnum = tmp
    else:
        secondnum = firstnum
        firstnum = tmp

    for ea_char in firstnum:
        num1_links.append("static/%s.png" % captcha.c[int(ea_char)])
    for ea_char in secondnum:
        num2_links.append("static/%s.png" % captcha.c[int(ea_char)])

    cap = captcha(firstnum, secondnum, num1_links, num2_links)

    operation = random.randint(0, 3)
    cap.operation = captcha.operations[operation]
    if operation == 0:
        cap.solution = int(firstnum) + int(secondnum)
    elif operation == 1:
        cap.solution = int(firstnum) - int(secondnum)
    elif operation == 2:
        cap.solution = int(firstnum + secondnum)
    else:
        cap.solution = secondnum[::-1] + firstnum[::-1]

    return cap
