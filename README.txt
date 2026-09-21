This application is currently running on http://kidallowance.net
The source code is hosted at https://github.com/zsolt-szabo/allowance_app

This application has only been tested on linux

System requirements
   python|virtualenv|sqlite3

To get started using the application
  -Python 3.14 or higher (keep this in mind if you intend on 
       running this on a WSGI server as python version can matter)
  -Virtual env needs to be set up in the flaskenv directory
    1) In the allowance_app directory type 'virtualenv flaskenv' 
        you need to have python virtualenv installed 
        http://docs.python-guide.org/en/latest/dev/virtualenvs/
        
        WARNING: If you want to make a staging area that ultimately
            copies your allowance_app directory to a WSGI web server
            location, you need to put your virtualenv outside of the
            allowance_app directory and run through the setup of that
            directory from there.  That is because the virtualenv
            scripts will hardcode their locations and moving the
            directory to a new location creates problems.
        
    2) Enable the virtual environment '. flaskenv/bin/activate' 
    3) install libraries 'pip install -r py_requirements.txt' 
    4) create the database './db_create.py'
    5) Run unit tests.  'cd unit',  './test_group_01.py'
    6) run the server './run.py'

Running the test suites
    There are two suites, and both must pass:

    1) The pytest suite (characterization + unit tests):
          pip install -r requirements-dev.txt
          pytest -q
       tests/characterization/ pins the behaviour of the money code
       (allowance payouts, ledger entries, percentage redistribution)
       exactly as it is today, including its known bugs.  Tests named
       test_KNOWN_BUG_* assert the CURRENT, incorrect behaviour on
       purpose -- when one of those bugs is fixed, that test's assertion
       is inverted, which proves the fix changed one thing and no more.
       Do not "fix" a failing KNOWN_BUG test by deleting it.

    2) The legacy functional suite:
          cd unit && ./test_group_01.py
       It asserts against rendered HTML, which is precisely what makes it
       a useful regression net while the code underneath is refactored.

    Lint with 'flake8 .'.  setup.cfg carries a documented baseline of
    pre-existing findings so that only NEW violations fail.

Checking a database for integrity problems
    scripts/verify_prod_snapshot.py reports on invariants the application
    relies on but never enforces -- most importantly that a kid's money
    totalled across the 5 sub-accounts always equals the same money
    totalled across the 7 storage locations.  It is strictly read-only,
    but run it against a copy anyway:

        sqlite3 app.db ".backup /tmp/snapshot.db"
        ./scripts/verify_prod_snapshot.py /tmp/snapshot.db

    Expect findings on a long-lived database; none of these rules has
    ever been enforced.

Tech support access to a user's account
    There is no master password.  To help a user who cannot get in, mint
    a short-lived link for their account from a shell on the server:

        ./scripts/support_login.py --email someone@example.com

    Paste the printed URL into a browser and you are in that account,
    with the red TECH SUPPORT banner showing.  The link names exactly one
    account, expires (15 minutes by default, --minutes to change), and
    both minting and use are written to the application log.

To utilize google authentication
    1) You need to have some knowledge about how google auth works
       because you will have to setup 
       https://developers.google.com/identity/sign-in/web/
    2) You will need to have Open SSL or the equivalent on your server
       for connecting to google.
    3) Once you have basic knowledge of google auth and have set up your
       own google identity credentials search for all places to update
       within this codebase with 'grep -R CONFIG_FOR_GOOGLE *'.  Replace
       all values of CONFIG_FOR_GOOGLE with the appropriate values.
    4) finally change ENABLE_GOOGLE_LOGIN in the file config.py to the value
       of True
    5) NOTE: the script local_deployment_params.py is helpful, in making this
           process configurable and repeatable but you still need a basic
           understanding.
