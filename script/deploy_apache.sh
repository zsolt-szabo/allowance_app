# A very rudamentary example of a shell script that would allow you to update
# changes for the application on an AMI linux machine where flask is running on a web server
# using WSGI.
# Notes: this assumes there is an allowance_app_support directory with the following files
# in place: app.db, db_repository, flaskenv, somefile.wsgi
#
# The idea is to separate local database, installed libraries as well as the wsgi file
# required to integrate with apache. THESE ALL MUST BE ORIGINALLY CREATED BY HAND.
# /var/www/html/allowance_support_directory
#  app.db :  manually create app.db, copy it to this directory and change
#      owner to apache, group www
#  db_repository:  Wherever you created app.db, is where this directory exists,
#      copy it over and change permissions the same way
#  flaskenv:  You need to follow the steps to create flaskenv in the README.tx
#      file but in this directory as root
#  somefile.wsgi:  Once you learn how to integrate flaskw with wsgi (beyond scope
#      of this document) place it here with the same permissions.
#
# Once you have adjusted this file, as well as created --configfile for
# local_deployment_params.py, you should store these files outside of the git
# source tree.  This script assumes that location in a directory called scripts/
# relative to where this script will be called from.  Adjust as you see fit.
#  TODO:  There are still hard coded  referencing website location as well as
#       google-client auth information.  This should all be moved to config.py
test_stat () {
    check=$1
    msg=$2
    if [ "$check" -ne 0 ]
    then
        echo ERROR: $msg
        exit 9
    fi
}
user=`id | grep root`
if [ -z "$user" ]
then
    echo ERROR, you must run this as root
    exit
fi

if [ ! -d /var/www/html/allowance_app_support/db_repository ]
then
    echo ERROR, Initial setup must be done by hand, we are missing the allowance_app_support/db_repository directory in /var/www/html
    exit
fi
if [ ! -e /var/www/html/allowance_app_support/app.db ]
then
    echo ERROR, Initial setup must be done by hand, we are missing the allowance_app_support/app.db file in /var/www/html
    exit
fi
if [ ! -d apache_deploy ]
then
    cp -r /var/www/html/allowance_app_support .
    check=$?
    test_stat $check "creating local copy of allowance_app_support problems"

    cp -r allowance_app_support/app.db allowance_app_support/app.db.BAK

    git clone https://github.com/zsolt-szabo/allowance_app.git apache_deploy
    . /var/www/html/allowance_app_support/flaskenv/bin/activate
    cd apache_deploy

    python local_deployment_params.py --configfile ../scripts/YOUNEEDTOCREATETHISFILEWITH_local_deployment_params.py --deployed_location .
    check=$?
    test_stat $check "not continuing failure in local_deployment_params.py"

    echo Testing migration of database
    python db_migrate.py
    check=$?
    test_stat $check "database migrate failed not progressing"

    python db_upgrade.py
    check=$?
    test_stat $check "database upgrade failed, not progressing"

    echo "###################################################"
    echo Review the server locally before continuing
    echo Press enter to deploy
    echo "###################################################"
    read junk

    cd ..
    set -x
    rm -rf /var/www/html/BAK_allowance_app

    cp -R apache_deploy /var/www/html
    chown -R apache /var/www/html/apache_deploy
    chgrp -R www /var/www/html/apache_deploy

    cp -R allowance_app_support /var/www/html/STAGING_allowance_app_support
    chown apache /var/www/html/STAGING_allowance_app_support
    chgrp www /var/www/html/STAGING_allowance_app_support

    # These 4 lines are critical and will cause an outage
    mv /var/www/html/allowance_app_support  /var/www/html/BAKallowance_app_support
    mv /var/www/html/STAGING_allowance_app_support /var/www/html/allowance_app_support
    mv  /var/www/html/allowance_app /var/www/html/BAK_allowance_app
    mv /var/www/html/apache_deploy /var/www/html/allowance_app

    chown apache /var/www/html/allowance_app_support/app.db
    chgrp www /var/www/html/allowance_app_support/app.db
    echo ownership cleanup
    chown -R ec2-user apache_deploy allowance_app_support
    echo FINISHED
else
    echo "apache_deploy directory already exists, please delete"
fi

