#!/bin/bash
export FLASK_APP=app
export FLASK_ENV=development
export PORT=7331
export PATH_PREFIX='/lobe'

gunicorn -b 127.0.0.1:$PORT wsgi --timeout 120