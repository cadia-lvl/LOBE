"""Initialize Flask app."""
import os

from flask import Flask
from flask_security import (Security, SQLAlchemyUserDatastore)
from flask_reverse_proxy_fix.middleware import ReverseProxyPrefixFix

from forms import ExtendedLoginForm
from models import db, User, Role
from filters import format_date

from .views.verification.views import verification
from .views.main.views import main
from .views.collection.views import collection
from .views.token.views import token
from .views.recording.views import recording
from .views.session.views import session
from .views.user.views import user
from .views.application.views import application
from .views.configuration.views import configuration
from .views.shop.views import shop

def create_app():
    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    app = Flask(__name__)
    if os.getenv('SEMI_PROD', False):
        app.config.from_pyfile('{}.py'.format(os.path.join('../settings/','semi_production')))
    else:
        app.config.from_pyfile('{}.py'.format(os.path.join('../settings/',
            os.getenv('FLASK_ENV', 'development'))))
    if 'REVERSE_PROXY_PATH' in app.config:
        ReverseProxyPrefixFix(app)

    db.init_app(app)
    security = Security(app, user_datastore, login_form=ExtendedLoginForm)

    # register filters
    app.jinja_env.filters['datetime'] = format_date

    # Propagate background task exceptions
    app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = True

    # register blueprints
    app.register_blueprint(main)
    app.register_blueprint(collection)
    app.register_blueprint(verification)
    app.register_blueprint(token)
    app.register_blueprint(recording)
    app.register_blueprint(session)
    app.register_blueprint(user)
    app.register_blueprint(application)
    app.register_blueprint(configuration)
    app.register_blueprint(shop)

    return app

