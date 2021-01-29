import datetime
import json
import math
import os
import traceback
from flask import current_app as app
import csv
from pydub import AudioSegment
from pydub.utils import mediainfo
import pathlib
from werkzeug import secure_filename
from collections import defaultdict
from flask import flash
from sqlalchemy import func
from flask_security import current_user
from lobe.models import (Collection, Recording, Session, Token, Trim,
                         User, db, MosInstance, CustomRecording,
                         CustomToken, MosRating)


def create_tokens(collection_id, files, is_g2p):
    tokens = []
    num_errors = 0
    error_line, error_file = None, None
    for file in files:
        if is_g2p:
            i_f = file.stream.read().decode("utf-8").split('\n')
            for idx, line in enumerate(i_f):
                try:
                    text, src, scr, *pron = line.split('\t')[0:]
                    pron = '\t'.join(p for p in pron)
                    token = Token(
                        text,
                        file.filename,
                        collection_id,
                        score=scr,
                        pron=pron,
                        source=src)
                    tokens.append(token)
                    db.session.add(token)
                except ValueError:
                    num_errors += 1
                    error_line = idx + 1
                    error_file = file.filename
                    continue
        else:
            content = file.stream.read().decode("utf-8").strip().split('\n')
            for c in content:
                # we split each file by new lines
                if c[-1] == ',':
                    # this is a hack for the SQL stuff.
                    c = c[:-1]
                token = Token(c, file.filename, collection_id)
                tokens.append(token)
                # add token to database
                db.session.add(token)

    if num_errors > 0:
        flash(
            f'{num_errors} villur komu upp, fyrsta villan í' +
            f'{error_file} í línu {error_line}',
            category='danger')

    db.session.commit()

    # save token text to file
    for token in tokens:
        token.save_to_disk()
    db.session.commit()

    # reset the number of tokens in the collection
    collection = Collection.query.get(collection_id)
    collection.update_numbers()
    db.session.commit()
    return tokens


def insert_collection(form):
    collection = Collection()
    form.populate_obj(collection)
    db.session.add(collection)
    db.session.flush()

    dirs = [
        collection.get_record_dir(), collection.get_token_dir(),
        collection.get_video_dir(), collection.get_wav_audio_dir()]
    # create dirs for tokens and records
    for dir in dirs:
        if not os.path.exists(dir):
            os.makedirs(dir)
        else:
            raise ValueError("""
                For some reason, we are about to create a collection with the
                same primary key as a previous collection. This could happen
                for example if 2 databases are used on the same machine. If
                this error occurs, the current environment has to change the
                DATA_BASE_DIR, TOKEN_DIR, RECORD_DIR flask environment
                variables to point to some other place.

                Folder that already exists: {}

                Perhaps some of the source folders have never been created
                before.
                """.format(dir))
    db.session.commit()
    return collection


def save_custom_wav(zip, zip_name, tsv_name, mos, id):
    # Create parent folders if missing (this should probably be done somewhere else)
    pathlib.Path(app.config["WAV_CUSTOM_AUDIO_DIR"]).mkdir(exist_ok=True)
    pathlib.Path(app.config["CUSTOM_RECORDING_DIR"]).mkdir(exist_ok=True)
    pathlib.Path(app.config["CUSTOM_TOKEN_DIR"]).mkdir(exist_ok=True)

    with zip.open(tsv_name) as tsvfile:
        wav_path_dir = app.config["WAV_CUSTOM_AUDIO_DIR"]+"{}".format(id)
        webm_path = app.config["CUSTOM_RECORDING_DIR"]+"{}".format(id)
        mc = tsvfile.read()
        c = csv.StringIO(mc.decode())
        rd = csv.reader(c, delimiter="\t")
        pathlib.Path(wav_path_dir).mkdir(exist_ok=True)
        pathlib.Path(webm_path).mkdir(exist_ok=True)
        custom_tokens = []
        for row in rd:
            if row[0] and (len(row) == 3 or len(row) == 5 or len(row) == 6):
                if not ((row[1].lower() == 's' or row[1].lower() == 'r') and row[2]):
                    pass
                if not (row[3] and row[3].isnumeric() and row[4] and row[4].isnumeric() and row[5]):
                    pass
                for zip_info in zip.infolist():
                    if zip_info.filename[-1] == '/':
                        continue
                    zip_info.filename = os.path.basename(zip_info.filename)
                    if zip_info.filename == row[0]:
                        custom_token_name = '{}_m{:09d}'.format(
                            zip_name, id)
                        custom_recording = CustomRecording()
                        custom_token = CustomToken(
                            row[2], custom_token_name)
                        if len(row) == 3:
                            mos_instance = MosInstance(
                                custom_token=custom_token,
                                custom_recording=custom_recording)
                        elif len(row) == 5:
                            mos_instance = MosInstance(
                                custom_token=custom_token,
                                custom_recording=custom_recording,
                                voice_idx=row[3],
                                utterance_idx=row[4])
                        elif len(row) == 6:
                            mos_instance = MosInstance(
                                custom_token=custom_token,
                                custom_recording=custom_recording,
                                voice_idx=row[3],
                                utterance_idx=row[4],
                                question=row[5])
                        db.session.add(custom_token)
                        db.session.add(custom_recording)
                        db.session.add(mos_instance)
                        db.session.flush()
                        file_id = '{}_s{:09d}_m{:09d}'.format(
                            os.path.splitext(
                                os.path.basename(zip_info.filename))[0],
                            custom_recording.id, id)
                        fname = secure_filename(f'{file_id}.webm')
                        path = os.path.join(
                            app.config['CUSTOM_RECORDING_DIR'],
                            str(id), fname)
                        wav_path = os.path.join(
                            app.config['WAV_CUSTOM_AUDIO_DIR'],
                            str(id),
                            secure_filename(f'{file_id}.wav'))
                        zip_info.filename = secure_filename(
                            f'{file_id}.wav')
                        zip.extract(zip_info, wav_path_dir)
                        sound = AudioSegment.from_wav(wav_path)
                        sound.export(path, format="webm")
                        custom_recording.original_fname = row[0]
                        custom_recording.user_id = current_user.id
                        custom_recording.file_id = file_id
                        custom_recording.fname = fname
                        custom_recording.path = path
                        custom_recording.wav_path = wav_path
                        if row[1].lower() == 's':
                            mos_instance.is_synth = True
                        else:
                            mos_instance.is_synth = False
                        mos.mos_objects.append(mos_instance)
                        custom_tokens.append(custom_token)
                
        if len(custom_tokens) > 0:
            custom_token_dir = app.config["CUSTOM_TOKEN_DIR"]+"{}".format(id)
            pathlib.Path(custom_token_dir).mkdir(exist_ok=True)
            for token in custom_tokens:
                token.save_to_disk()
            db.session.commit()
        return custom_tokens


def save_uploaded_collection(zip, zip_name, tsv_name, form):
    # creating new collection
    collection = Collection()
    form.populate_obj(collection)
    db.session.add(collection)
    db.session.flush()

    dirs = [
            collection.get_record_dir(),
            collection.get_token_dir(),
            collection.get_video_dir(),
            collection.get_wav_audio_dir()]

    # create dirs for tokens and records
    for dir in dirs:
        if not os.path.exists(dir):
            os.makedirs(dir)
        else:
            raise ValueError("""
                For some reason, we are about to create a collection with the
                same primary key as a previous collection. This could happen
                for example if 2 databases are used on the same machine. If
                this error occurs, the current environment has to change the
                DATA_BASE_DIR, TOKEN_DIR, RECORD_DIR flask environment
                variables to point to some other place.

                Folder that already exists: {}

                Perhaps some of the source folders have never been created
                before.
                """.format(dir))

    with zip.open(tsv_name) as tsvfile:
        mc = tsvfile.read()
        c = csv.StringIO(mc.decode())
        rd = csv.reader(c, delimiter="\t")
        tokens = []
        duration = 0
        user_id = int(form.data['assigned_user_id'])
        manager_id = current_user.id
        collection_id = collection.id
        has_video = False

        # creating session
        record_session = Session(
            user_id, collection_id, manager_id,
            duration=duration, has_video=has_video, is_dev=collection.is_dev)
        db.session.add(record_session)
        db.session.flush()

        for row in rd:
            if row[0] and len(row) >= 2:
                for zip_info in zip.infolist():
                    if zip_info.filename[-1] == '/':
                        continue
                    zip_info.filename = os.path.basename(zip_info.filename)
                    if zip_info.filename == row[0]:
                        try:
                            # create a new token
                            if not row[1]:
                                continue
                            text = row[1]
                            src = row[2] if row[2] else None
                            scr = row[3] if row[3] else None
                            pron = row[4] if row[4] else None
                            token = Token(
                                text, zip_name, collection.id, score=scr,
                                pron=pron, source=src)
                            tokens.append(token)
                            db.session.add(token)
                            db.session.flush()

                        except ValueError as error:
                            print(error)
                            continue

                        recording = Recording(
                            int(token.id), row[0], user_id,
                            session_id=record_session.id, has_video=has_video)

                        db.session.add(recording)
                        db.session.flush()
                        recording._set_path()

                        zip_info.filename = '{}.wav'.format(os.path.splitext(
                            os.path.basename(recording.fname))[0])
                        export_to_path = secure_filename('{}.webm'.format(
                            os.path.splitext(os.path.basename(row[0]))[0]))
                        export_to_path = os.path.join(dirs[0], export_to_path)

                        zip.extract(zip_info, dirs[3])
                        sound = AudioSegment.from_wav(recording.wav_path)
                        sound.export(recording.path, format="webm")

                        info = mediainfo(recording.path)

                        recorder_settings = {
                            'sampleRate': info['sample_rate'],
                            'sampleSize': 16,
                            'channelCount': info['channels'],
                            'latency': 0,
                            'autoGainControl': False,
                            'echoCancellation': False,
                            'noiseSuppression': False,
                        }

                        recording._set_wave_params(recorder_settings)

        db.session.commit()

        for t in tokens:
            t.save_to_disk()
            t.update_numbers()
        db.session.commit()

        # then update the numbers of the collection
        collection.update_numbers()
        db.session.commit()

    return collection


def is_valid_info(data):
    if 'collection_info' in data and \
            'text_info' in data and \
            'recording_info' in data and \
            'other' in data:
        if 'text' in data['text_info'] and \
                "session_id" in data["collection_info"] and \
                "recording_fname" in data["recording_info"] and \
                "text_marked_bad" in data["other"] and \
                "recording_marked_bad" in data["other"] and\
                "duration" in data["recording_info"]:
            return True
    return False


def save_uploaded_lobe_collection(zip, zip_name, json_name, form):
    # creating new collection
    collection = Collection()
    form.populate_obj(collection)
    db.session.add(collection)
    db.session.flush()

    dirs = [
        collection.get_record_dir(),
        collection.get_token_dir(),
        collection.get_video_dir(),
        collection.get_wav_audio_dir()]
    # create dirs for tokens and records
    for dir in dirs:
        if not os.path.exists(dir):
            os.makedirs(dir)
        else:
            raise ValueError("""
                For some reason, we are about to create a collection with the
                same primary key as a previous collection. This could happen
                for example if 2 databases are used on the same machine. If
                this error occurs, the current environment has to change the
                DATA_BASE_DIR, TOKEN_DIR, RECORD_DIR flask environment
                variables to point to some other place.

                Folder that already exists: {}

                Perhaps some of the source folders have never been created
                before.
                """.format(dir))

    with zip.open(json_name) as json_file:
        data = json_file.read()
        info = json.loads(data.decode("utf-8"))
        tokens = []
        # creating session
        duration = 0
        user_id = int(form.data['assigned_user_id'])
        manager_id = current_user.id
        collection_id = collection.id
        has_video = False
        sessions = {}
        for key in info:
            if is_valid_info(info[key]):
                for zip_info in zip.infolist():
                    row = info[key]
                    session_id = row["collection_info"]["session_id"]
                    duration = row["recording_info"]["duration"]
                    if session_id not in sessions:
                        new_record_session = Session(
                            user_id, collection_id, manager_id,
                            duration=duration, has_video=has_video,
                            is_dev=collection.is_dev)
                        db.session.add(new_record_session)
                        db.session.flush()
                        sessions[session_id] = {
                            'session': new_record_session,
                            'duration': []}
                        record_session = new_record_session
                    else:
                        record_session = sessions[session_id]['session']
                    info_filename = row["recording_info"]["recording_fname"]
                    zip_info.filename = os.path.basename(zip_info.filename)
                    if zip_info.filename == info_filename:
                        try:
                            text = row["text_info"]["text"]
                            src = row["text_info"]["fname"] if \
                                row["text_info"]["fname"] else None
                            scr = row["text_info"]["score"]
                            pron = row["text_info"]["pron"]
                            token = Token(
                                text, zip_name, collection.id, score=scr,
                                pron=pron, source=src)
                            tokens.append(token)
                            db.session.add(token)
                            db.session.flush()
                            if row['other']['text_marked_bad'] == 'true':
                                token.marked_as_bad = True

                        except ValueError as error:
                            print(error)

                        recording = Recording(
                            int(token.id), info_filename, user_id,
                            session_id=record_session.id, has_video=has_video)

                        db.session.add(recording)
                        db.session.flush()
                        recording._set_path()
                        zip_info.filename = '{}.wav'.format(os.path.splitext(
                            os.path.basename(recording.fname))[0])
                        export_to_path = secure_filename('{}.webm'.format(
                            os.path.splitext(
                                os.path.basename(info_filename))[0]))
                        export_to_path = os.path.join(dirs[0], export_to_path)
                        zip.extract(zip_info, dirs[3])
                        sound = AudioSegment.from_wav(recording.wav_path)
                        sound.export(recording.path, format="webm")
                        recorder_settings = {
                            'sampleRate': row["recording_info"]["sr"],
                            'sampleSize': row["recording_info"]["bit_depth"],
                            'channelCount':
                                row["recording_info"]["num_channels"],
                            'latency': 0,
                            'autoGainControl': False,
                            'echoCancellation': False,
                            'noiseSuppression': False,
                        }
                        recording._set_wave_params(recorder_settings)
                        if row['other']['recording_marked_bad'] == 'true':
                            recording.marked_as_bad = True
                        sessions[session_id]['duration'].append(duration)
        for key in sessions:
            sessions[session_id]['session'].duration = sum(
                sessions[session_id]['duration'])
        db.session.commit()

        for t in tokens:
            t.save_to_disk()
            t.update_numbers()
        db.session.commit()
        # then update the numbers of the collection
        collection.update_numbers()
        db.session.commit()
    return collection


def is_valid_rating(rating):
    if int(rating) > 0 and int(rating) <= 5:
        return True
    return False


def delete_rating_if_exists(mos_instance_id, user_id):
    rating = MosRating.query\
        .filter(MosRating.mos_instance_id == mos_instance_id) \
        .filter(MosRating.user_id == user_id).all()
    exists = False
    for r in rating:
        exists = True
        db.session.delete(r)
    db.session.commit()
    return exists


def save_MOS_ratings(form, files):
    user_id = int(form['user_id'])
    mos_id = int(form['mos_id'])
    mos_list = json.loads(form['mos_list'])
    if len(mos_list) == 0:
        return None
    for i in mos_list:
        if "rating" in i:
            if is_valid_rating(i['rating']):
                delete_rating_if_exists(i['id'], user_id)
                mos_instance = MosInstance.query.get(i['id'])
                rating = MosRating()
                rating.rating = int(i['rating'])
                rating.user_id = user_id
                rating.placement = i['placement']
                mos_instance.ratings.append(rating)
    db.session.commit()
    return mos_id


def save_recording_session(form, files):
    duration = float(form['duration'])
    user_id = int(form['user_id'])
    manager_id = int(form['manager_id'])
    collection_id = int(form['collection_id'])
    collection = Collection.query.get(collection_id)
    has_video = collection.configuration.has_video
    recording_objs = json.loads(form['recordings'])
    skipped = json.loads(form['skipped'])
    record_session = None
    if len(recording_objs) > 0 or len(skipped):
        record_session = Session(
            user_id,
            collection_id,
            manager_id,
            duration=duration,
            has_video=has_video,
            is_dev=collection.is_dev)
        db.session.add(record_session)
        db.session.flush()
    for token_id, recording_obj in recording_objs.items():
        # this token has a recording
        file_obj = files.get('file_{}'.format(token_id))
        recording = Recording(
            int(token_id),
            file_obj.filename,
            user_id,
            session_id=record_session.id,
            has_video=has_video)
        if "analysis" in recording_obj:
            recording.analysis = recording_obj['analysis']
        if "cut" in recording_obj:
            recording.start = recording_obj['cut']['start']
            recording.end = recording_obj['cut']['end']
        if "transcription" in recording_obj and recording_obj['transcription']:
            recording.transcription = recording_obj['transcription']
        db.session.add(recording)
        db.session.flush()
        recording.add_file_obj(file_obj, recording_obj['settings'])
    db.session.commit()

    for token_id in recording_objs:
        token = Token.query.get(token_id)
        token.update_numbers()
    db.session.commit()

    for token_id in skipped:
        # this token was skipped and has no token
        token = Token.query.get(int(token_id))
        token.marked_as_bad = True
        token.marked_as_bad_session_id = record_session.id
    db.session.commit()

    # then update the numbers of the collection
    collection.update_numbers()
    db.session.commit()
    return record_session.id if record_session else None


def sessions_day_info(sessions, user):
    # insert by dates
    days = defaultdict(list)
    for s in sessions:
        days[s.created_at.date()].append(s)

    day_info = dict()
    for day, sessions in days.items():
        is_voice, is_manager = False, False
        role = "voice"
        for s in sessions:
            if is_voice and is_manager:
                break
            is_voice = is_voice or user.id == s.user_id
            is_manager = is_manager or user.id == s.manager_id
        if is_manager:
            if is_voice:
                role = "both"
            else:
                role = "manager"
        day_info[day] = {
            'sessions': sessions,
            'role': role,
            'start_time': sessions[0].get_start_time,
            'end_time': sessions[-1].created_at,
            'est_work_time': datetime.timedelta(
                seconds=math.ceil(
                    (sessions[-1].created_at - sessions[0]
                        .get_start_time).total_seconds())),
            'session_duration': datetime.timedelta(
                seconds=int(sum(s.duration for s in sessions)))}

    total_est_work_time = sum(
        (i['est_work_time'] for _, i in day_info.items()),
        datetime.timedelta(0))
    total_session_duration = sum(
        (i['session_duration'] for _, i in day_info.items()),
        datetime.timedelta(0))

    return day_info, total_est_work_time, total_session_duration


def delete_recording_db(recording):
    collection = Collection.query.get(recording.get_collection_id())
    token = recording.get_token()
    try:
        os.remove(recording.get_path())
        if recording.get_wav_path is not None:
            os.remove(recording.get_wav_path())
    except Exception as error:
        print(f'{error}\n{traceback.format_exc()}')
        return False
    db.session.delete(recording)
    db.session.commit()

    token.update_numbers()
    db.session.commit()

    collection.update_numbers()
    db.session.commit()
    return True


def delete_token_db(token):
    try:
        os.remove(token.get_path())
    except Exception as error:
        print(f'{error}\n{traceback.format_exc()}')
        return False

    recordings = token.recordings
    collection = token.collection
    db.session.delete(token)
    for recording in recordings:
        try:
            os.remove(recording.get_path())
        except Exception as error:
            print(f'{error}\n{traceback.format_exc()}')
            return False
        db.session.delete(recording)

    collection.update_numbers()
    db.session.commit()
    return True


def delete_mos_instance_db(instance):
    errors = []
    try:
        os.remove(instance.custom_token.get_path())
        os.remove(instance.custom_recording.get_path())
    except Exception as error:
        errors.append("Remove from disk error")
        print(f'{error}\n{traceback.format_exc()}')
    try:
        db.session.delete(instance)
        db.session.commit()
    except Exception as error:
        errors.append("Remove from database error")
        print(f'{error}\n{traceback.format_exc()}')
    if errors:
        return False, errors
    return True, errors


def delete_session_db(record_session):
    tokens = [r.get_token() for r in record_session.recordings]
    collection = Collection.query.get(record_session.collection_id)
    try:
        for recording in record_session.recordings:
            os.remove(recording.get_path())
            if recording.get_wav_path() is not None:
                os.remove(recording.get_wav_path())
    except FileNotFoundError:
        pass
    except Exception as error:
        print(f'{error}\n{traceback.format_exc()}')
        return False
    for recording in record_session.recordings:
        db.session.delete(recording)
    db.session.delete(record_session)
    db.session.commit()

    for token in tokens:
        token.update_numbers()
    db.session.commit()

    collection.update_numbers()
    db.session.commit()
    return True


def resolve_order(object, sort_by, order='desc'):
    ordering = getattr(object, sort_by)
    if callable(ordering):
        ordering = ordering()
    if str(order) == 'asc':
        return ordering.asc()
    else:
        return ordering.desc()


def get_verifiers():
    return [u for u in User.query.all()
            if any(r.name == 'Greinir' for r in u.roles)]


def get_admins():
    return [u for u in User.query.all()
            if u.is_admin()]


def insert_trims(trims, verification_id):
    '''
    trims is a list of dictionaries sorted in time order, e.g.:
    [{"start":0.6633760683760684,"end":0.9950641025641026},
        {"start":1.1801923076923078,"end":1.6121581196581196}]
    '''
    trims = json.loads(trims)
    for idx, trim_data in enumerate(trims):
        trim = Trim()
        trim.start = trim_data['start']
        trim.end = trim_data['end']
        trim.index = idx
        trim.verification_id = verification_id
        db.session.add(trim)
    db.session.commit()


def activity(model):
    '''
    Returns two lists (x, y) where x contains timestamps
    and y contains the number of items of the given model
    that were created at the given day
    '''
    groups = ['year', 'month', 'day']
    groups = [func.extract(x, model.created_at).label(x) for x in groups]
    q = (
            db.session.query(func.count(model.id).label('count'), *groups)
            .group_by(*groups)
            .order_by(*groups)
            .all())
    x = [
            (lambda x: f'{int(x.day)}/{int(x.month)}/{int(x.year)}')(el)
            for el in q]
    y = [el.count for el in q]
    return x, y
