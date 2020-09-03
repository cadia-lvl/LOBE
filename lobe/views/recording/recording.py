from functools import wraps
import traceback
import json
import os

from flask import (Blueprint, redirect, url_for, request, render_template,
                   flash, Response, send_from_directory, jsonify)
from flask import current_app as app
from flask_security import current_user, login_required, roles_accepted

from lobe.models import Collection, Recording, User, Token, db
from lobe.tools.analyze import (find_segment, load_sample, signal_is_too_high,
                                signal_is_too_low)
from lobe.db import resolve_order, delete_recording_db, save_recording_session

recording = Blueprint(
    'recording', __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/recording/static')


@recording.route('/recordings/')
@login_required
@roles_accepted('admin', 'Notandi')
def recording_list():
    page = int(request.args.get('page', 1))
    only_bad = bool(request.args.get('only_bad', False))

    if only_bad:
        recordings = db.session.query(Recording)\
            .filter_by(marked_as_bad=True)\
            .paginate(
                page,
                per_page=app.config['RECORDING_PAGINATION'])
    else:
        recordings = Recording.query.order_by(
            resolve_order(
                Recording,
                request.args.get('sort_by', default='created_at'),
                order=request.args.get('order', default='desc')))\
            .paginate(page, per_page=app.config['RECORDING_PAGINATION'])

    return render_template(
        'recording_list.jinja',
        recordings=recordings,
        only_bad=only_bad,
        section='recording')


@recording.route('/recordings/<int:id>/')
@login_required
@roles_accepted('admin', 'Notandi')
def recording_detail(id):
    recording = Recording.query.get(id)
    return render_template(
        'recording.jinja',
        recording=recording,
        section='recording')


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
    return redirect(request.args.get('backref', url_for('main.index')))


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
        return send_from_directory(
            recording.get_directory(), recording.fname,
            as_attachment=True)
    except Exception as error:
        app.logger.error(
            "Error downloading a recording : {}\n{}".format(
                error, traceback.format_exc()))


def require_login_if_closed_collection(func):
    """
    If collection is part of a posting we need to allow applicants to access
    without logging in, otherwise er only want 'admin' or 'Notandi' to
    be able to record for the collection.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        collection_id = kwargs.get("collection_id") or \
            request.form.get("collection_id")
        user_id = request.args.get('user_id') or request.form.get('user_id')

        collection = Collection.query.get(collection_id)
        if not collection.is_closed and collection.open_for_applicant(user_id):
            return func(*args, **kwargs)

        if current_user and \
            (current_user.has_role("admin") or
                current_user.has_role("Notandi")):
            return func(*args, **kwargs)

        return app.login_manager.unauthorized()

    return wrapper


# TODO: MOVE ELSEWHERE
@recording.route('/record/<int:collection_id>/', methods=['GET'])
@require_login_if_closed_collection
def record_session(collection_id):
    collection = Collection.query.get(collection_id)
    user_id = request.args.get('user_id')

    if not user_id:
        flash(
            "Villa kom upp. Vinsamlega veljið rödd til að taka upp",
            category="danger")
        return redirect(url_for('collection.collection_detail',
                                id=collection_id))
    if not collection.configuration:
        flash(
            "Villa kom upp. Vinsamlega veljið stillingar fyrir söfnunina",
            category="danger")
        return redirect(url_for('collection.collection_detail',
                                id=collection_id))
    user_id = int(user_id)
    user = User.query.get(user_id)
    if collection.has_assigned_user():
        if user_id != collection.assigned_user_id:
            flash(
                "Aðeins skráð rödd getur tekið upp í þessari söfnun",
                category="danger")
            return redirect(url_for('main.index'))

    if collection.is_multi_speaker:
        # TODO: Can we just always use this query?
        tokens = Token.query.filter(
            Token.collection_id == collection_id,
            Token.id.notin_(
                Recording.query.filter(
                    Recording.user_id == user_id).values(Recording.token_id)
            ),
            Token.marked_as_bad != True
        ).order_by(
            collection.get_sortby_function()
        ).limit(collection.configuration.session_sz)
    else:
        tokens = Token.query.filter(
            Token.collection_id == collection_id,
            Token.num_recordings == 0,
            Token.marked_as_bad != True
        ).order_by(
            collection.get_sortby_function()
        ).limit(
            collection.configuration.session_sz
        )

    if tokens.count() == 0:
        flash(
            "Engar ólesnar eða ómerkar setningar eru eftir í þessari söfnun",
            category="warning")
        return redirect(url_for("collection.collection_detail",
                                id=collection_id))

    return render_template(
        'record.jinja',
        section='record',
        collection=collection,
        token=tokens,
        json_tokens=json.dumps([t.get_dict() for t in tokens]),
        user=user,
        manager=current_user,
        application=(not collection.is_closed),
        tal_api_token=app.config['TAL_API_TOKEN'])


@recording.route('/record/analyze/', methods=['POST'])
@login_required
@roles_accepted('admin', 'Notandi')
def analyze_audio():
    # save to disk, only one file in the form
    file_obj = next(iter(request.files.values()))
    file_path = os.path.join(app.config['TEMP_DIR'], file_obj.filename)
    file_obj.save(file_path)

    high_thresh = float(request.form['high_thresh'])
    high_frames = int(request.form['high_frames'])
    low_thresh = float(request.form['low_thresh'])
    top_db = float(request.form['top_db'])

    # load the sample
    sample, sr = load_sample(file_path)
    segment_times = find_segment(sample, sr, top_db=top_db)
    # check the sample and return the response
    message = 'ok'
    if signal_is_too_high(sample, thresh=high_thresh, num_frames=high_frames):
        message = 'high'
    elif signal_is_too_low(sample, thresh=low_thresh):
        message = 'low'

    body = {
        'analysis': message,
        'segment': {
            'start': float(segment_times[0]),
            'end': float(segment_times[1])
        }
    }
    return jsonify(body), 200


@recording.route('/recording/<int:id>/cut/', methods=['POST'])
@login_required
@roles_accepted('admin', 'Notandi')
def cut_recording(id):
    recording = Recording.query.get(id)
    start = float(request.form['start'])
    end = float(request.form['end'])

    if start == -1 and end == -1:
        recording.start = None
        recording.end = None
    else:
        recording.start = start
        recording.end = end
    db.session.commit()
    return "ok", 200


@recording.route('/record/token/<int:tok_id>/')
@login_required
@roles_accepted('admin', 'Notandi')
def record_single(tok_id):
    token = Token.query.get(tok_id)
    return render_template(
        'record.jinja',
        tokens=token,
        section='record',
        single=True,
        json_tokens=json.dumps([token.get_dict()]),
        tal_api_token=app.config['TAL_API_TOKEN'])


@recording.route('/post_recording/', methods=['POST'])
@require_login_if_closed_collection
def post_recording():
    collection = Collection.query.get(request.form.get("collection_id"))
    try:
        session_id = save_recording_session(request.form, request.files)
    except Exception as error:
        flash(
            "Villa kom upp. Hafið samband við kerfisstjóra",
            category="danger")
        app.logger.error("Error posting recordings: {}\n{}".format(
            error, traceback.format_exc()))
        return Response(str(error), status=500)

    if collection.posting:
        return Response(url_for("application.application_success"))
    elif session_id is None:
        flash("Engar upptökur, bara setningar merktar.", category='success')
        return Response(url_for('main.index'), status=200)
    else:
        return Response(url_for('session.rec_session_detail', id=session_id), status=200)
