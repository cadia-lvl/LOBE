from flask import Blueprint, redirect, url_for
from flask_security import current_user, login_required, roles_accepted

# Blueprint configuration
collection = Blueprint(
    'collection', __name__, template_folder='templates')

@collection.route('/collections/create/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
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
    return render_template('forms/model.jinja', form=form, type='create',
        section='collection')


@collection.route('/collections/')
@login_required
@roles_accepted('admin', 'Notandi')
def collection_list():
    page = int(request.args.get('page', 1))
    # TODO: sort_by not currently supported
    sort_by = request.args.get('sort_by', 'name')
    collections = Collection.query.order_by(resolve_order(Collection,
            request.args.get('sort_by', default='name'),
            order=request.args.get('order', default='desc')))\
            .paginate(page,per_page=app.config['COLLECTION_PAGINATION'])
    return render_template('lists/collections.jinja', collections=collections,
        section='collection')


@collection.route('/collections/zip_list/')
@login_required
@roles_accepted('admin')
def collection_zip_list():
    page = int(request.args.get('page', 1))
    # TODO: sort_by not currently supported
    sort_by = request.args.get('sort_by', 'name')
    collections = db.session.query(Collection).filter_by(has_zip=True).paginate(page,
        per_page=app.config['COLLECTION_PAGINATION'], )
    return render_template('lists/zips.jinja', zips=collections,
        section='collection')


@collection.route('/collections/<int:id>/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin', 'Notandi')
def collection_detail(id):
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


@collection.route('/collections/<int:id>/sessions', methods=['GET'])
@login_required
@roles_accepted('admin', 'Notandi')
def collection_sessions(id):
    page = int(request.args.get('page', 1))
    collection = Collection.query.get(id)
    rec_sessions = ListPagination(collection.sessions, page,
        app.config['SESSION_PAGINATION'])
    return render_template('lists/collection_sessions.jinja',
        collection=collection, sessions=rec_sessions, section='collection')


@collection.route('/collections/<int:id>/trim', methods=['GET'])
@login_required
@roles_accepted('admin')
def trim_collection(id):
    '''
    Trim all recordings in the collection
    '''
    trim_type = int(request.args.get('trim_type', default=0))
    executor.submit(trim_collection_handler, id, trim_type)
    flash('Söfnun verður klippt vonbráðar.', category='success')
    return redirect(url_for('collection', id=id))


@collection.route('/collections/<int:id>/generate_zip')
@login_required
@roles_accepted('admin')
def generate_zip(id):
    # TODO: Send some message in real-time to notify user when finished
    executor.submit(create_collection_zip, id)
    flash('Skjalasafn verður tilbúið vonbráðar.', category='success')
    return redirect(url_for('collection', id=id))


@collection.route('/collections/<int:id>/stream_zip')
@login_required
@roles_accepted('admin')
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


@collection.route('/collections/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def edit_collection(id):
    collection = Collection.query.get(id)
    form = collection_edit_form(collection)
    if request.method == 'POST':
        try:
            form = CollectionForm(request.form)
            if form.validate():
                form.populate_obj(collection)
                db.session.commit()
                collection = Collection.query.get(id)
                flash("Söfnun hefur verið breytt", category='success')
                return redirect(url_for('collection', id=id))
        except Exception as error:
            app.logger.error('Error updating a collection : {}\n{}'.format(
                error, traceback.format_exc()))

    return render_template('forms/model.jinja', collection=collection,
        form=form, type='edit', action=url_for('edit_collection', id=id),
        section='collection')


@collection.route('/collections/<int:id>/delete/')
@login_required
@roles_accepted('admin')
def delete_collection(id):
    collection = db.session.query(Collection).get(id)
    name = collection.name
    has_zip = collection.has_zip
    zip_path = collection.zip_path
    try:
        db.session.delete(collection)
        db.session.commit()
        shutil.rmtree(collection.get_record_dir())
        shutil.rmtree(collection.get_token_dir())
        shutil.rmtree(collection.get_video_dir())
        if has_zip: os.remove(zip_path)
        flash("{} var eytt".format(name), category='success')
    except Exception as error:
        flash("Villa kom upp. Hafið samband við kerfisstjóra", category="danger")
        app.logger.error('Error updating a collection : {}\n{}'.format(
            error, traceback.format_exc()))
    return redirect(url_for('collection_list'))


@collection.route('/collections/<int:id>/delete_archive/')
@login_required
@roles_accepted('admin')
def delete_collection_archive(id):
    collection = db.session.query(Collection).get(id)
    if collection.has_zip:
        do_delete = True
        try:
            os.remove(collection.zip_path)
        except FileNotFoundError:
            pass
        except Exception as error:
            flash("Villa kom upp. Hafið samband við kerfisstjóra", category="danger")
            app.logger.error('Error deleting an archive : {}\n{}'.format(
                error, traceback.format_exc()))
            do_delete = False
        if do_delete:
            collection.has_zip = False
            collection.zip_token_count = 0
            collection.zip_created_at = None
            db.session.commit()
            flash("Skjalasafni var eytt", category='success')
    else:
        flash("Söfnun hefur ekkert skjalasafn", category='warning')
    return redirect(url_for('collection', id=id))