#!flaskenv/bin/python
from app import app
import logging

logging.basicConfig(level=logging.DEBUG)
app.jinja_env.globals.update(LOCAL_SERVER_PORT=None)

if __name__ == "__main__":
    LOCAL_SERVER_PORT = 5000
    app.jinja_env.globals.update(LOCAL_SERVER_PORT=LOCAL_SERVER_PORT)
    app.run(port=LOCAL_SERVER_PORT, debug=True, host='0.0.0.0')
