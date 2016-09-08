#!flaskenv/bin/python
# Copyright (C) 2016  name of Zsolt Szabo zsoltman@hotmail.com

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
import argparse
import re
import os
import sys

Template='''
# You MUST update entire REGEXTOREPLACE, not just the value you want to adjust.
# EXAMPLE:
# app/lib/somefile::foobar = 78::foobar = 99
# Leave value to <UPDATEME> if you are not updating a specfic field

# FILEPATH::REGEXTOREPLACE::NEWVAL
app/lib/a_login.py::goog_user = 'a1a2google_userb6b8xzxxzyaa15332TuyvkbarU879'::<UPDATEME>
config.py::SECRET_KEY = 'you-should-change-this-to-something-secure-and-different'::<UPDATEME>

# BEGIN GOOGLE CONFIG
config.py::ENABLE_GOOGLE_LOGIN = False::<UPDATEME>
gitkit-server-config.json::"clientId:: "CONFIG_FOR_GOOGLE"::<UPDATEME>
gitkit-server-config.json::"projectId": "CONFIG_FOR_GOOGLE"::<UPDATEME>
gitkit-server-config.json::"serviceAccountEmail": "CONFIG_FOR_GOOGLE"::<UPDATEME>
gitkit-server-config.json::"serviceAccountPrivateKeyFile": "CONFIG_FOR_GOOGLE"::<UPDATEME>
gitkit-server-config.json::"widgetUrl": "CONFIG_FOR_GOOGLE"::<UPDATEME>
app/templates/base.html::xhr.open('GET', 'http://CONFIG_FOR_GOOGLE/logout')::<UPDATEME>
app/templates/base.html::name="google-signin-client_id" content="CONFIG_FOR_GOOGLE"::<UPDATEME>
app/templates/login.html::name="google-signin-client_id" content="CONFIG_FOR_GOOGLE"::<UPDATEME>
'''

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="'Allowance app' local deployment script. Create a " +
        'local file with python local_deployment_params.py --blank > ' +
        'local_deploy.txt. Next, adjust all necessary variables, then:' +
        'python local_deployment_params.py --configfile ' +
        'local_deploy.txt --deployed_location /var/www/html/allowance_app')
    parser.add_argument('--blank', "-b", action='store_true',
                        help='Print contents of blank config file')
    parser.add_argument('--configfile', "-c",
                        help='File with all the local value definitions.')
    parser.add_argument('--deployed_location', "-d",
                        help='Location of application (where config.py) ' +
                        'lives.')
    parser.add_argument('--test_run', '-t', action='store_true',
                        help='Run through entire process, but ' +
                        "don't write to files.")

    args = parser.parse_args()

    if args.blank is True:
        print Template
    elif args.configfile is not None and args.deployed_location is not None:
        failure_occurred = False
        with open(args.configfile) as f:
            contents = f.readlines()
        for eachline in contents:
            if not re.search('^#', eachline.strip()) and not \
                    re.search('^\s*$', eachline, re.S):
                linesplit = eachline.split('::')
                fpath = os.path.join(args.deployed_location, linesplit[0])
                regex = linesplit[1].replace('(', '\(').replace(')', '\)')
                if os.path.isfile(fpath):
                    with open(fpath) as change_file:
                        to_change = change_file.read()
                        if not re.search(regex, to_change):
                            failure_occurred = True
                            print "Failed to find regex '%s'" % linesplit[1]
                            print "    in file %s" % fpath
                else:
                    failure_occurred = True
                    print "Error in config, file %s not found! " % fpath
                    print "    for line '%s'" % eachline
        if failure_occurred is False:
            counter = 0
            for eachline in contents:
                counter += 1
                if not re.search('^#', eachline.strip()) and not \
                        re.search('^\s*$', eachline, re.S):
                    linesplit = eachline.split('::')
                    if linesplit[2] == "<UPDATEME>":
                        print "Skipping line %s in %s as it is undefined" % \
                            (counter, args.configfile)
                        continue  # Not updating anything
                    fpath = os.path.join(args.deployed_location, linesplit[0])
                    regex = linesplit[1].replace('(', '\(').replace(')', '\)')
                    with open(fpath) as change_file:
                        to_change = change_file.read()
                    newcontent = re.sub(regex, linesplit[2], to_change)
                    if not args.test_run:
                        with open(fpath, 'w') as fixfile:
                            fixfile.write(newcontent)
                        print '  * adjusted file ' + fpath
                    else:
                        print '  * TESTRUN on file ' + fpath
                        sys.exit(11)
        else:
            sys.exit(15)

    elif args.configfile is None and args.deployed_location is None:
        parser.print_usage()
        sys.exit(13)
    else:
        parser.print_usage()
        print "\nERROR: --configfile [file] parma requires " + \
            "--deployed_location [path]"
        sys.exit(17)
