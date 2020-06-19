import datetime
import json
import math
import multiprocessing
import os
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from functools import partialmethod
from flask import flash
from models import Collection, Recording, Session, Token, Trim, User, db

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
                    token = Token(text, file.filename, collection_id, score=scr,
                        pron=pron, source=src)
                    tokens.append(token)
                    db.session.add(token)
                except ValueError as error:
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
        flash(f'{num_errors} villur komu upp, fyrsta villan í {error_file} í línu {error_line}',
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
    collection = Collection(form.name.data, form.sort_by.data,
        assigned_user_id=form.assigned_user_id.data,
        configuration_id=form.configuration_id.data)
    db.session.add(collection)
    db.session.flush()

    dirs = [collection.get_record_dir(), collection.get_token_dir(),
        collection.get_video_dir(), collection.get_wav_audio_dir()]
    # create dirs for tokens and records
    for dir in dirs:
        if not os.path.exists(dir): os.makedirs(dir)
        else:
            raise ValueError("""
                For some reason, we are about to create a collection with the
                same primary key as a previous collection. This could happen
                for example if 2 databases are used on the same machine. If
                this error occurs, the current environment has to change the
                DATA_BASE_DIR, TOKEN_DIR, RECORD_DIR flask environment variables
                to point to some other place.

                Folder that already exists: {}

                Perhaps some of the source folders have never been created before.
                """.format(dir))
    db.session.commit()
    return collection

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
        record_session = Session(user_id, collection_id, manager_id,
            duration=duration, has_video=has_video)
        db.session.add(record_session)
        db.session.flush()
    for token_id, recording_obj in recording_objs.items():
        # this token has a recording
        file_obj = files.get('file_{}'.format(token_id))
        recording = Recording(int(token_id), file_obj.filename, user_id,
            session_id=record_session.id, has_video=has_video)
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
            if is_voice and is_manager: break
            is_voice = is_voice or user.id == s.user_id
            is_manager = is_manager or user.id == s.manager_id
        if is_manager:
            if is_voice: role = "both"
            else: role = "manager"
        day_info[day] = {
            'sessions': sessions,
            'role': role,
            'start_time': sessions[0].get_start_time,
            'end_time': sessions[-1].created_at,
            'est_work_time': datetime.timedelta(seconds=math.ceil((sessions[-1].created_at - sessions[0].get_start_time).total_seconds())),
            'session_duration': datetime.timedelta(seconds=int(sum(s.duration for s in sessions)))}

    total_est_work_time = sum((i['est_work_time'] for _, i in day_info.items()),
        datetime.timedelta(0))
    total_session_duration = sum((i['session_duration'] for _, i in day_info.items()),
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
    return [u for u in User.query.all() if any(r.name == 'Greinir' for r in u.roles)]

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