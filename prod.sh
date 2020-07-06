#!/bin/bash
export FLASK_APP=app
export FLASK_ENV=production
export PORT=7331
export SEMI_PROD=True

py38/bin/python manage.py add_default_roles
py38/bin/python manage.py add_default_configuration

py38/bin/gunicorn -b 127.0.0.1:$PORT wsgi \
    --timeout 360 \
    --workers 4 \
    --threads 4 \
    --log-level=debug \
    --error-logfile=gunicorn.log \
    --capture-output
