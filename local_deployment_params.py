#!flaskenv/bin/python
import argparse
import re
import os

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
                        help='Location of application (where config.py) lives.')

    args = parser.parse_args()

    if args.blank is True:
        print Template
    elif args.configfile is not None and args.deployed_location is not None:
        failure_occurred = False
        with open(os.path.join(args.deployed_location,args.configfile)) as f:
            contents = f.readlines()
        for eachline in contents:
            if not re.search('^#', eachline.strip()) and not \
                    re.search('^\s*$', eachline, re.S):
                linesplit = eachline.split('::')
                fpath = os.path.join(args.deployed_location, linesplit[0])
                regex = linesplit[1].replace('(','\(').replace(')','\)')
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
            for eachline in contents:
                if not re.search('^#', eachline.strip()) and not \
                        re.search('^\s*$', eachline, re.S):
                    linesplit = eachline.split('::')
                    if linesplit[2] == "<UPDATEME>":
                        continue  # Not updating anything
                    fpath = os.path.join(args.deployed_location, linesplit[0])
                    regex = linesplit[1].replace('(','\(').replace(')','\)')
                    with open(fpath) as change_file:
                        to_change = change_file.read()
                    newcontent = re.sub(regex, linesplit[2], to_change)
                    #with open(fpath, 'w') as fixfile:
                    #   fixfile.write(newcontent)
                    print '  * adjusted file ' + fpath
    elif args.configfile is None and args.deployed_location is None:
        parser.print_usage()
    else:
        parser.print_usage()
        print "\nERROR: --configfile [file] parma requires " + \
            "--deployed_location [path]"
