from flask import Blueprint, redirect, url_for
from flask_security import current_user, login_required, roles_accepted

# Blueprint configuration
recording = Blueprint(
    'recording', __name__, template_folder='templates')

@recording.route('/recordings/')
@login_required
@roles_accepted('admin', 'Notandi')
def recording_list():
    page = int(request.args.get('page', 1))
    only_bad = bool(request.args.get('only_bad', False))

    if only_bad:
        recordings = db.session.query(Recording).filter_by(marked_as_bad=True).paginate(page,
            per_page=app.config['RECORDING_PAGINATION'])
    else:
        recordings = Recording.query.order_by(resolve_order(Recording,
            request.args.get('sort_by', default='created_at'),
            order=request.args.get('order', default='desc')))\
            .paginate(page, per_page=app.config['RECORDING_PAGINATION'])

    return render_template('lists/recordings.jinja', recordings=recordings, only_bad=only_bad,
        section='recording')


@recording.route('/recordings/<int:id>/')
@login_required
@roles_accepted('admin', 'Notandi')
def recording_detail(id):
    recording = Recording.query.get(id)
    return render_template('recording.jinja', recording=recording, section='recording')


@recording.route('/recordings/<int:id>/delete/', methods=['GET'])
@login_required
@roles_accepted('admin')
def delete_recording(id):
    recording = Recording.query.get(id)
    did_delete = delete_recording_db(recording)
    if did_delete:
        flash("Upptöku var eytt", category='success')
    else:
        flash("Ekki gekk að eyða upptöku", category='warning')
    return redirect(request.args.get('backref', url_for('index')))


@recording.route('/recordings/<int:id>/mark_bad/')
@login_required
@roles_accepted('admin', 'Notandi')
def toggle_recording_bad(id):
    recording = Recording.query.get(id)
    recording.marked_as_bad = not recording.marked_as_bad
    db.session.commit()
    return redirect(url_for('recording', id=recording.id))


@recording.route('/recordings/<int:id>/mark_bad_ajax/')
@login_required
@roles_accepted('admin', 'Notandi')
def toggle_recording_bad_ajax(id):
    recording = Recording.query.get(id)
    state = not recording.marked_as_bad
    recording.marked_as_bad = state
    db.session.commit()

    return Response(str(state), 200)


@recording.route('/recordings/<int:id>/download/')
@login_required
def download_recording(id):
    recording = Recording.query.get(id)
    try:
        return send_from_directory(recording.get_directory(), recording.fname,
            as_attachment=True)
    except Exception as error:
        app.logger.error(
            "Error downloading a recording : {}\n{}".format(error,traceback.format_exc()))