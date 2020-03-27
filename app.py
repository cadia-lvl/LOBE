import json
import os
import sys
import zipfile
import tempfile
import traceback
import shutil
import subprocess
import logging
from logging.handlers import RotatingFileHandler

from collections import defaultdict
from flask import (Flask, Response, flash, redirect, render_template, request,
    send_from_directory, send_file, session, url_for, after_this_request, flash)
from flask_security import (Security, SQLAlchemyUserDatastore, login_required,
    roles_required, current_user)
from flask_security.utils import hash_password
from flask_executor import Executor
from sqlalchemy import or_
from sqlalchemy.sql.expression import func, select
from werkzeug import secure_filename, Request
from db import (create_tokens, insert_collection, newest_sessions, save_recording_session,
    sessions_day_info, delete_recording_db, delete_session_db)
from filters import format_date
from forms import (BulkTokenForm, CollectionForm, ExtendedLoginForm,
    ExtendedRegisterForm, UserEditForm, SessionEditForm, RoleForm)
from models import Collection, Recording, Role, Token, User, Session, db
from flask_reverse_proxy_fix.middleware import ReverseProxyPrefixFix
from ListPagination import ListPagination

from managers import ZipManager, RecordingInfoManager, IndexManager, create_collection_zip
from tools.analyze import load_sample, signal_is_too_high, signal_is_too_low

# initialize the logger
logHandler = RotatingFileHandler('logs/info.log', maxBytes=1000,
    backupCount=1)
logHandler.setLevel(logging.DEBUG)
logHandler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
))

user_datastore = SQLAlchemyUserDatastore(db, User, Role)
def create_app():
    app = Flask(__name__)
    if os.getenv('SEMI_PROD', False):
        app.config.from_pyfile('{}.py'.format(os.path.join('settings/','semi_production')))
    else:
        app.config.from_pyfile('{}.py'.format(os.path.join('settings/',
            os.getenv('FLASK_printENV', 'development'))))
    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(logHandler)
    if 'REVERSE_PROXY_PATH' in app.config:
        ReverseProxyPrefixFix(app)

    db.init_app(app)
    security = Security(app, user_datastore, login_form=ExtendedLoginForm)

    # register filters
    app.jinja_env.filters['datetime'] = format_date

    # Propagate background task exceptions
    app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = True

    return app

app = create_app()
executor = Executor(app)


# GENERAL ROUTES
@app.route('/')
@login_required
def index():
    return redirect(url_for('collection_list'))

@app.route('/lobe/')
@login_required
def index_redirect():
    return redirect(url_for('collection_list'))

@app.route('/post_recording/', methods=['POST'])
@login_required
def post_recording():
    session_id = None
    try:
        session_id = save_recording_session(request.form, request.files)
    except Exception as error:
        flash("Villa kom upp. Hafið samband við kerfisstjóra", category="danger")
        app.logger.error("Error posting recordings: {}\n{}".format(error,traceback.format_exc()))
        return Response(str(error), status=500)

    if session_id is None:
        flash("Engar upptökur, bara setningar merktar.", category='success')
        return Response(url_for('index'), status=200)
    else:
        return Response(url_for('rec_session', id=session_id), status=200)


# RECORD ROUTES

@app.route('/record/<int:coll_id>/')
@login_required
def record_session(coll_id):
    collection = Collection.query.get(coll_id)
    user_id = request.args.get('user_id')
    if not user_id:
        flash("Villa kom upp. Vinsamlega veljið rödd til að taka upp", category="danger")
        return redirect(url_for('index'))
    user_id = int(user_id)
    user = User.query.get(user_id)
    if not user:
        flash("Notandi er ekki þekktur. Vinsamlega hafið samband við kerfisstjóra",
            category="danger")
        app.logger.error("User with id {} does not exist when trying to record".format(
            user_id))
        return redirect(url_for('index'))

    if collection.has_assigned_user():
        if user_id != collection.assigned_user_id:
            flash("Aðeins skráð rödd getur tekið upp í þessari söfnun", category="danger")
            return redirect(url_for('index'))

    tokens = Token.query.filter(Token.collection_id==coll_id,
        Token.num_recordings==0, Token.marked_as_bad!=True).order_by(
            collection.get_sortby_function()).limit(app.config['SESSION_SZ'])
    for token in tokens:
        print(token.num_recordings)
    if tokens.count() == 0:
        flash("Engar ólesnar eða ómerktar setningar eru eftir í þessari söfnun", category="warning")
        return redirect(url_for("collection", id=coll_id))

    return render_template('record.jinja', section='record',
        collection=collection,  tokens=tokens,
        json_tokens=json.dumps([t.get_dict() for t in tokens]),
        tal_api_token=app.config['TAL_API_TOKEN'], user=user,
        manager=current_user)

@app.route('/record_beta/<int:coll_id>/', methods=['GET'])
@login_required
def record_session_beta(coll_id):
    collection = Collection.query.get(coll_id)

    if collection.has_assigned_user():
        if current_user.id != collection.assigned_user_id:
            flash("Aðeins skráð rödd getur tekið upp í þessari söfnun",
                category="danger")
            return redirect(url_for('index'))

    tokens = Token.query.filter(Token.collection_id==coll_id,
        Token.num_recordings==0, Token.marked_as_bad!=True).order_by(
            func.random()).limit(app.config['SESSION_SZ'])

    if tokens.count() == 0:
        flash("Engar ólesnar eða ómerkar setningar eru eftir í þessari söfnun",
            category="warning")
        return redirect(url_for("collection", id=coll_id))

    return render_template('record_beta.jinja', section='record',
        collection=collection, token=tokens, json_tokens=json.dumps(
            [t.get_dict() for t in tokens]),
        tal_api_token=app.config['TAL_API_TOKEN'])

@app.route('/record_beta/<int:coll_id>/post/', methods=['GET', 'POST'])
@login_required
def post_recording_beta(coll_id):
    if request.method == 'POST':
        print(request.form)
        for name in request.form:
            print(name)
        for file in request.files:
            file_obj = request.files.get(file)
            fname = file_obj.filename
            file_obj.save(fname)
            print(fname)
            command = "ffmpeg -i {} -vn audio_test.wav".format(fname)
            subprocess.call(command, shell=True)

    return redirect(url_for('record_session_beta', coll_id=coll_id))

@app.route('/record_beta/analyze/', methods=['POST'])
@login_required
def analyze_audio():
    # save to disk, only one file in the form
    file_obj = next(iter(request.files.values()))
    file_path = os.path.join(app.config['TEMP_DIR'], file_obj.filename)
    file_obj.save(file_path)

    # load the sample
    sample, _ = load_sample(file_path)

    # check the sample and return the response
    if signal_is_too_high(sample):
        return Response('high', 200)
    elif signal_is_too_low(sample):
        return Response('low', 200)
    return Response('ok', 200)

@app.route('/record/token/<int:tok_id>/')
@login_required
def record_single(tok_id):
    token = Token.query.get(tok_id)
    return render_template('record.jinja', tokens=token, section='record',
        single=True, json_tokens=json.dumps([token.get_dict()]),
        tal_api_token=app.config['TAL_API_TOKEN'])

# RATING ROUTES
@app.route('/rate/<int:coll_id>')
@login_required
def rate_session(coll_id):
    collection = Collection.query.get(coll_id)
    recordings = db.session.query(Recording).order_by(func.random()).limit(app.config['SESSION_SZ'])
    return render_template('rate.jinja', section='rate',
        json_recordings=json.dumps([r.get_dict() for r in recordings]),
        collection=collection,  recordings=recordings)

# COLLECTION ROUTES

@app.route('/collections/create/', methods=['GET', 'POST'])
@login_required
def create_collection():
    form = CollectionForm(request.form)
    if request.method == 'POST' and form.validate():
        try:
            # add collection to database
            collection = insert_collection(form)

            return redirect(url_for('collection', id=collection.id))
        except Exception as error:
            flash("Error creating collection.", category="danger")
            app.logger.error("Error creating collection {}\n{}".format(error,traceback.format_exc()))
    return render_template('collection_create.jinja', form=form,
        section='collection')

@app.route('/collections/')
@login_required
def collection_list():
    page = int(request.args.get('page', 1))
    # TODO: sort_by not currently supported
    sort_by = request.args.get('sort_by', 'name')
    collections = Collection.query.order_by(resolve_order(Collection,
            request.args.get('sort_by', default='name'),
            order=request.args.get('order', default='desc')))\
            .paginate(page,per_page=app.config['COLLECTION_PAGINATION'])
    return render_template('collection_list.jinja', collections=collections,
        section='collection')

@app.route('/collections/zip_list/')
@login_required
def collection_zip_list():
    page = int(request.args.get('page', 1))
    # TODO: sort_by not currently supported
    sort_by = request.args.get('sort_by', 'name')
    collections = db.session.query(Collection).filter_by(has_zip=True).paginate(page,
        per_page=app.config['COLLECTION_PAGINATION'], )
    return render_template('zip_list.jinja', collections=collections,
        section='collection')

@app.route('/collections/<int:id>/', methods=['GET', 'POST'])
@login_required
def collection(id):
    token_form = BulkTokenForm(request.form)
    if request.method == 'POST':
        tokens = create_tokens(id, request.files.getlist('files'),
            token_form.is_g2p.data)

    collection = Collection.query.get(id)

    tokens = Token.query.filter(Token.collection_id==collection.id)\
            .order_by(resolve_order(Token,
                request.args.get('sort_by', default='created_at'),
                order=request.args.get('order', default='desc')))\
            .paginate(int(request.args.get('page', 1)) ,per_page=app.config['TOKEN_PAGINATION'])

    return render_template('collection.jinja',
        collection=collection, token_form=token_form, tokens=tokens,
        users=User.query.all(), section='collection')

def resolve_order(object, sort_by, order='desc'):
    ordering = getattr(object, sort_by)
    if callable(ordering):
        ordering = ordering()
    if str(order) == 'asc':
        return ordering.asc()
    else:
        return ordering.desc()


@app.route('/collections/<int:id>/sessions', methods=['GET'])
@login_required
def collection_sessions(id):
    page = int(request.args.get('page', 1))
    collection = Collection.query.get(id)
    rec_sessions = ListPagination(collection.sessions, page,
        app.config['SESSION_PAGINATION'])
    return render_template('collection_sessions.jinja',
        collection=collection, sessions=rec_sessions, section='collection')


@app.route('/collections/<int:id>/generate_zip')
@login_required
def generate_zip(id):
    # TODO: Send some message in real-time to notify user when finished
    executor.submit(create_collection_zip, id)
    flash('Skjalasafn verður tilbúið vonbráðar.', category='success')
    return redirect(url_for('collection', id=id))

@app.route('/collections/<int:id>/stream_zip')
@login_required
def stream_collection_zip(id):
    collection = Collection.query.get(id)
    zip_file = open(collection.zip_path, 'rb')
    file_size = os.path.getsize(collection.zip_path)
    return Response(
        zip_file,
        mimetype='application/octet-stream',
        headers=[
            ('Content-Length', str(file_size)),
            ('Content-Disposition', "attachment; filename=\"%s\"" % '{}'.format(collection.zip_fname))
        ],
        direct_passthrough=True)

@app.route('/collections/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
def edit_collection(id):
    collection = Collection.query.get(id)
    form = CollectionForm(request.form, obj=collection)
    try:
        if request.method == 'POST' and form.validate():
            form.populate_obj(collection)
            db.session.commit()
            collection = Collection.query.get(id)
            if collection.has_video:
                # create the video directory for the collection
                if not os.path.exists(collection.get_video_dir()):
                    os.makedirs(collection.get_video_dir())
            flash("Söfnun hefur verið breytt", category='success')
            return redirect(url_for('collection', id=id))
    except Exception as error:
        app.logger.error('Error updating a collection : {}\n{}'.format(
            error, traceback.format_exc()))

    return render_template('model_form.jinja', collection=collection,
        form=form, type='edit', action=url_for('edit_collection', id=id),
        section='collection')

@app.route('/collections/<int:id>/delete/')
@login_required
@roles_required('admin')
def delete_collection(id):
    collection = db.session.query(Collection).get(id)
    name = collection.name
    is_video = collection.has_video
    try:
        db.session.delete(collection)
        db.session.commit()
        shutil.rmtree(collection.get_record_dir())
        shutil.rmtree(collection.get_token_dir())
        if is_video:
            shutil.rmtree(collection.get_video_dir())
        flash("{} var eytt".format(name), category='success')
    except Exception as error:
        flash("Villa kom upp. Hafið samband við kerfisstjóra", category="danger")
        app.logger.error('Error updating a collection : {}\n{}'.format(
            error, traceback.format_exc()))

    return redirect(url_for('collection_list'))

# TOKEN ROUTES

@app.route('/tokens/<int:id>/')
@login_required
def token(id):
    return render_template('token.jinja', token=Token.query.get(id),
        section='token')

@app.route('/tokens/')
@login_required
def token_list():
    page = int(request.args.get('page', default=1))
    only_bad = bool(request.args.get('only_bad', False))

    if only_bad:
        tokens = db.session.query(Token).filter_by(marked_as_bad=True).order_by(
            resolve_order(Token, request.args.get('sort_by', default='created_at'),
                order=request.args.get('order', default='desc'))).paginate(page,
            per_page=app.config['TOKEN_PAGINATION'])
    else:
        tokens = Token.query.order_by(resolve_order(Token,
                request.args.get('sort_by', default='created_at'),
                order=request.args.get('order', default='desc'))).paginate(page,
            per_page=app.config['TOKEN_PAGINATION'])

    return render_template('token_list.jinja', tokens=tokens, only_bad=only_bad, section='token')

@app.route('/tokens/<int:id>/download/')
@login_required
def download_token(id):
    token = Token.query.get(id)
    try:
        return send_from_directory(token.get_directory(), token.fname,
            as_attachment=True)
    except Exception as error:
        app.logger.error(
            "Error downloading a token : {}\n{}".format(error,traceback.format_exc()))

# RECORDING ROUTES

@app.route('/recordings/')
@login_required
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

    return render_template('recording_list.jinja', recordings=recordings, only_bad=only_bad,
        section='recording')

@app.route('/recordings/<int:id>/')
@login_required
def recording(id):
    recording = Recording.query.get(id)
    return render_template('recording.jinja', recording=recording, section='recording')

@app.route('/recordings/<int:id>/delete/', methods=['GET'])
@login_required
@roles_required('admin')
def delete_recording(id):
    recording = Recording.query.get(id)
    did_delete = delete_recording_db(recording)
    if did_delete:
        flash("Upptöku var eytt", category='success')
    else:
        flash("Ekki gekk að eyða upptöku", category='warning')
    return redirect(request.args.get('backref', url_for('index')))


@app.route('/recordings/<int:id>/mark_bad/')
@login_required
def toggle_recording_bad(id):
    recording = Recording.query.get(id)
    recording.marked_as_bad = not recording.marked_as_bad
    db.session.commit()

    return redirect(url_for('recording', id=recording.id))

@app.route('/recordings/<int:id>/mark_bad_ajax/')
@login_required
def toggle_recording_bad_ajax(id):
    recording = Recording.query.get(id)
    state = not recording.marked_as_bad
    recording.marked_as_bad = state
    db.session.commit()

    return Response(str(state), 200)

@app.route('/recordings/<int:id>/download/')
@login_required
def download_recording(id):
    recording = Recording.query.get(id)
    try:
        return send_from_directory(recording.get_directory(), recording.fname,
            as_attachment=True)
    except Exception as error:
        app.logger.error(
            "Error downloading a recording : {}\n{}".format(error,traceback.format_exc()))

# SESSION ROUTES

@app.route('/sessions/')
@login_required
def rec_session_list():
    page = int(request.args.get('page', 1))
    sessions = Session.query.order_by(resolve_order(Session,
        request.args.get('sort_by', default='created_at'),
        order=request.args.get('order', default='desc'))).paginate(page,
        per_page=app.config['SESSION_PAGINATION'])
    return render_template('session_list.jinja', sessions=sessions,
        section='session')

@app.route('/sessions/<int:id>/')
@login_required
def rec_session(id):
    session = Session.query.get(id)
    return render_template('session.jinja', session=session, section='session')

@app.route('/sessions/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def session_edit(id):
    session = Session.query.get(id)
    form = SessionEditForm(request.form)
    try:
        if request.method == 'POST' and form.validate():
            form.populate_obj(session)
            db.session.commit()
            flash("Lotu var breytt", category='success')
    except Exception as error:
        app.logger.error('Error updating a session : {}\n{}'.format(error, traceback.format_exc()))
    return render_template('model_form.jinja', form=form, type='edit',
        action=url_for('session_edit', id=id), section='session')

@app.route('/sessions/<int:id>/delete/', methods=['GET'])
@login_required
@roles_required('admin')
def delete_session(id):
    record_session = Session.query.get(id)
    did_delete = delete_session_db(record_session)
    if did_delete:
        flash("Lotu var eytt", category='success')
    else:
        flash("Ekki gekk að eyða lotu", category='warning')
    return redirect(url_for('rec_session_list'))

# USER ROUTES

@app.route('/users/')
@login_required
@roles_required('admin')
def user_list():
    page = int(request.args.get('page', 1))
    users = User.query.order_by(resolve_order(User,
            request.args.get('sort_by', default='name'),
            order=request.args.get('order', default='desc')))\
            .paginate(page, app.config['USER_PAGINATION'])
    return render_template('user_list.jinja', users=users, section='user')

@app.route('/users/<int:id>/')
@login_required
def user(id):
    page = int(request.args.get('page', 1))
    user = User.query.get(id)
    recordings = Recording.query.filter(Recording.user_id==id).order_by(resolve_order(Recording,
            request.args.get('sort_by', default='created_at'),
            order=request.args.get('order', default='desc')))\
            .paginate(page, app.config['RECORDING_PAGINATION'])
    return render_template("user.jinja", user=user, recordings=recordings,
        section='user')

@app.route('/users/<int:id>/times', methods=['GET'])
@login_required
def user_time_info(id):
    user = User.query.get(id)
    sessions = Session.query.filter(
        or_(Session.user_id==user.id, Session.manager_id==user.id)).order_by(Session.created_at)

    day_info, total_est_work_time, total_session_duration = sessions_day_info(sessions, user)

    return render_template('user_time.jinja', user=user, sessions=sessions,
        day_info=day_info, total_est_work_time=total_est_work_time,
        total_session_duration=total_session_duration)


@app.route('/users/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
def user_edit(id):
    user = User.query.get(id)
    form = UserEditForm(request.form, obj=user)

    try:
        if request.method == 'POST' and form.validate():
            form.populate_obj(user)
            db.session.commit()
            flash("Notanda var breytt", category='success')
    except Exception as error:
        app.logger.error('Error updating a user : {}\n{}'.format(error, traceback.format_exc()))

    return render_template('model_form.jinja', user=user, form=form, type='edit',
        action=url_for('user_edit', id=id), section='user')

@app.route('/users/create/', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def user_create():
    form = ExtendedRegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        try:
            user_datastore.create_user(name=form.name.data, email=form.email.data,
                password=hash_password(form.password.data), roles=[form.role.data])
            db.session.commit()
            flash("Nýr notandi var búinn til", category='success')
            return redirect(url_for('user_list'))
        except Exception as error:
            app.logger.error('Error creating a user : {}\n{}'.format(error,traceback.format_exc()))
    return render_template('model_form.jinja', form=form, type='create',
        action=url_for('user_create'), section='user')

@app.route('/users/<int:id>/delete/')
@login_required
@roles_required('admin')
def delete_user(id):
    user = db.session.query(User).get(id)
    name = user.name
    db.session.delete(user)
    db.session.commit()
    flash("{} var eytt".format(name), category='success')
    return redirect(url_for('user_list'))

@app.route('/roles/create/', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def role_create():
    form = RoleForm(request.form)
    if request.method == 'POST' and form.validate():
        try:
            role = Role()
            form.populate_obj(role)
            db.session.add(role)
            db.session.commit()
        except Exception as error:
            app.logger.error('Error creating a role : {}\n{}'.format(error,traceback.format_exc()))
    return render_template('model_form.jinja', form=form, type='create',
        action=url_for('role_create'), section='role')

@app.route('/roles/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
def role_edit(id):
    role = Role.query.get(id)
    form = RoleForm(request.form, obj=role)

    if request.method == 'POST' and form.validate():
        try:
            form.populate_obj(role)
            db.session.commit()
            flash("Hlutverki var breytt", category='success')
        except Exception as error:
            app.logger.error('Error updating a role : {}\n{}'.format(error,traceback.format_exc()))
    return render_template('model_form.jinja', role=role, form=form, type='edit',
        action=url_for('role_edit', id=id), section='role')

# OTHER ROUTES
@app.route('/other/lobe_manual/')
@login_required
def download_manual():
    try:
        return send_from_directory(app.config['OTHER_PATH'], app.config['MANUAL_FNAME'],
            as_attachment=True)
    except Exception as error:
        flash("Error downloading manual", category="danger")
        app.logger.error(
            "Error downloading manual : {}\n{}".format(error,traceback.format_exc()))

@app.route('/other/test_record/')
@login_required
def test_record():
    token = Token.query.filter(Token.marked_as_bad!=True).order_by(
        func.random()).limit(1)[0]
    return render_template('record.jinja', tokens=token, section='record',
        single=True, record_test=True, json_tokens=json.dumps([token.get_dict()]),
        tal_api_token=app.config['TAL_API_TOKEN'])


@app.errorhandler(404)
def page_not_found(error):
    flash("Við fundum ekki síðuna sem þú baðst um.", category="warning")
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_server_error(error):
    flash("Alvarleg villa kom upp, vinsamlega reynið aftur", category="danger")
    app.logger.error('Server Error: %s', (error))
    return redirect(url_for('index'))