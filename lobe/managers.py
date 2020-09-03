import datetime
import os
import json
import zipfile
import traceback
from random import randint

from flask import current_app as app


from lobe.tools.analyze import load_sample, find_segment
from lobe.models import User, Collection, db


def pseudo_unique():
    '''
    TODO: replace with something better.
    I used this to add some entropy to filenames in case multiple archives
    are created at the same time.
    '''
    return str(randint(10000, 99999))


class ZipManager:
    def __init__(self, collection):
        self.collection = collection
        self.meta_path = os.path.join(
            app.config['TEMP_DIR'],
            f'meta_{pseudo_unique()}.json')
        self.zf = zipfile.ZipFile(self.collection.zip_path, mode='w')

    def add_token(self, token):
        self.zf.write(token.get_path(), 'text/{}'.format(token.get_fname()))

    def add_recording(self, recording, user_id):
        self.zf.write(
            recording.get_zip_path(),
            'audio/{}/{}'.format(user_id, recording.get_zip_fname()))

    def add_recording_info(self, info_path):
        self.zf.write(info_path, 'info.json')

    def add_index(self, index_path):
        self.zf.write(index_path, 'index.tsv')

    def add_meta(self, speaker_ids):
        meta = {'speakers': []}
        for id in speaker_ids:
            meta['speakers'].append(User.query.get(id).get_meta())
        meta['collection'] = self.collection.get_meta()
        meta_f = open(self.meta_path, 'w', encoding='utf-8')
        json.dump(meta, meta_f, ensure_ascii=False, indent=4)
        meta_f.close()
        self.zf.write(self.meta_path, 'meta.json')

    def close(self):
        self.zf.close()

    def clean_up(self):
        os.remove(self.meta_path)


class IndexManager:
    def __init__(self):
        self.path = os.path.join(
            app.config['TEMP_DIR'],
            f'index_{pseudo_unique()}.tsv')
        self.index = open(self.path, 'w')
        self.is_closed = False

    def add(self, recording, token, user_name):
        self.index.write('{}\t{}\t{}\n'.format(
            user_name, recording.get_zip_fname(), token.get_fname()))

    def close(self):
        self.index.close()
        self.is_closed = True

    def clean_up(self):
        assert self.is_closed
        os.remove(self.path)

    def get_path(self):
        return self.path


class RecordingInfoManager:
    def __init__(self, write_file=True):
        self.info = {}
        self.write_file = write_file
        if self.write_file:
            self.path = os.path.join(
                app.config['TEMP_DIR'],
                f'info_{pseudo_unique()}.json')
            self.is_closed = False

    def add(self, recording, token, user_name):
        self.info[recording.id] = {
            'collection_info': {
                'user_name': user_name,
                'user_id': recording.user_id,
                'session_id': recording.session.id
                if recording.session else 'n/a'
            }, 'text_info': {
                'id': token.id,
                'fname': token.get_fname(),
                'score': token.score,
                'text': token.text,
                'pron': token.pron
            }, 'recording_info': {
                'recording_fname': recording.get_zip_fname(),
                'sr': recording.sr,
                'num_channels': recording.num_channels,
                'bit_depth': recording.bit_depth,
                'duration': recording.duration,
            }, 'other': {
                'transcription': recording.transcription,
                'recording_marked_bad': recording.marked_as_bad,
                'text_marked_bad': token.marked_as_bad}}
        if recording.start is not None and recording.end is not None:
            self.info[recording.id]['recording_info']['start']\
                = recording.start
            self.info[recording.id]['recording_info']['end']\
                = recording.end

    def close(self):
        if self.write_file:
            with open(self.path, 'w', encoding='utf-8') as info_f:
                json.dump(self.info, info_f, ensure_ascii=False, indent=4)
            self.is_closed = True

    def clean_up(self):
        if self.write_file:
            assert self.is_closed
            os.remove(self.path)

    def get_path(self):
        if self.write_file:
            return self.path


def create_collection_info(id):
    collection = Collection.query.get(id)
    dl_tokens = [t for t in collection.tokens if t.num_recordings > 0]
    if not os.path.exists(app.config['TEMP_DIR']):
        os.makedirs(app.config['TEMP_DIR'])
    recording_info_manager = RecordingInfoManager(write_file=False)
    for token in dl_tokens:
        for recording in token.recordings:
            speaker_name = recording.get_user().name
            recording_info_manager.add(recording, token, speaker_name)
    return recording_info_manager.info

def create_collection_zip(id):
    collection = Collection.query.get(id)
    dl_tokens = [t for t in collection.tokens if t.num_recordings > 0]
    if not os.path.exists(app.config['TEMP_DIR']):
        os.makedirs(app.config['TEMP_DIR'])
    speaker_ids = set()
    recording_info_manager = RecordingInfoManager()
    index_manager = IndexManager()
    zip_manager = ZipManager(collection)
    try:
        for token in dl_tokens:
            zip_manager.add_token(token)
            for recording in token.recordings:
                speaker_name = recording.get_user().name
                speaker_ids.add(recording.user_id)
                # HACK
                if recording.get_zip_path() is not None:
                    zip_manager.add_recording(recording, recording.user_id)
                    recording_info_manager.add(recording, token, speaker_name)
                    index_manager.add(recording, token, recording.user_id)
                else:
                    print(f"Error - token {token.id}",
                          " does not have a recording")

        index_manager.close()
        recording_info_manager.close()
        zip_manager.add_index(index_manager.get_path())
        zip_manager.add_recording_info(recording_info_manager.get_path())
        zip_manager.add_meta(speaker_ids)

    except Exception as error:
        print("{}\n{}".format(error, traceback.format_exc()))
        app.logger.error(
            "Error creating a collection .zip : {}\n{}".format(
                error, traceback.format_exc()))
    finally:
        zip_manager.close()
        try:
            zip_manager.clean_up()
            recording_info_manager.clean_up()
            index_manager.clean_up()
        except Exception as error:
            app.logger.error(
                "Error deleting files after generating an archive : {}\n{}"
                .format(error, traceback.format_exc()))

    # update the zip info for the collection
    collection.has_zip = True
    collection.zip_token_count = len(dl_tokens)
    collection.zip_created_at = datetime.datetime.now()
    db.session.commit()


def trim_collection_handler(id, trim_type):
    collection = Collection.query.get(id)
    if trim_type == 2:
        for token in collection.tokens:
            for recording in token.recordings:
                recording.reset_trim()
    else:
        tokens = [t for t in collection.tokens if t.num_recordings > 0]
        for token in tokens:
            for recording in token.recordings:
                if trim_type == 0 and not recording.has_trim or trim_type == 1:
                    sample, sr = load_sample(recording.get_path())
                    stamps = find_segment(
                        sample,
                        sr,
                        top_db=collection.configuration.trim_threshold)
                    recording.set_trim(float(stamps[0]), float(stamps[1]))
    db.session.commit()
