import json
import os
from flask import (Flask, Response, flash, redirect, render_template, request,
    send_from_directory, session, url_for)
from flask_security import (Security, SQLAlchemyUserDatastore, login_required,
    roles_required)
from flask_security.utils import hash_password
from sqlalchemy.sql.expression import func, select
from werkzeug import secure_filename
from db import (create_tokens, get_paginated, insert_collection,
    newest_collections)
from filters import format_date
from forms import (BulkTokenForm, CollectionForm, ExtendedLoginForm,
    ExtendedRegisterForm)
from models import Collection, Recording, Role, Token, User, db

app = Flask(__name__, static_url_path=os.getenv('STATIC_URL_PATH', '/static'))
app.config.from_pyfile('{}.py'.format(os.path.join('settings/', os.getenv('FLASK_ENV', 'dev'))))

db.init_app(app)
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore, login_form=ExtendedLoginForm)

# register filters
app.jinja_env.filters['datetime'] = format_date

# GENERAL ROUTES
@app.route('/lobe/')
@login_required
def index():
    return render_template('index.jinja', collections=newest_collections(num=4))

@app.route('/lobe/post_recording', methods=['POST'])
@login_required
def post_recording():
    recordings = []
    files = []
    for token in request.form:
        token_id = request.form[token]
        file_obj = request.files.get('file_{}'.format(token_id))
        recording = Recording(token_id, file_obj.filename, session['user_id'])
        db.session.add(recording)
        recordings.append(recording)
        files.append(file_obj)
    db.session.commit()
    for idx, recording in enumerate(recordings):
        recording.save_to_disk(files[idx])
    db.session.commit()

    return Response(status=200)

# RECORD ROUTES

@app.route('/lobe/record/<int:coll_id>')
@login_required
def record_session(coll_id):
    collection = Collection.query.get(coll_id)
    tokens = Token.query.filter_by(collection=coll_id).order_by(func.random()).limit(50)
    print(collection)
    print(json.dumps([t.get_dict() for t in tokens]))
    return render_template('record.jinja', section='record', collection=collection, tokens=tokens,
        json_tokens=json.dumps([t.get_dict() for t in tokens]))

@app.route('/lobe/record/token/<tok_id>')
@login_required
def record_single(tok_id):
    token = Token.query.get(tok_id)
    return render_template('record.jinja', tokens=token, section='record', single=True,
        json_tokens =json.dumps([token.get_dict()]))

# COLLECTION ROUTES

@app.route('/lobe/collections/create', methods=['GET', 'POST'])
@login_required
def create_collection():
    form = CollectionForm(request.form)
    if request.method == 'POST' and form.validate():
        # add collection to database
        collection = insert_collection(form.name.data)

        return redirect(url_for('collection', id=collection.id))

    return render_template('collection_create.jinja', form=form, section='collection')

@app.route('/lobe/collections/')
@login_required
def collection_list():
    page = int(request.args.get('page', 1))
    sort_by = request.args.get('sort_by', 'name')
    collections = Collection.query.paginate(page, per_page=app.config['COLLECTION_PAGINATION'])
    return render_template('collection_list.jinja', collections=collections, section='collection')

@app.route('/lobe/collections/<int:id>', methods=['GET', 'POST'])
@login_required
def collection(id):
    token_form = BulkTokenForm(request.form)
    if request.method == 'POST':
        tokens = create_tokens(id, request.files.getlist('files'))

    page = int(request.args.get('page', 1))
    collection = Collection.query.get(id)
    tokens = collection.get_tokens().paginate(page, per_page=app.config['TOKEN_PAGINATION'])
    return render_template('collection.jinja',
        collection=collection, token_form=token_form, tokens=tokens, section='collection')


# TOKEN ROUTES

@app.route('/lobe/tokens/<int:id>')
@login_required
def token(id):
    return render_template('token.jinja', token=Token.query.get(id), section='token')

@app.route('/lobe/tokens/')
@login_required
def token_list():
    page = int(request.args.get('page', 1))
    tokens = Token.query.paginate(page, per_page=app.config['TOKEN_PAGINATION'])
    return render_template('token_list.jinja', tokens=tokens, section='token')


# RECORDING ROUTES
@app.route('/lobe/recordings/')
@login_required
def recording_list():
    page = int(request.args.get('page', 1))
    recordings = Recording.query.paginate(page, per_page=app.config['RECORDING_PAGINATION'])
    return render_template('recording_list.jinja', recordings=recordings, section='recording')

@app.route('/lobe/recording/<int:id>')
@login_required
def recording(id):
    recording = Recording.query.get(id)
    return render_template('recording.jinja', recording=recording, section='recording')

@app.route('/lobe/recordings/<int:id>/download')
@login_required
def download_recording(id):
    recording = Recording.query.get(id)
    return send_from_directory(recording.get_directory(), recording.fname, as_attachment=True)

# USER ROUTES

@app.route('/lobe/users/')
@login_required
def user_list():
    page = int(request.args.get('page', 1))
    #users = User.query.paginate(page, per_page=RECORDING_PAGINATION)
    users = get_paginated(User, page, app.config['RECORDING_PAGINATION'], 'name', desc=False)
    return render_template('user_list.jinja', users=users, section='user')


@app.route('/lobe/users/create', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def create_user():
    form = ExtendedRegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        user_datastore.create_user(name=form.name.data, email=form.email.data,
            password=hash_password(form.password.data), roles=[form.role.data])
        db.session.commit()
    return render_template('user_create.jinja', form=form, section='user')
