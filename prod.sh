#!/bin/bash
export FLASK_APP=app
export FLASK_ENV=production
gunicorn $FLASK_APP:app