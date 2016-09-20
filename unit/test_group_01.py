#!../flaskenv/bin/python
import unittest
import tempfile
import sys
import logging
import copy
import os

required_paths = [
    '../']

for each_path in required_paths:
    sys.path.append(each_path)

import app

from app import app as flask_obj
from local_data import test_data

logging.getLogger().setLevel(logging.ERROR)


class GlobalData:
    pass

gd = GlobalData


class kidAllowanceTestCase(unittest.TestCase):

    def test_01_setup(self):
        gd.db_fd, gd.unit_db = tempfile.mkstemp()
        flask_obj.config['TESTING'] = True
        flask_obj.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + \
            gd.unit_db
        flask_obj.config['WTF_CSRF_ENABLED'] = False
        gd.app = flask_obj.test_client()
        app.db.create_all()
        user1 = app.models.User(**test_data.user1)
        user1.set_password(test_data.user1['pw_hash'])
        kid1 = app.models.Kid(**test_data.user1_kid1)
        app.db.session.add(user1)  # Add person1
        app.db.session.commit()
        app.db.session.add(kid1)   # Add kid whipper for person1
        app.db.session.commit()
        user2 = app.models.User(**test_data.user2)
        user2.set_password(test_data.user2['pw_hash'])
        kid2 = app.models.Kid(**test_data.user2_kid2)
        app.db.session.add(user2)  # Add person2
        app.db.session.commit()
        app.db.session.add(kid2)   # Add kid larry for person2
        app.db.session.commit()

    def test_02_index_not_logged_in(self):
        rv = gd.app.get("/")
        assert 'Please login with your' in rv.data
        assert 'Register' in rv.data
        assert 'blogspot' in rv.data
        assert 'whipper' not in rv.data

    def test_03_index_logged_in(self):
        test_data.user1['password'] = test_data.user1['pw_hash']
        rv = gd.app.post(
            '/login',
            data=dict(**test_data.user1),
            follow_redirects=True)
        assert 'Logout' in rv.data
        assert 'Hi person1' in rv.data
        assert 'whipper' in rv.data
        assert 'rabbit/rabbit' in rv.data

    def test_04_index_after_logged_in(self):
        rv = gd.app.get("/")
        assert 'Logout' in rv.data
        assert 'Hi person1' in rv.data
        assert 'whipper' in rv.data
        assert 'rabbit/rabbit' in rv.data

    def test_05_allowance_page(self):
        rv = gd.app.get('/allowance?kid=whipper:rabbit:rabbit')
        assert '/ledger?kid=whipper:rabbit:rabbit' in rv.data
        assert 'remove_allowance?allow_id=' not in rv.data

    # Good allowance create ########
    def test_06_allowance_create_good(self):
        rv = gd.app.post(
            "/allowance?kid=whipper:rabbit:rabbit",
            data=dict(**test_data.kid1_allow_good),
            follow_redirects=True)
        assert 'kid1 good allowance' in rv.data
        assert '80.0' in rv.data
        assert '20.0' in rv.data
        assert "$ 3.0" in rv.data

    def test_07_logout(self):
        rv = gd.app.get('/logout', follow_redirects=True)
        assert 'Please login with your' in rv.data
        assert 'Register' in rv.data
        assert 'blogspot' in rv.data

    # #######################################
    # Add allowance for person2 kid2 ########
    def test_08_index_logged_in(self):
        test_data.user2['password'] = test_data.user2['pw_hash']
        rv = gd.app.post(
            '/login',
            data=dict(**test_data.user2),
            follow_redirects=True)
        assert 'Logout' in rv.data
        assert 'Hi person2' in rv.data
        assert 'larry' in rv.data
        assert 'tiger/tiger' in rv.data

    def test_09_allowance_check_against_user1s_kid_should_fail(self):
        rv = gd.app.post(
            "/allowance?kid=whipper:rabbit:rabbit",
            data=dict(**test_data.kid2_allow_good),
            follow_redirects=True)
        assert 'ERROR: Problem getting child data, error logged' in rv.data

    def test_10_allowance_create_kid2_good(self):
        rv = gd.app.post(
            "/allowance?kid=larry:tiger:tiger",
            data=dict(**test_data.kid2_allow_good),
            follow_redirects=True)
        assert 'kid2 good allowance' in rv.data
        assert '30.0' in rv.data
        assert '70.0' in rv.data
        assert "$ 4.0" in rv.data

    def test_11_logout(self):
        rv = gd.app.get('/logout', follow_redirects=True)
        assert 'Please login with your' in rv.data
        assert 'Register' in rv.data
        assert 'blogspot' in rv.data
    # Logout as person 2
    # #######################################

    # Login back as as person1
    def test_12_index_logged_in(self):
        test_data.user1['password'] = test_data.user1['pw_hash']
        rv = gd.app.post(
            '/login',
            data=dict(**test_data.user1),
            follow_redirects=True)
        assert 'Logout' in rv.data
        assert 'Hi person1' in rv.data
        assert 'whipper' in rv.data
        assert 'rabbit/rabbit' in rv.data

    def test_13_allowance_no_amount(self):
        data = copy.copy(test_data.kid1_allow_bad)
        del data['amount']
        rv = gd.app.post(
            "/allowance?kid=whipper:rabbit:rabbit",
            data=dict(**data),
            follow_redirects=True)
        assert 'ERROR:(amount)' in rv.data

    def test_14_allowance_too_much(self):
        data = copy.copy(test_data.kid1_allow_bad)
        data['amount'] = 501
        rv = gd.app.post(
            "/allowance?kid=whipper:rabbit:rabbit",
            data=dict(**data),
            follow_redirects=True)
        assert 'ERROR:(amount)' in rv.data

    def test_15_allowance_negative(self):
        data = copy.copy(test_data.kid1_allow_bad)
        data['amount'] = -3
        rv = gd.app.post(
            "/allowance?kid=whipper:rabbit:rabbit",
            data=dict(**data),
            follow_redirects=True)
        assert 'ERROR:(amount)' in rv.data

    def test_16_allowance_no_payout_days(self):
        data = copy.copy(test_data.kid1_allow_bad)
        del data['payout_days']
        rv = gd.app.post(
            "/allowance?kid=whipper:rabbit:rabbit",
            data=dict(**data),
            follow_redirects=True)
        assert 'ERROR:(payout_days)' in rv.data

    def test_17_allowance_bad_acc_distrib(self):
        data = copy.copy(test_data.kid1_allow_bad)
        data['acct2_perc'] = 20
        rv = gd.app.post(
            "/allowance?kid=whipper:rabbit:rabbit",
            data=dict(**data),
            follow_redirects=True)
        assert 'sub-accounts must add up to 100%' in rv.data

    def test_18_allowance_bad_loc_distrib(self):
        data = copy.copy(test_data.kid1_allow_bad)
        data['location2_perc'] = 20
        rv = gd.app.post(
            "/allowance?kid=whipper:rabbit:rabbit",
            data=dict(**data),
            follow_redirects=True)
        assert 'storage (where) must add up to 100%' in rv.data

    def test_19_delete_allowance_not_mine(self):
        rv = gd.app.get(
            "/remove_allowance?allow_id=2",
            follow_redirects=True)
        assert 'Unable to understand allowance Id given for removal' in \
            rv.data

    def test_20_delete_allowance_existing(self):
        rv = gd.app.get(
            "/remove_allowance?allow_id=1",
            follow_redirects=True)
        assert 'kid1 good allowance' not in rv.data

#        with open('out.html', 'w') as f:
#            f.write(rv.data)

    def test_99_teardown(self):
        os.close(gd.db_fd)
        os.unlink(gd.unit_db)

if __name__ == "__main__":
    print "=" * 80
    print "=" * 40, "      BEGIN TESTING"
    print "=" * 80
    unittest.main()
