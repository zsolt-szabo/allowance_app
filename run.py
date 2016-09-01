#!flaskenv/bin/python
from app import app
import logging

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
