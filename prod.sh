#!/bin/bash
export FLASK_APP=app
export FLASK_ENV=production
export PORT=7331
export SEMI_PROD=True

python manage.py add_default_roles
python manage.py add_default_configuration

gunicorn -b 127.0.0.1:$PORT wsgi \
    --timeout 360 \
    --workers 4 \
    --threads 4 \
    --log-level=debug \
    --error-logfile=gunicorn.log \
    --capture-output
