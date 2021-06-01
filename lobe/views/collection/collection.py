import os
import traceback
import shutil
import json
from zipfile import ZipFile
from flask import (Blueprint, redirect, url_for, request, render_template,
                   flash, send_from_directory, Response)
from flask import current_app as app
from flask_security import login_required, roles_accepted

from lobe.models import Collection, Token, User, db
from lobe.db import (
    resolve_order, insert_collection, create_tokens,
    save_uploaded_lobe_collection, save_uploaded_collection)
from lobe.forms import (
    CollectionForm, BulkTokenForm, collection_edit_form, UploadCollectionForm)
from lobe.tools.pagination import ListPagination
from lobe.managers import (
    trim_collection_handler, create_collection_zip, create_collection_info)

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
            return redirect(url_for('collection.collection_detail',
                                    id=collection.id))
        except Exception as error:
            flash("Error creating collection.", category="danger")
            app.logger.error("Error creating collection {}\n{}".format(
                error, traceback.format_exc()))
    return render_template(
        'forms/model.jinja',
        form=form,
        type='create',
        section='collection')


@collection.route('/collections/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin', 'Notandi')
def collection_list():
    form = UploadCollectionForm()
    if request.method == 'POST':
        if form.validate():
            if form.is_g2p.data:
                try:
                    zip_file = request.files.get('files')
                    with ZipFile(zip_file, 'r') as zip:
                        zip_name = zip_file.filename[:-4]
                        tsv_name = '{}/index.tsv'.format(zip_name)
                        collection = save_uploaded_collection(
                            zip, zip_name, tsv_name, form)
                    return redirect(url_for(
                        'collection.collection_detail',
                        id=collection.id))
                except Exception as e:
                    print(e)
                    flash(
                        'Ekki tókst að hlaða söfnun upp. Athugaðu hvort' +
                        ' öllum leiðbeiningum sé fylgt og reyndu aftur.',
                        category='warning')
            elif form.is_lobe_collection:
                try:
                    zip_file = request.files.get('files')
                    with ZipFile(zip_file, 'r') as zip:
                        zip_name = zip_file.filename[:-4]
                        json_name = 'info.json'
                        collection = save_uploaded_lobe_collection(
                            zip, zip_name, json_name, form)
                    return redirect(url_for(
                        'collection.collection_detail',
                        id=collection.id))
                except Exception as e:
                    print(e)
                    flash(
                        'Ekki tókst að hlaða söfnun upp. Athugaðu hvort' +
                        ' öllum leiðbeiningum sé fylgt og reyndu aftur.',
                        category='warning')
            else:
                flash(
                    'Ekki tókst að hlaða söfnun upp. Athugaðu hvort' +
                    ' öllum leiðbeiningum sé fylgt og reyndu aftur.',
                    category='warning')
        else:
            flash(
                'Ekki tókst að hlaða söfnun upp. Athugaðu hvort' +
                ' öllum leiðbeiningum sé fylgt og reyndu aftur.',
                category='warning')

    page = int(request.args.get('page', 1))
    collections = Collection.query.order_by(
        resolve_order(
            Collection,
            request.args.get('sort_by', default='name'),
            order=request.args.get('order', default='desc')))\
        .paginate(page, per_page=app.config['COLLECTION_PAGINATION'])
    return render_template(
        'collection_list.jinja',
        form=form,
        collections=collections,
        section='collection')


@collection.route('/collections/zip_list/')
@login_required
@roles_accepted('admin')
def collection_zip_list():
    page = int(request.args.get('page', 1))
    collections = db.session.query(Collection)\
        .filter_by(has_zip=True)\
        .paginate(page, per_page=app.config['COLLECTION_PAGINATION'])
    return render_template(
        'zip_list.jinja',
        zips=collections,
        section='collection')


@collection.route('/collections/<int:id>/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin', 'Notandi')
def collection_detail(id):
    token_form = BulkTokenForm(request.form)
    if request.method == 'POST':
        tokens = create_tokens(
            id,
            request.files.getlist('files'),
            token_form.is_g2p.data)

    collection = Collection.query.get(id)
    recorded_users = []
    all_users = collection.users
    for u in all_users:
        num = collection.get_user_number_of_recordings(u.id)
        json_user = {'user': u,
                    'number_of_recordings': num,
                    'time_estimate': collection.get_user_time_estimate(u.id),
                    'percentage': round((num/collection.num_tokens)*100)
                    }

        recorded_users.append(json_user)

    tokens = Token.query.filter(Token.collection_id == collection.id)\
        .order_by(resolve_order(
            Token,
            request.args.get('sort_by', default='created_at'),
            order=request.args.get('order', default='desc')))\
        .paginate(
            int(request.args.get('page', 1)),
            per_page=app.config['TOKEN_PAGINATION'])

    return render_template(
        'collection.jinja',
        collection=collection,
        token_form=token_form,
        recorded_users=recorded_users,
        tokens=tokens,
        users=User.query.order_by(User.name).all(),
        section='collection')


@collection.route('/collections/<int:id>/sessions', methods=['GET'])
@login_required
@roles_accepted('admin', 'Notandi')
def collection_sessions(id):
    page = int(request.args.get('page', 1))
    collection = Collection.query.get(id)
    rec_sessions = ListPagination(
        collection.sessions, page,
        app.config['SESSION_PAGINATION'])
    return render_template(
        'collection_session_list.jinja',
        collection=collection,
        sessions=rec_sessions,
        section='collection')


@collection.route('/collections/<int:id>/trim', methods=['GET'])
@login_required
@roles_accepted('admin')
def trim_collection(id):
    '''
    Trim all recordings in the collection
    '''
    trim_type = int(request.args.get('trim_type', default=0))
    app.executor.submit(trim_collection_handler, id, trim_type)
    flash('Söfnun verður klippt vonbráðar.', category='success')
    return redirect(url_for('collection.collection_detail', id=id))


@collection.route('/collections/<int:id>/generate_zip')
@login_required
@roles_accepted('admin')
def generate_zip(id):
    # TODO: Send some message in real-time to notify user when finished
    app.executor.submit(create_collection_zip, id)
    flash('Skjalasafn verður tilbúið vonbráðar.', category='success')
    return redirect(url_for('collection.collection_detail', id=id))


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
            ('Content-Disposition',
                f"attachment; filename=\"{collection.zip_fname}\"")],
        direct_passthrough=True)


@collection.route('/collections/stream_collection_demo')
@login_required
@roles_accepted('admin')
def stream_collection_index_demo():
    other_dir = app.config["OTHER_DIR"]
    try:
        return send_from_directory(
            other_dir, 'synidaemi_collection.zip',
            as_attachment=True)
    except Exception as error:
        app.logger.error(
            "Error downloading a custom recording : {}\n{}".format(
                error, traceback.format_exc()))


@collection.route('/collections/<int:id>/collection_info')
@login_required
@roles_accepted('admin')
def download_collection_info(id):
    info = create_collection_info(id)
    json.dump(
        info,
        open(
            os.path.join(app.config['TEMP_DIR'], f'{id}_info.json'),
            'w', encoding='utf-8'), ensure_ascii=False, indent=4)
    try:
        return send_from_directory(
            app.config['TEMP_DIR'],
            f'{id}_info.json',
            as_attachment=True)
    except Exception as error:
        app.logger.error(
            "Error downloading info : {}\n{}".format(
                error, traceback.format_exc()))


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
                return redirect(url_for('collection.collection_detail', id=id))
        except Exception as error:
            app.logger.error('Error updating a collection : {}\n{}'.format(
                error, traceback.format_exc()))

    form.is_multi_speaker.data = collection.is_multi_speaker
    form.is_dev.data = collection.is_dev
    form.verify.data = collection.verify

    return render_template(
        'forms/model.jinja',
        collection=collection,
        form=form,
        type='edit',
        action=url_for('collection.edit_collection', id=id),
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
        if has_zip:
            os.remove(zip_path)
        flash("{} var eytt".format(name), category='success')
    except Exception as error:
        flash(
            "Villa kom upp. Hafið samband við kerfisstjóra",
            category="danger")
        app.logger.error('Error updating a collection : {}\n{}'.format(
            error, traceback.format_exc()))
    return redirect(url_for('collection.collection_list'))


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
            flash(
                "Villa kom upp. Hafið samband við kerfisstjóra",
                category="danger")
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
    return redirect(url_for('collection.collection_detail', id=id))
