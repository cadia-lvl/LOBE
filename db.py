from models import db, Collection, Session, Token, Recording
from concurrent.futures import ProcessPoolExecutor
from collections import defaultdict
from functools import partialmethod
import multiprocessing
import os
import datetime
import math
import json

from settings.common import RECORDING_BIT_DEPTH

def create_tokens(collection_id, files, is_g2p):
    tokens = []
    for file in files:
        if is_g2p:
            i_f = file.stream.read().decode("utf-8").split('\n')
            for line in i_f:
                try:
                    text, src, scr, *pron = line.split('\t')[0:]
                    pron = '\t'.join(p for p in pron)
                    token = Token(text, file.filename, collection_id, score=scr,
                        pron=pron, source=src)
                    tokens.append(token)
                    db.session.add(token)
                except ValueError:
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
        has_video=form.has_video.data,
        assigned_user_id=form.assigned_user_id.data)
    db.session.add(collection)
    db.session.flush()

    dirs = [collection.get_record_dir(), collection.get_token_dir(),
        collection.zip_path]
    if collection.has_video:
        dirs.append(collection.get_video_dir())
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
    recording_objs = json.loads(form['recordings'])
    record_session = None
    if len(recording_objs) > 0:
        record_session = Session(user_id, collection_id, manager_id,
            duration=duration)
        db.session.add(record_session)
        db.session.flush()
    for token_id, recording_obj in recording_objs.items():
        # this token has a recording
        file_obj = files.get('file_{}'.format(token_id))
        recording = Recording(int(token_id), file_obj.filename, user_id,
            recording_obj['transcript'], RECORDING_BIT_DEPTH,
            session_id=record_session.id)
        db.session.add(recording)
        db.session.flush()
        recording.add_file_obj(file_obj)
    db.session.commit()

    for token_id in recording_objs:
        token = Token.query.get(token_id)
        token.update_numbers()
    db.session.commit()

    for token_id in json.loads(form['skipped']):
        # this token was skipped and has no token
        token = Token.query.get(int(token_id))
        token.marked_as_bad = True
    db.session.commit()

    # then update the numbers of the collection
    collection = Collection.query.get(collection_id)
    collection.update_numbers()
    db.session.commit()

    return record_session.id if record_session else None

def newest_collections(num=4):
    ''' Get the num newest collections '''
    return Collection.query.order_by(Collection.created_at.desc()).limit(num)


def newest_sessions(user_id, num=4):
    ''' Get the num newest collections '''
    return Session.query.filter(Session.user_id==user_id,).order_by(Session.created_at.desc()).limit(num)

def sessions_day_info(sessions, user):
    # insert by dates
    days = defaultdict(list)
    for s in sessions:
        days[s.created_at.date()].append(s)

    day_info = dict()
    for day, sessions in days.items():
        is_voice = False
        is_manager = False
        for s in sessions:
            if is_voice and is_manager: break
            is_voice == is_voice or user.id == s.user_id
            is_manager == is_manager or user.id == s.manager_id
        role = "voice"
        if is_voice and is_manager:
            role = "both"
        else:
            role = "manager"
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