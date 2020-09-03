import traceback

from flask import (redirect, url_for, render_template, request,
                   send_from_directory, flash, Blueprint)
from flask import current_app as app
from flask_security import login_required, roles_accepted

from lobe.models import Token, db
from lobe.db import resolve_order, delete_token_db

token = Blueprint(
    'token', __name__, template_folder='templates')


@token.route('/tokens/<int:id>/')
@login_required
@roles_accepted('admin', 'Notandi')
def token_detail(id):
    return render_template(
        'token.jinja',
        token=Token.query.get(id),
        section='token')


@token.route('/tokens/')
@login_required
@roles_accepted('admin', 'Notandi')
def token_list():
    page = int(request.args.get('page', default=1))
    tokens = Token.query.order_by(resolve_order(
            Token,
            request.args.get('sort_by', default='created_at'),
            order=request.args.get('order', default='desc')))\
        .paginate(page, per_page=app.config['TOKEN_PAGINATION'])

    return render_template(
        'token_list.jinja',
        tokens=tokens,
        section='token')


@token.route('/tokens/<int:id>/download/')
@login_required
@roles_accepted('admin', 'Notandi')
def download_token(id):
    token = Token.query.get(id)
    try:
        return send_from_directory(
            token.get_directory(),
            token.fname,
            as_attachment=True)
    except Exception as error:
        app.logger.error(
            "Error downloading a token : {}\n{}".format(
                error, traceback.format_exc()))


@token.route('/tokens/<int:id>/delete/', methods=['GET'])
@login_required
@roles_accepted('admin')
def delete_token(id):
    token = Token.query.get(id)
    did_delete = delete_token_db(token)
    if did_delete:
        flash("Setningu var eytt", category='success')
    else:
        flash("Ekki gekk að eyða setningu", category='warning')
    return redirect(request.args.get('backref', url_for('main.index')))


@token.route('/token/<int:id>/mark_bad/')
@login_required
@roles_accepted('admin', 'Notandi')
def toggle_token_bad(id):
    token = Token.query.get(id)
    token.marked_as_bad = not token.marked_as_bad
    token.collection.update_numbers()
    db.session.commit()
    return redirect(url_for('token.token_detail', id=token.id))
