import os
import traceback

from flask import (redirect, url_for, render_template, send_from_directory,
                   flash, request, Blueprint)
from flask import current_app as app
from flask_security import current_user, login_required

main = Blueprint(
    'main', __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/main/static')


@main.route('/')
@login_required
def index():
    if current_user.has_role('Greinir'):
        return redirect(url_for('verification.verify_index'))
    return redirect(url_for('collection_list'))


@main.route(f"/{os.getenv('LOBE_REDIRECT','lobe')}/")
@login_required
def index_redirect():
    if current_user.has_role('Greinir'):
        return redirect(url_for('verification.verify_index'))
    return redirect(url_for('collection_list'))


@main.route('/other/lobe_manual/')
@login_required
def download_manual():
    try:
        return send_from_directory(
            app.config['OTHER_DIR'], app.config['MANUAL_FNAME'],
            as_attachment=True)
    except Exception as error:
        flash("Error downloading manual", category="danger")
        app.logger.error(
            "Error downloading manual : {}\n{}".format(
                error, traceback.format_exc()))


@main.route('/other/test_media_device')
@login_required
def test_media_device():
    return render_template('media_device_test.jinja')


@main.errorhandler(404)
def page_not_found(error):
    flash("Við fundum ekki síðuna sem þú baðst um.", category="warning")
    return redirect(url_for('index'))


@main.errorhandler(500)
def internal_server_error(error):
    flash("Alvarleg villa kom upp, vinsamlega reynið aftur", category="danger")
    app.logger.error('Server Error: %s', (error))
    return redirect(url_for('index'))


@main.route('/not-in-chrome/')
def not_in_chrome():
    return render_template(
        'not_in_chrome.jinja',
        previous=request.args.get('previous'))


@main.route('/tos/')
def tos():
    return render_template('tos.jinja')