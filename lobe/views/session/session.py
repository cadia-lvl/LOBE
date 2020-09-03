import traceback

from flask import redirect, url_for, request, render_template, flash, Blueprint
from flask import current_app as app
from flask_security import login_required, roles_accepted


from lobe.db import resolve_order, delete_session_db
from lobe.models import Session, db
from lobe.forms import SessionEditForm

session = Blueprint(
    'session', __name__, template_folder='templates')

@session.route('/sessions/')
@login_required
@roles_accepted('admin', 'Notandi')
def rec_session_list():
    page = int(request.args.get('page', 1))
    sessions = Session.query.order_by(
        resolve_order(
            Session,
            request.args.get('sort_by', default='created_at'),
            order=request.args.get('order', default='desc')))\
        .paginate(
            page,
            per_page=app.config['SESSION_PAGINATION'])
    return render_template(
        'session_list.jinja',
        sessions=sessions,
        section='session')


@session.route('/sessions/<int:id>/')
@login_required
@roles_accepted('admin', 'Notandi')
def rec_session_detail(id):
    session = Session.query.get(id)
    return render_template(
        'session.jinja',
        session=session,
        section='session')


@session.route('/sessions/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def session_edit(id):
    session = Session.query.get(id)
    form = SessionEditForm(request.form)
    try:
        if request.method == 'POST' and form.validate():
            form.populate_obj(session)
            db.session.commit()
            flash("Lotu var breytt", category='success')
    except Exception as error:
        app.logger.error('Error updating a session : {}\n{}'.format(
            error, traceback.format_exc()))
    return render_template(
        'forms/model.jinja',
        form=form,
        type='edit',
        action=url_for('session.session_edit', id=id),
        section='session')


@session.route('/sessions/<int:id>/delete/', methods=['GET'])
@login_required
@roles_accepted('admin')
def delete_session(id):
    record_session = Session.query.get(id)
    did_delete = delete_session_db(record_session)
    if did_delete:
        flash("Lotu var eytt", category='success')
    else:
        flash("Ekki gekk að eyða lotu", category='warning')
    return redirect(url_for('session.rec_session_list'))
