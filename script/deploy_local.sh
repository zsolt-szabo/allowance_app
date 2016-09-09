# Create a local deployment of  the allowance_app.
# This includes adjusting all parameters  required by
# --configfile

if [ ! -d allowance_app ]
then
    git clone https://github.com/zsolt-szabo/allowance_app.git
    cd allowance_app
    virtualenv flaskenv
    . flaskenv/bin/activate
    pip install -r py_requirements.txt
    ./db_create.py
    python local_deployment_params.py --configfile ../scripts/z_flask_local.txt --deployed_location .
else
    echo "allowance_app directory already exists, please delete"
fi

