import json
import traceback
import random
import uuid
import numpy as np
from zipfile import ZipFile
from operator import itemgetter

from flask import (Blueprint, Response, send_from_directory, request,
                   render_template, flash, redirect, url_for)
from flask import current_app as app
from flask_security import login_required, roles_accepted, current_user
from sqlalchemy.exc import IntegrityError

from lobe.models import (Mos, Collection, MosInstance, User, Token,
                         CustomToken, CustomRecording, db)
from lobe.db import (resolve_order, save_custom_wav, save_MOS_ratings,
                     delete_mos_instance_db)
from lobe.forms import (MosSelectAllForm, MosUploadForm, MosItemSelectionForm,
                        MosTestForm, MosForm, MosDetailForm)

mos = Blueprint(
    'mos', __name__, template_folder='templates')


@mos.route('/mos/')
@login_required
@roles_accepted('admin')
def mos_list():
    page = int(request.args.get('page', 1))
    mos_list = Mos.query.order_by(
            resolve_order(
                Mos,
                request.args.get('sort_by', default='created_at'),
                order=request.args.get('order', default='desc')))\
        .paginate(page, per_page=app.config['MOS_PAGINATION'])
    collections = Collection.query.order_by(
            resolve_order(
                Collection,
                request.args.get('sort_by', default='name'),
                order=request.args.get('order', default='desc')))
    return render_template(
        'mos_list.jinja',
        mos_list=mos_list,
        collections=collections,
        section='mos')


@mos.route('/mos/collection/<int:id>')
@login_required
@roles_accepted('admin')
def mos_collection(id):
    page = int(request.args.get('page', 1))
    collection = Collection.query.get(id)
    mos_list = Mos.query.filter(Mos.collection_id == id).order_by(
            resolve_order(
                Mos,
                request.args.get('sort_by', default='created_at'),
                order=request.args.get('order', default='desc')))\
        .paginate(page, per_page=app.config['MOS_PAGINATION'])
    return render_template(
        'mos_collection_list.jinja',
        mos_list=mos_list,
        collection=collection,
        section='mos')


@mos.route('/mos/collection/none')
@login_required
@roles_accepted('admin')
def mos_collection_none():
    page = int(request.args.get('page', 1))
    collection = json.dumps({'name': 'Óháð söfnun', 'id': 0})
    mos_list = Mos.query.filter(Mos.collection_id == None).order_by(
            resolve_order(
                Mos,
                request.args.get('sort_by', default='created_at'),
                order=request.args.get('order', default='desc')))\
        .paginate(page, per_page=app.config['MOS_PAGINATION'])
    return render_template(
        'mos_no_collection_list.jinja',
        mos_list=mos_list,
        collection=collection,
        section='mos')


@mos.route('/mos/<int:id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def mos_detail(id):
    mos = Mos.query.get(id)
    form = MosUploadForm()
    select_all_forms = [
        MosSelectAllForm(is_synth=True, select=True),
        MosSelectAllForm(is_synth=True, select=False),
        MosSelectAllForm(is_synth=False, select=True),
        MosSelectAllForm(is_synth=False, select=False),
    ]

    if request.method == 'POST':
        if form.validate():
            if(form.is_g2p.data):
                zip_file = request.files.get('files')
                with ZipFile(zip_file, 'r') as zip:
                    zip_name = zip_file.filename[:-4]
                    tsv_name = '{}/index.tsv'.format(zip_name)
                    successfully_uploaded = save_custom_wav(
                        zip, zip_name, tsv_name, mos, id)
                    if len(successfully_uploaded) > 0:
                        flash("Tókst að hlaða upp {} setningum.".format(
                            len(successfully_uploaded)),
                            category="success")
                    else:
                        flash(
                            "Ekki tókst að hlaða upp neinum setningum.",
                            category="warning")
                return redirect(url_for('mos.mos_detail', id=id))
            else:
                flash(
                    "Ekki tókst að hlaða inn skrá. Eingögnu hægt að hlaða inn skrám á stöðluðu formi.",
                    category="danger")
        else:
            flash(
                "Villa í formi, athugaðu að rétt sé fyllt inn og reyndu aftur.",
                category="danger")

    mos_list = MosInstance.query.filter(MosInstance.mos_id == id).order_by(
            resolve_order(
                MosInstance,
                request.args.get('sort_by', default='id'),
                order=request.args.get('order', default='desc'))).all()

    if mos.collection is not None:
        collection = mos.collection
    else:
        collection = json.dumps({'name': 'Óháð söfnun', 'id': 0})

    ground_truths = []
    synths = []
    for m in mos_list:
        m.selection_form = MosItemSelectionForm(obj=m)
        if m.is_synth:
            synths.append(m)
        else:
            ground_truths.append(m)
    ratings = mos.getAllRatings()

    return render_template(
        'mos.jinja',
        mos=mos,
        mos_list=mos_list,
        collection=collection,
        select_all_forms=select_all_forms,
        ground_truths=ground_truths,
        synths=synths,
        mos_form=form,
        ratings=ratings,
        section='mos')


@mos.route('/mos/<int:id>/edit/detail', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def mos_edit_detail(id):
    mos = Mos.query.get(id)
    form = MosDetailForm(request.form, obj=mos)
    if request.method == "POST":
        if form.validate():
            form.populate_obj(mos)
            db.session.commit()
            return redirect(url_for("mos.mos_detail", id=mos.id))
    return render_template(
        'forms/model.jinja',
        form=form,
        type='edit',
        action=url_for('mos.mos_edit_detail', id=mos.id))


@mos.route('/mos/take_test/<uuid:mos_uuid>/', methods=['GET', 'POST'])
def take_mos_test(mos_uuid):
    mos = Mos.query.filter(Mos.uuid == str(mos_uuid)).first()
    form = MosTestForm(request.form)
    if request.method == "POST":
        if form.validate():
            try:
                # We don't really want to require email ,
                # but we have to fake one for the user model
                user_uuid = uuid.uuid4()
                email = "{}@lobe.is".format(user_uuid)
                new_user = app.user_datastore.create_user(
                    name=form.data["name"],
                    email=email,
                    password=None,
                    uuid=user_uuid,
                    audio_setup=form.data["audio_setup"],
                    roles=[]
                )
                form.populate_obj(new_user)
                mos.add_participant(new_user)
                db.session.commit()
            except IntegrityError as e:
                print(e)
                app.logger.error(
                    "Could not create user for application," +
                    " email already in use")
                flash("Þetta netfang er nú þegar í notkun", category='error')
                return redirect(
                    url_for("mos.take_mos_test", mos_uuid=mos_uuid))
            return redirect(
                url_for("mos.mos_test", id=mos.id, uuid=new_user.uuid))

    return render_template(
        'take_mos_test.jinja',
        form=form,
        type='create',
        mos=mos,
        action=url_for('mos.take_mos_test', mos_uuid=mos_uuid))


@mos.route('/mos/<int:id>/mostest/<string:uuid>', methods=['GET', 'POST'])
def mos_test(id, uuid):
    user = User.query.filter(User.uuid == uuid).first()
    if user.is_admin():
        if user.id != current_user.id:
            flash("Þú hefur ekki aðgang að þessari síðu", category='error')
            return redirect(url_for("mos", id=id))
    mos = Mos.query.get(id)
    if mos.use_latin_square:
        mos_configurations = mos.getConfigurations()
        mos_list = mos_configurations[(mos.num_participants - 1) % len(mos_configurations)]
    else:
        mos_instances = MosInstance.query.filter(MosInstance.mos_id == id, MosInstance.selected == True)
        mos_list = [instance for instance in mos_instances if instance.path]
        random.shuffle(mos_list)

    audio = []
    audio_url = []
    info = {'paths': [], 'texts': []}
    for i in mos_list:
        if i.custom_recording:
            audio.append(i.custom_recording)
            audio_url.append(i.custom_recording.get_download_url())
        else:
            continue
        info['paths'].append(i.path)
        info['texts'].append(i.text)
    audio_json = json.dumps([r.get_dict() for r in audio])
    mos_list_json = json.dumps([r.get_dict() for r in mos_list])

    return render_template(
        'mos_test.jinja',
        mos=mos,
        mos_list=mos_list,
        user=user,
        recordings=audio_json,
        recordings_url=audio_url,
        json_mos=mos_list_json,
        section='mos')


@mos.route('/mos/<int:id>/mos_results', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def mos_results(id):
    mos = Mos.query.get(id)
    mos_list = MosInstance.query.filter(MosInstance.mos_id == id).order_by(
            resolve_order(
                MosInstance,
                request.args.get('sort_by', default='id'),
                order=request.args.get('order', default='desc'))).all()
    ratings = mos.getAllRatings()
    max_placement = 1
    for j in ratings:
        if j.placement > max_placement:
            max_placement = j.placement

    if len(ratings) == 0:
        return redirect(url_for('mos.mos_detail', id=mos.id))
    user_ids = mos.getAllUsers()
    users = User.query.filter(User.id.in_(user_ids)).all()

    all_rating_stats = []
    placement = [0]*max_placement
    p_counter = [0]*max_placement
    for i in ratings:
        all_rating_stats.append(i.rating)
        placement[i.placement - 1] += i.rating
        p_counter[i.placement - 1] += 1
    all_rating_stats = np.array(all_rating_stats)
    for i in range(len(placement)):
        if p_counter[i] != 0 and placement[i] != 0:
            placement[i] = placement[i]/p_counter[i]
    placement_info = {
        'placement': placement,
        'p_nums': list(range(1, len(mos_list)))}
    rating_json = {
        'average': round(np.mean(all_rating_stats), 2),
        'std': round(np.std(all_rating_stats), 2)}
    mos_stats = {
        'names': [],
        'means': [],
        'total_amount': []}
    for m in mos_list:
        mos_stats['names'].append(str(m.id))
        mos_stats['means'].append(m.average_rating)
        mos_stats['total_amount'].append(m.number_of_ratings)
    users_list = []
    users_graph_json = []
    for u in users:
        user_ratings = mos.getAllUserRatings(u.id)
        ratings_stats = []
        for r in user_ratings:
            ratings_stats.append(r.rating)
        ratings_stats = np.array(ratings_stats)

        mos_ratings_per_user = []
        for m in mos_list:
            if not m.getUserRating(u.id):
                mos_ratings_per_user.append('')
            else:
                mos_ratings_per_user.append(m.getUserRating(u.id))
        user_ratings = {
            "username": u.get_printable_name(),
            "ratings": mos_ratings_per_user}
        temp = {
            'user': u,
            'mean': round(np.mean(ratings_stats), 2),
            'std': round(np.std(ratings_stats), 2),
            'total': len(ratings_stats),
            'user_ratings': mos_ratings_per_user}
        temp2 = {
            'user_ratings': user_ratings}
        users_list.append(temp)
        users_graph_json.append(temp2)

    users_list = sorted(users_list, key=itemgetter('mean'))

    # Average per voice index
    ratings_by_voice = mos.getResultsByVoice()
    per_voice_data = {
        "x": [],
        "y": [],
    }
    for voice_idx, ratings in ratings_by_voice.items():
        per_voice_data["x"].append(voice_idx)
        per_voice_data["y"].append(round(np.mean([r.rating for r in ratings])))

    return render_template(
        'mos_results.jinja',
        mos=mos,
        mos_stats=mos_stats,
        ratings=ratings,
        placement_info=placement_info,
        users=users_list,
        rating_json=rating_json,
        users_graph_json=users_graph_json,
        per_voice_data=per_voice_data,
        mos_list=mos_list,
        section='mos'
    )


@mos.route('/mos/<int:id>/mos_results/download', methods=['GET'])
@login_required
@roles_accepted('admin')
def download_mos_data(id):
    mos = Mos.query.get(id)
    response_lines = [
        "\t".join(map(str, line)) for line in mos.getResultData()
    ]
    r = Response(response="\n".join(response_lines), status=200, mimetype="text/plain")
    r.headers["Content-Type"] = "text/plain; charset=utf-8"
    return r


@mos.route('/mos/<int:id>/stream_zip')
@login_required
@roles_accepted('admin')
def stream_MOS_zip(id):
    mos = Mos.query.get(id)
    mos_list = MosInstance.query\
        .filter(MosInstance.mos_id == id)\
        .filter(MosInstance.is_synth == False).order_by(
            resolve_order(
                MosInstance,
                request.args.get('sort_by', default='id'),
                order=request.args.get('order', default='desc'))).all()

    results = 'mos_instance_id\tcustom_token_id\ttoken_text\n'
    for i in mos_list:
        results += "{}\t{}\t{}\n".format(
            str(i.id),
            str(i.custom_token.id),
            i.custom_token.text)

    generator = (cell for row in results for cell in row)

    return Response(
        generator,
        mimetype="text/plain",
        headers={
            "Content-Disposition":
            "attachment;filename={}_tokens.txt".format(
                mos.printable_id)}
        )


@mos.route('/mos/stream_mos_demo')
@login_required
@roles_accepted('admin')
def stream_MOS_index_demo():
    other_dir = app.config["OTHER_DIR"]
    try:
        return send_from_directory(
            other_dir, 'synidaemi_mos.zip', as_attachment=True)
    except Exception as error:
        app.logger.error(
            "Error downloading a custom recording : {}\n{}".format(
                error, traceback.format_exc()))


@mos.route('/mos/post_mos_rating/<int:id>', methods=['POST'])
def post_mos_rating(id):
    mos_id = id
    try:
        mos_id = save_MOS_ratings(request.form, request.files)
    except Exception as error:
        flash(
            "Villa kom upp. Hafið samband við kerfisstjóra",
            category="danger")
        app.logger.error("Error posting recordings: {}\n{}".format(
            error, traceback.format_exc()))
        return Response(str(error), status=500)
    if mos_id is None:
        flash("Engar einkunnir í MOS prófi.", category='warning')
        return Response(url_for('mos.mos_list'), status=200)

    flash("MOS próf klárað", category='success')
    if current_user.is_anonymous:
        return Response(
            url_for('mos.mos_done', id=mos_id), status=200)
    else:
        return Response(
            url_for('mos.mos_detail', id=mos_id), status=200)


@mos.route('/mos/instances/<int:id>/edit', methods=['POST'])
@login_required
@roles_accepted('admin')
def mos_instance_edit(id):
    try:
        instance = MosInstance.query.get(id)
        form = MosItemSelectionForm(request.form, obj=instance)
        form.populate_obj(instance)
        db.session.commit()
        response = {}
        return Response(json.dumps(response), status=200)
    except Exception as error:
        app.logger.error('Error creating a verification : {}\n{}'.format(
            error, traceback.format_exc()))
        errorMessage = "<br>".join(list("{}: {}".format(
            key, ", ".join(value)) for key, value in form.errors.items()))
        return Response(errorMessage, status=500)


@mos.route('/mos/<int:id>/select_all', methods=['POST'])
@login_required
@roles_accepted('admin')
def mos_select_all(id):
    try:
        form = MosSelectAllForm(request.form)
        is_synth = True if form.data['is_synth'] == 'True' else False
        select = True if form.data['select'] == 'True' else False
        mos_list = MosInstance.query\
            .filter(MosInstance.mos_id == id)\
            .filter(MosInstance.is_synth == is_synth).all()
        for m in mos_list:
            m.selected = select
        db.session.commit()
        return redirect(url_for('mos.mos_detail', id=id))
    except Exception as error:
        print(error)
        flash("Ekki gekk að merkja alla", category='warning')
    return redirect(url_for('mos.mos_detail', id=id))


@mos.route('/mos/instances/<int:id>/delete/', methods=['GET'])
@login_required
@roles_accepted('admin')
def delete_mos_instance(id):
    instance = MosInstance.query.get(id)
    mos_id = instance.mos_id
    did_delete, errors = delete_mos_instance_db(instance)
    if did_delete:
        flash("Línu var eytt", category='success')
    else:
        flash("Ekki gekk að eyða línu rétt", category='warning')
        print(errors)
    return redirect(url_for('mos.mos_detail', id=mos_id))


@mos.route('/mos/create', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def mos_create():
    try:
        mos = Mos()
        mos.uuid = uuid.uuid4()
        db.session.add(mos)
        db.session.commit()
        flash("Nýrri MOS prufu bætt við", category="success")
        return redirect(url_for('mos.mos_detail', id=mos.id))
    except Exception as error:
        flash("Error creating MOS.", category="danger")
        app.logger.error("Error creating MOS {}\n{}".format(
            error, traceback.format_exc()))
    return redirect(url_for('mos.mos_collection_none'))


@mos.route('/mos/collection/<int:id>/create', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def mos_create_collection(id):
    max_num_recorded = Collection.query.get(id).num_recorded_tokens
    form = MosForm(max_num_recorded, request.form)
    tokens = Token.query\
        .filter(Token.num_recordings > 0)\
        .filter(Token.collection_id == id).all()
    if request.method == 'POST' and form.validate():
        try:
            mos = Mos()
            form.populate_obj(mos)
            mos.uuid = uuid.uuid4()
            mos.collection = Collection.query.get(id)
            mos.collection_id = id
            tokens = Token.query.filter(Token.num_recordings > 0) \
                                .filter(Token.collection_id == id).all()
            random_tokens = random.sample(tokens, form.num_samples.data)
            for i in random_tokens:
                rand_recording_num = random.randint(0, len(i.recordings)-1)
                custom_token = CustomToken(i.text, i.original_fname, True)
                custom_token.copyToken(i)
                custom_recording = CustomRecording(True)
                custom_recording.copyRecording(
                    i.recordings[rand_recording_num])
                mos_instance = MosInstance(
                    custom_token=custom_token,
                    custom_recording=custom_recording)
                mos.mos_objects.append(mos_instance)
            db.session.add(mos)
            db.session.commit()
            flash("Nýrri MOS prufu bætt við", category="success")
            return redirect(url_for('mos.mos_detail', id=mos.id))
        except Exception as error:
            flash("Error creating MOS.", category="danger")
            app.logger.error("Error creating MOS {}\n{}".format(
                error, traceback.format_exc()))
    return render_template(
        'forms/model.jinja',
        form=form,
        action=url_for('mos.mos_create_collection', id=id),
        section='mos',
        type='create')


@mos.route('/custom-recording/<int:id>/download/')
def download_custom_recording(id):
    custom_recording = CustomRecording.query.get(id)
    try:
        return send_from_directory(
            custom_recording.get_directory(),
            custom_recording.fname,
            as_attachment=True)
    except Exception as error:
        app.logger.error(
            "Error downloading a custom recording : {}\n{}".format(
                error, traceback.format_exc()))


@mos.route('/custom_tokens/<int:id>/')
@login_required
@roles_accepted('admin', 'Notandi')
def custom_token(id):
    return render_template(
        'custom_token.jinja',
        token=CustomToken.query.get(id),
        section='token')


@mos.route('/custom_tokens/<int:id>/download/')
@login_required
@roles_accepted('admin', 'Notandi')
def download_custom_token(id):
    token = CustomToken.query.get(id)
    try:
        return send_from_directory(
            token.get_directory(),
            token.fname,
            as_attachment=True)
    except Exception as error:
        app.logger.error(
            "Error downloading a token : {}\n{}".format(
                error, traceback.format_exc()))


@mos.route('/mos-done/<int:id>', methods=['GET'])
def mos_done(id):
    mos = Mos.query.get(id)
    return render_template("mos_done.jinja", mos=mos)
