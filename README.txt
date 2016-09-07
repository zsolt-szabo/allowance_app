This application is currently running on http://kidallowance.net
The source code is hosted at https://github.com/zsolt-szabo/allowance_app

This application has only been tested on linux

System requirements
   python|virtualenv|sqlite3

To get started using the application
  -Python 2.7.09 or higher (keep this in mind if you intend on 
       running this on a WSGI server as python version can matter)
  -Virtual env needs to be set up in the flaskenv directory
    1) In the allowance_app directory type 'virtualenv flaskenv' 
        you need to have python virtualenv installed 
        http://docs.python-guide.org/en/latest/dev/virtualenvs/
    2) Enable the virtual environment '. flaskenv/bin/activate' 
    3) install libraries 'pip install -r py_requirements.txt' --relocatable
    4) create the database './db_create.py' 
    5) run the server './run.py'

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
