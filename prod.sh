#!/bin/bash
export FLASK_APP=app
export FLASK_ENV=production
export PORT=7331
export STATIC_URL_PATH='/lobe/static/'

gunicorn -b 127.0.0.1:$PORT wsgi --timeout 120