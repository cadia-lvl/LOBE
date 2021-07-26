import contextlib
import os
import uuid
import wave
import json
import subprocess
import random
from collections import Counter, defaultdict

import numpy as np
from datetime import datetime, timedelta

from flask import current_app as app
from flask import url_for
from flask_security import RoleMixin, UserMixin
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import relationship
from werkzeug import secure_filename

from wtforms_components import ColorField
from wtforms import validators

from lobe.tools.latin_square import balanced_latin_squares

db = SQLAlchemy()

ADMIN_ROLE_ID = 1
ADMIN_ROLE_NAME = "admin"
ESTIMATED_AVERAGE_RECORD_LENGTH = 5


class BaseModel(db.Model):
    """Base data model for all objects"""
    __abstract__ = True

    def __init__(self, *args):
        super().__init__(*args)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, {
            column: value
            for column, value in self.__dict__.items()})


class Collection(BaseModel, db.Model):
    __tablename__ = 'Collection'

    id = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        autoincrement=True)
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())
    name = db.Column(
        db.String,
        default=str(datetime.now().date()))
    assigned_user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'))
    is_multi_speaker = db.Column(
        db.Boolean,
        default=False)
    configuration_id = db.Column(
        db.Integer,
        db.ForeignKey('Configuration.id'))
    tokens = db.relationship(
        "Token",
        lazy='select',
        backref='collection',
        cascade='all, delete, delete-orphan')
    sessions = db.relationship(
        "Session",
        lazy='select',
        backref='collection',
        cascade='all, delete, delete-orphan')
    active = db.Column(
        db.Boolean,
        default=True)
    sort_by = db.Column(db.String)
    num_tokens = db.Column(
        db.Integer,
        default=0)
    num_recorded_tokens = db.Column(
        db.Integer,
        default=0)
    num_invalid_tokens = db.Column(
        db.Integer,
        default=0)
    has_zip = db.Column(
        db.Boolean,
        default=False)
    zip_token_count = db.Column(
        db.Integer,
        default=0)
    zip_created_at = db.Column(db.DateTime)
    is_dev = db.Column(
        db.Boolean,
        default=False)
    verify = db.Column(db.Boolean, default=False)

    @hybrid_property
    def num_nonrecorded_tokens(self):
        return self.num_tokens - self.num_recorded_tokens

    @hybrid_method
    def get_complete_ratio(self, as_percent=False):
        if self.num_tokens == 0 or self.number_of_users == 0:
            ratio = 0
        else:
            if not self.is_multi_speaker:
                ratio = (self.num_tokens - self.num_nonrecorded_tokens)\
                        / self.num_tokens
            else:
                ratio = (self.number_of_recordings)\
                        / (self.num_tokens * self.number_of_users)
        if as_percent:
            ratio = round(ratio*100, 3)
        return ratio

    @hybrid_method
    def get_invalid_ratio(self, as_percent=False):
        if self.num_tokens == 0:
            ratio = 0
        else:
            if self.is_multi_speaker:
                ratio = (self.num_invalid_tokens) / (self.num_tokens)
            else:
                ratio = (self.num_invalid_tokens) / self.num_tokens
        if as_percent:
            ratio = round(ratio*100, 3)
        return ratio

    def get_url(self):
        return url_for('collection.collection_detail', id=self.id)

    def get_download_url(self):
        return url_for('collection.stream_collection_zip', id=self.id)

    def get_edit_url(self):
        return url_for('collection.edit_collection', id=self.id)

    def get_trim_url(self, trim_type):
        return url_for('collection.trim_collection', id=self.id) +\
            f'?trim_type={trim_type}'

    def get_record_dir(self):
        return os.path.join(app.config['RECORD_DIR'], str(self.id))

    def get_token_dir(self):
        return os.path.join(app.config['TOKEN_DIR'], str(self.id))

    def get_video_dir(self):
        return os.path.join(app.config['VIDEO_DIR'], str(self.id))

    def get_wav_audio_dir(self):
        return os.path.join(app.config['WAV_AUDIO_DIR'], str(self.id))

    def has_assigned_user(self):
        return self.assigned_user_id is not None

    def get_assigned_user(self):
        if self.has_assigned_user():
            return User.query.get(self.assigned_user_id)

    @hybrid_property
    def zip_path(self):
        return os.path.join(app.config['ZIP_DIR'], self.zip_fname)

    @hybrid_property
    def zip_fname(self):
        return f'{self.id}.zip'

    def get_sortby_function(self):
        if self.sort_by == "score":
            return Token.score.desc()
        elif self.sort_by == "random":
            return func.random()
        else:
            return Token.id

    def update_numbers(self):
        tokens = Token.query.filter(Token.collection_id == self.id)
        self.num_tokens = tokens.count()
        self.num_invalid_tokens = \
            tokens.filter(Token.marked_as_bad == True).count()
        self.num_recorded_tokens = \
            tokens.filter(Token.num_recordings > 0).count()

    def get_meta(self):
        '''
        Returns a dictionary of values that are included in meta.json
        when downloading collections
        '''
        meta = {
            'id': self.id,
            'name': self.name}
        if self.has_assigned_user():
            meta['assigned_user_id'] = self.get_assigned_user().id
        return meta

    def estimate_hours(self):
        '''
        Returns an estimate of hours of speech given the number
        of sentences spoken.
        '''
        if not self.is_multi_speaker:
            return round((self.num_tokens - self.num_nonrecorded_tokens)
                        * ESTIMATED_AVERAGE_RECORD_LENGTH / 3600, 1)
        else:
            return round((self.number_of_recordings)
                        * ESTIMATED_AVERAGE_RECORD_LENGTH / 3600, 1)

    @hybrid_property
    def is_closed(self):
        return self.posting is None

    def open_for_applicant(self, user_id):
        if not self.is_closed:
            application = \
                Application.query.filter(Application.user_id == user_id).first()
            if application and application.posting_id == self.posting.id:
                return True
        return False

    def get_user_number_of_recordings(self, user_id):
        user_ids = self.user_ids
        if user_id in user_ids:
            recordings = Recording.query.join(Recording.token).filter(
                Token.collection_id == self.id,
                Recording.user_id == user_id
            ).count()
            return recordings
        return False

    def get_users_number_of_recordings(self, user_ids):
        recordings = Recording.query.join(Recording.token).filter(
            Token.collection_id == self.id,
            Recording.user_id.in_(user_ids)
        ).with_entities(
            Recording.user_id, func.count(Recording.id)
        ).group_by(Recording.user_id).all()
        return recordings

    def get_user_time_estimate(self, user_id, num_recordings=None):
        num = num_recordings if num_recordings else self.get_user_number_of_recordings(user_id)
        return round(num * ESTIMATED_AVERAGE_RECORD_LENGTH / 3600, 1)

    @hybrid_property
    def configuration(self):
        if self.configuration_id is not None:
            return Configuration.query.get(self.configuration_id)
        return None

    @hybrid_property
    def posting(self):
        return Posting.query.filter(Posting.collection == self.id).first()

    @property
    def printable_id(self):
        return "T-{:04d}".format(self.id)

    @property
    def mos_url(self):
        return url_for('mos.mos_collection', id=self.id)
    
    @property
    def number_of_users(self):
        if not self.is_multi_speaker:
            return 1
        else:
            return len(self.user_ids)
    
    @property
    def number_of_recordings(self):
        recordings = Recording.query.join(Recording.token).filter(
            Token.collection_id == self.id
        ).count()
        return recordings

    @property
    def user_ids(self):
        if not self.is_multi_speaker:
            if self.has_assigned_user():
                return [self.assigned_user_id]
            else:
                return []
        else:
            user_ids = Recording.query.join(Recording.token).filter(
                Token.collection_id == self.id,
                Token.num_recordings > 0
            ).with_entities(Recording.user_id).distinct(Recording.user_id).all()
            return list(set(row[0] for row in user_ids))

    @property
    def users(self):
        user_ids = self.user_ids
        users = []
        if len(user_ids) == 0:
            return []
        for u in user_ids:
            users.append(User.query.get(u))
        return users
            





class Configuration(BaseModel, db.Model):
    __tablename__ = 'Configuration'

    id = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        autoincrement=True)
    name = db.Column(db.String)
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())
    is_default = db.Column(
        db.Boolean,
        default=False)
    # general configuration
    session_sz = db.Column(
        db.Integer,
        default=50)
    live_transcribe = db.Column(
        db.Boolean,
        default=True)
    visualize_mic = db.Column(
        db.Boolean,
        default=True)
    auto_trim = db.Column(
        db.Boolean,
        default=True)
    analyze_sound = db.Column(
        db.Boolean,
        default=True)
    # recording configuration
    auto_gain_control = db.Column(
        db.Boolean,
        default=False)
    noise_suppression = db.Column(
        db.Boolean,
        default=False)
    channel_count = db.Column(
        db.Integer,
        default=1)
    sample_rate = db.Column(
        db.Integer,
        default=48000)
    sample_size = db.Column(
        db.Integer,
        default=16)

    # MediaRecorder configuration
    blob_slice = db.Column(
        db.Integer,
        default=10)
    audio_codec = db.Column(
        db.String,
        default='pcm')

    # Video configuration
    video_w = db.Column(
        db.Integer,
        default=1280)
    video_h = db.Column(
        db.Integer,
        default=720)
    video_codec = db.Column(
        db.String,
        default='vp8')
    has_video = db.Column(
        db.Boolean,
        default=False)

    # Other
    trim_threshold = db.Column(
        db.Float,
        default=40)
    too_low_threshold = db.Column(
        db.Float,
        default=-15)
    too_high_threshold = db.Column(
        db.Float,
        default=-4.5)
    too_high_frames = db.Column(
        db.Integer,
        default=10)

    @hybrid_property
    def printable_name(self):
        if self.name:
            return self.name
        else:
            return "Conf-{:03d}".format(self.id)

    @hybrid_property
    def url(self):
        return url_for("configuration.conf_detail", id=self.id)

    @hybrid_property
    def delete_url(self):
        return url_for("configuration.delete_conf", id=self.id)

    @hybrid_property
    def edit_url(self):
        return url_for("configuration.edit_conf", id=self.id)

    @hybrid_property
    def codec(self):
        codec = self.audio_codec
        if self.has_video:
            codec = f'{self.video_codec}, {codec}'

    @hybrid_property
    def media_constraints(self):
        constraints = {'audio': {
            'channelCount': self.channel_count,
            'sampleSize': self.sample_size,
            'sampleRate': self.sample_rate,
            'noiseSuppression': self.noise_suppression,
            'autoGainControl': self.auto_gain_control
        }}
        if self.has_video:
            constraints['video'] = {
                'width': self.video_w,
                'height': self.video_h}
        return constraints

    @hybrid_property
    def mime_type(self):
        return f'{"video" if self.has_video else "audio"}/webm; codecs=' +\
                 f'"{"vp8, " if self.has_video else ""}pcm"'

    @hybrid_property
    def json(self):
        return json.dumps({
            'has_video': self.has_video,
            'live_transcribe': self.live_transcribe,
            'visualize_mic': self.visualize_mic,
            'analyze_sound': self.analyze_sound,
            'auto_trim': self.auto_trim,
            'media_constraints': self.media_constraints,
            'mime_type': self.mime_type,
            'codec': self.codec,
            'blob_slice': self.blob_slice,
            'trim_threshold': self.trim_threshold,
            'low_threshold': self.too_low_threshold,
            'high_threshold': self.too_high_threshold,
            'high_frames': self.too_high_frames})


class Token(BaseModel, db.Model):
    __tablename__ = 'Token'

    def __init__(
        self,
        text,
        original_fname,
        collection_id,
        score: float = -1,
        pron: str = None,
        source: str = None
    ):
        self.text = text
        self.original_fname = original_fname
        self.collection_id = collection_id
        self.marked_as_bad = False
        self.score = score
        if pron is not None:
            self.pron = pron
        if source is not None:
            self.source = source

    id = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        autoincrement=True)
    text = db.Column(db.String)
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())

    original_fname = db.Column(
        db.String,
        default='Unknown')
    collection_id = db.Column(
        db.Integer,
        db.ForeignKey('Collection.id'))
    fname = db.Column(db.String)
    path = db.Column(db.String)
    marked_as_bad = db.Column(
        db.Boolean,
        default=False)
    num_recordings = db.Column(
        db.Integer,
        default=0)
    pron = db.Column(db.String)
    score = db.Column(
        db.Float,
        default=-1)
    source = db.Column(db.String)
    recordings = db.relationship(
        "Recording",
        lazy='joined',
        backref='token')

    def get_url(self):
        return url_for('token.token_detail', id=self.id)

    def get_record_url(self):
        return url_for('token.record_single', tok_id=self.id)

    @hybrid_property
    def mark_bad_url(self):
        return url_for('token.toggle_token_bad', id=self.id)

    def get_path(self):
        return self.path

    def get_fname(self):
        return self.fname

    @hybrid_property
    def length(self):
        return len(self.text)

    def short_text(self, limit=20):
        if self.length < limit:
            return self.text
        else:
            return f'{self.text[:limit]}...'

    def save_to_disk(self):
        self.set_path()
        f = open(self.path, 'w', encoding='utf-8')
        f.write(self.text)
        f.close()

    @hybrid_property
    def pron_list(self):
        return self.pron[1:-1].split('\t')

    def set_path(self):
        self.fname = secure_filename("{}_{:09d}.token".format(
            os.path.splitext(self.original_fname)[0], self.id))
        self.path = os.path.join(
            app.config['TOKEN_DIR'], str(self.collection_id), self.fname)

    def get_configured_path(self):
        '''
        Get the path the program believes the token should be stored at
        w.r.t. the current TOKEN_DIR environment variable
        '''
        path = os.path.join(
            app.config['TOKEN_DIR'], str(self.collection_id), self.fname)
        return path

    def get_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'file_id': self.get_file_id(),
            'url': self.get_url()}

    def get_file_id(self):
        return os.path.splitext(self.fname)[0]

    def get_printable_id(self):
        return "T-{:09d}".format(self.id)

    def get_directory(self):
        return os.path.dirname(self.path)

    def get_download_url(self):
        return url_for('token.download_token', id=self.id)

    @hybrid_property
    def delete_url(self):
        return url_for('token.delete_token', id=self.id)

    def update_numbers(self):
        self.num_recordings = Recording.query.filter(
            Recording.token_id == self.id).count()

    def get_printable_score(self):
        return round(self.score, 3)

    @hybrid_property
    def collection(self):
        return Collection.query.get(self.collection_id)

    def is_recorded_by_user(self, user_id):
        for r in self.recordings:
            if r.user_id == user_id:
                return True
        return False

    def recorded_by_how_many_users(self, user_ids):
        recorded = []
        for u in user_ids:
            if self.is_recorded_by_user(u):
                if u not in recorded:
                    recorded.append(u)
        return len(recorded)


class CustomToken(BaseModel, db.Model):
    __tablename__ = 'CustomToken'

    def __init__(
            self, text, original_fname, copied_token=False,
            pron="Óþekkt", score=None, source="Óþekkt"):
        self.text = text
        self.original_fname = original_fname
        self.marked_as_bad = False
        self.copied_token = copied_token
        self.pron = pron
        self.score = score
        if not copied_token:
            self.source = "Upphleðsla"
        else:
            self.source = source

    def get_url(self):
        return url_for('mos.custom_token', id=self.id)

    def get_path(self):
        return self.path

    def get_fname(self):
        return self.fname

    @hybrid_property
    def length(self):
        return len(self.text)

    def short_text(self, limit=20):
        if self.length < limit:
            return self.text
        else:
            return f'{self.text[:limit]}...'

    def save_to_disk(self):
        self.set_path()
        f = open(self.path, 'w', encoding='utf-8')
        f.write(self.text)
        f.close()

    def set_path(self):
        self.fname = secure_filename("{}_u{:09d}.token".format(
            os.path.splitext(self.original_fname)[0], self.id))
        self.path = os.path.join(
            app.config['CUSTOM_TOKEN_DIR'], str(self.mos_id), self.fname)

    def get_configured_path(self):
        '''
        Get the path the program believes the token should be stored at
        w.r.t. the current TOKEN_DIR environment variable
        '''
        if self.copied_token:
            path = os.path.join(
                app.config['TOKEN_DIR'], str(self.collection_id), self.fname)
            return path
        path = os.path.join(
            app.config['CUSTOM_TOKEN_DIR'], str(self.mos_id), self.fname)
        return path

    def get_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'file_id': self.get_file_id(),
            'url': self.get_url()}

    def get_file_id(self):
        return os.path.splitext(self.fname)[0]

    def get_printable_id(self):
        return "U-{:09d}".format(self.id)

    def get_directory(self):
        return os.path.dirname(self.path)

    def get_download_url(self):
        return url_for('mos.download_custom_token', id=self.id)

    def copyToken(self, token):
        self.fname = token.fname
        self.path = token.path
        self.pron = token.pron
        self.score = token.score
        self.source = token.source

    @property
    def custom_recording(self):
        return MosInstance.query.get(self.mos_instance_id).custom_recording

    @property
    def mos_id(self):
        return self.mosInstance.mos.id

    @hybrid_property
    def mos(self):
        return self.mosInstance.mos

    id = db.Column(
        db.Integer, primary_key=True, nullable=False, autoincrement=True)
    text = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    mos_instance_id = db.Column(db.Integer, db.ForeignKey("MosInstance.id"))
    original_fname = db.Column(db.String, default='Unknown')
    copied_token = db.Column(db.Boolean, default=False)
    fname = db.Column(db.String)
    path = db.Column(db.String)
    marked_as_bad = db.Column(db.Boolean, default=False)
    pron = db.Column(db.String)
    score = db.Column(db.Float, default=-1)
    source = db.Column(db.String)


class Rating(BaseModel, db.Model):
    __tablename__ = 'Rating'

    def __init__(self, recording_id, user_id, value):
        self.recording_id = recording_id
        self.user_id = user_id
        self.value = value

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True)
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())
    recording_id = db.Column(
        db.Integer,
        db.ForeignKey('Recording.id'))
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    value = db.Column(
        db.Boolean,
        default=False)


class Recording(BaseModel, db.Model):
    __tablename__ = 'Recording'

    def __init__(
        self,
        token_id,
        original_fname,
        user_id,
        bit_depth=None,
        session_id=None,
        has_video=False
    ):
        self.token_id = token_id
        self.original_fname = original_fname
        self.user_id = user_id
        self.marked_as_bad = False
        if bit_depth is not None:
            self.bit_depth = bit_depth
        if session_id is not None:
            self.session_id = session_id
        self.has_video = has_video

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True)
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())
    original_fname = db.Column(
        db.String, default='Unknown')

    token_id = db.Column(
        db.Integer,
        db.ForeignKey('Token.id'))
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey('Session.id'))
    priority_session_id = db.Column(
        db.Integer,
        db.ForeignKey('PrioritySession.id'))
    sr = db.Column(db.Integer)
    num_channels = db.Column(
        db.Integer,
        default=1)
    latency = db.Column(db.Float)
    auto_gain_control = db.Column(db.Boolean)
    echo_cancellation = db.Column(db.Boolean)
    noise_suppression = db.Column(db.Boolean)
    analysis = db.Column(db.String)
    duration = db.Column(db.Float)
    bit_depth = db.Column(db.Integer)
    transcription = db.Column(db.String)
    fname = db.Column(db.String)
    file_id = db.Column(db.String)
    path = db.Column(db.String)
    wav_path = db.Column(db.String)
    start = db.Column(db.Float)
    end = db.Column(db.Float)
    marked_as_bad = db.Column(
        db.Boolean,
        default=False)
    has_video = db.Column(
        db.Boolean,
        default=False)
    verifications = db.relationship(
        "Verification",
        lazy='select',
        backref='recording',
        cascade='all, delete, delete-orphan')
    is_verified = db.Column(
        db.Boolean,
        default=False)
    is_secondarily_verified = db.Column(
        db.Boolean,
        default=False)
    social_posts = db.relationship(
        "SocialPost", lazy="joined", back_populates='recording',
        cascade='all, delete, delete-orphan')

    def set_session_id(self, session_id):
        self.session_id = session_id

    def _set_wave_params(self, recorder_settings):
        self.sr = recorder_settings['sampleRate']
        self.bit_depth = recorder_settings['sampleSize']
        self.num_channels = recorder_settings['channelCount']
        self.latency = recorder_settings['latency']
        self.auto_gain_control = recorder_settings['autoGainControl']
        self.echo_cancellation = recorder_settings['echoCancellation']
        self.noise_suppression = recorder_settings['noiseSuppression']
        with contextlib.closing(wave.open(self.wav_path, 'r')) as f:
            self.duration = f.getnframes()/float(f.getframerate())

    def get_url(self):
        return url_for('recording.recording_detail', id=self.id)

    def get_fname(self):
        return self.fname

    def get_download_url(self):
        return url_for('recording.download_recording', id=self.id)

    def get_toggle_bad_url(self):
        return url_for('recording.toggle_recording_bad', id=self.id)

    def get_toggle_bad_ajax(self):
        return url_for('recording.toggle_recording_bad_ajax', id=self.id)

    def get_directory(self):
        return os.path.dirname(self.path)

    def get_path(self):
        return self.path

    def get_wav_path(self):
        return self.wav_path

    def get_zip_fname(self):
        if self.wav_path is not None:
            return os.path.split(self.wav_path)[1]
        return self.fname

    def get_zip_path(self):
        if self.wav_path is not None:
            return self.wav_path
        return self.path

    def save_to_disk(self, file_obj):
        '''
        Can only be called after being committed
        since we need self.id
        '''
        file_obj.filename = self.fname
        file_obj.save(self.path)

    def _save_wav_to_disk(self):
        # there is no ffmpeg on Eyra
        if os.getenv('SEMI_PROD', False) or \
                os.getenv('FLASK_ENV', 'development') == 'production':
            subprocess.call(['avconv', '-i', self.path, self.wav_path])
        else:
            subprocess.call(['ffmpeg', '-i', self.path, self.wav_path])

    def add_file_obj(self, obj, recorder_settings):
        '''
        performs, in order, :
        * self.set_path()
        * self.save_to_disk(obj)
        * self.set_wave_params()
        '''
        self._set_path()
        self.save_to_disk(obj)
        self._save_wav_to_disk()
        self._set_wave_params(recorder_settings)

    def _set_path(self):
        self.file_id = '{}_r{:09d}_t{:09d}'.format(
            os.path.splitext(self.original_fname)[0], self.id, self.token_id)
        self.fname = secure_filename(f'{self.file_id}.webm')
        self.path = os.path.join(
            app.config['VIDEO_DIR'] if self.has_video
            else app.config['RECORD_DIR'],
            str(self.token.collection_id), self.fname)
        self.wav_path = os.path.join(
            app.config['WAV_AUDIO_DIR'],
            str(self.token.collection_id),
            secure_filename(f'{self.file_id}.wav'))

    def get_configured_path(self):
        '''
        Get the path the program believes the token should be stored at
        w.r.t. the current TOKEN_DIR environment variable
        '''
        return os.path.join(
            app.config['RECORD_DIR'],
            str(self.token.collection_id),
            self.fname)

    def get_file_id(self):
        if self.fname is not None:
            return os.path.splitext(self.fname)[0]
        else:
            # not registered, (using) primary key
            return "nrpk_{:09d}".format(self.id)

    def get_user(self):
        return User.query.get(self.user_id)

    def get_token(self):
        if self.token_id is not None:
            return Token.query.get(self.token_id)
        return None
    
    @property
    def token_text(self):
        return self.get_token().text

    def get_printable_id(self):
        return "R-{:09d}".format(self.id)

    def get_printable_duration(self):
        if self.duration is not None:
            return "{:2.2f}s".format(self.duration)
        else:
            return "n/a"

    def get_printable_transcription(self):
        if self.transcription is not None and len(self.transcription) > 0:
            return self.transcription
        else:
            return "n/a"

    def get_dict(self):
        return {'id': self.id, 'token': self.token.get_dict()}

    def get_collection_id(self):
        return Token.query.get(self.token_id).collection_id

    def set_trim(self, start, end):
        self.start = start
        self.end = end

    @property
    def has_trim(self):
        return self.start is not None and self.end is not None
    
    @property
    def collection_id(self):
        return self.token.collection_id

    def reset_trim(self):
        self.set_trim(None, None)


class CustomRecording(BaseModel, db.Model):
    __tablename__ = 'CustomRecording'

    def __init__(self, copied_recording=False):
        self.copied_recording = copied_recording

    def get_fname(self):
        return self.fname

    def get_download_url(self):
        return url_for('mos.download_custom_recording', id=self.id)

    def get_directory(self):
        return os.path.dirname(self.path)

    def get_path(self):
        return self.path

    def get_wav_path(self):
        return self.wav_path

    def get_zip_fname(self):
        if self.wav_path is not None:
            return os.path.split(self.wav_path)[1]
        return self.fname

    def get_zip_path(self):
        if self.wav_path is not None:
            return self.wav_path
        return self.path

    def copyRecording(self, recording):
        self.original_fname = recording.original_fname
        self.user_id = recording.user_id
        self.duration = recording.duration
        self.fname = recording.fname
        self.file_id = recording.file_id
        self.path = recording.path
        self.wav_path = recording.wav_path

    def get_configured_path(self):
        '''
        Get the path the program believes the token should be stored at
        w.r.t. the current TOKEN_DIR environment variable
        '''
        if self.copied_recording:
            path = os.path.join(
                app.config['RECORD_DIR'],
                str(self.token.collection_id), self.fname)
            return path
        path = os.path.join(
            app.config['CUSTOM_RECORDING_DIR'],
            str(self.token.collection_id), self.fname)
        return path

    def get_file_id(self):
        if self.fname is not None:
            return os.path.splitext(self.fname)[0]
        else:
            # not registered, (using) primary key
            return "nrpk_{:09d}".format(self.id)

    def get_user(self):
        return User.query.get(self.user_id)

    def get_printable_id(self):
        return "S-{:09d}".format(self.id)

    def get_printable_duration(self):
        if self.duration is not None:
            return "{:2.2f}s".format(self.duration)
        else:
            return "n/a"

    def _set_path(self):
        # TODO: deal with file endings
        self.file_id = '{}_s{:09d}_m{:09d}'.format(
            os.path.splitext(self.original_fname)[0], self.id, self.token_id)
        self.fname = secure_filename(f'{self.file_id}.webm')
        self.path = os.path.join(
            app.config['CUSTOM_RECORDING_DIR'],
            str(self.mosInstance.id), self.fname)
        self.wav_path = os.path.join(
            app.config['WAV_CUSTOM_AUDIO_DIR'],
            str(self.mosInstance.id),
            secure_filename(f'{self.file_id}.wav'))

    def get_dict(self):
        if self.custom_token is not None:
            return {'id': self.id, 'token': self.custom_token.get_dict()}
        else:
            return {'id': self.id, 'text': self.text, 'file_id': '', 'url': ''}

    @property
    def custom_token(self):
        return self.mosInstance.custom_token

    @property
    def text(self):
        return self.custom_token.text

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    original_fname = db.Column(db.String, default='Unknown')
    mos_instance_id = db.Column(db.Integer, db.ForeignKey("MosInstance.id"))

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)

    duration = db.Column(db.Float)
    copied_recording = db.Column(db.Boolean, default=False)
    fname = db.Column(db.String)
    file_id = db.Column(db.String)
    path = db.Column(db.String)
    wav_path = db.Column(db.String)


class Session(BaseModel, db.Model):
    __tablename__ = 'Session'

    def __init__(
        self,
        user_id,
        collection_id,
        manager_id,
        duration=None,
        has_video=False,
        is_dev=False
    ):
        self.user_id = user_id
        self.manager_id = manager_id
        self.collection_id = collection_id
        self.has_video = has_video
        self.is_dev = is_dev
        if duration is not None:
            self.duration = duration

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    manager_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    collection_id = db.Column(
        db.Integer,
        db.ForeignKey('Collection.id'))
    duration = db.Column(db.Float)
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())
    has_video = db.Column(
        db.Boolean,
        default=False)
    recordings = db.relationship(
        "Recording",
        lazy='joined',
        backref='session',
        cascade='all, delete, delete-orphan')

    is_secondarily_verified = db.Column(
        db.Boolean,
        default=False)
    is_verified = db.Column(
        db.Boolean,
        default=False)
    has_priority = db.Column(
        db.Boolean,
        default=False)
    verified_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    secondarily_verified_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    is_dev = db.Column(
        db.Boolean,
        default=False)

    def get_printable_id(self):
        return "S-{:06d}".format(self.id)

    def get_url(self):
        return url_for('session.rec_session_detail', id=self.id)

    def get_printable_duration(self):
        if self.duration is not None:
            return str(timedelta(seconds=int(self.duration)))
        else:
            return 'n/a'

    @property
    def verifier(self):
        verifier = None
        if self.verified_by:
            verifier = User.query.get(self.verified_by)
        return verifier

    @property
    def collection(self):
        collection = None
        if self.collection_id:
            collection = Collection.query.get(self.collection_id)
        return collection

    @hybrid_property
    def get_start_time(self):
        if self.duration is not None:
            return self.created_at - timedelta(seconds=int(self.duration))
        return None

    @hybrid_property
    def num_recordings(self):
        return len(self.recordings)

    @hybrid_property
    def get_user(self):
        if self.user_id is not None:
            return User.query.get(self.user_id)
        return "n/a"

    @hybrid_property
    def get_manager(self):
        if self.manager_id is not None:
            return User.query.get(self.manager_id)
        return "n/a"


class PrioritySession(BaseModel, db.Model):
    __tablename__ = 'PrioritySession'

    def __init__(
        self,
        user_id,
        collection_id,
        manager_id,
        duration=None,
        has_video=False,
        is_dev=False
    ):
        self.user_id = user_id
        self.manager_id = manager_id
        self.collection_id = collection_id
        self.has_video = has_video
        self.is_dev = is_dev
        if duration is not None:
            self.duration = duration

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    manager_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    collection_id = db.Column(
        db.Integer,
        db.ForeignKey('Collection.id'))
    duration = db.Column(db.Float)
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())
    has_video = db.Column(
        db.Boolean,
        default=False)
    recordings = db.relationship(
        "Recording",
        lazy='joined',
        backref='prioritySession',
        cascade='all, delete, delete-orphan')

    is_secondarily_verified = db.Column(
        db.Boolean,
        default=False)
    is_verified = db.Column(
        db.Boolean,
        default=False)
    verified_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    secondarily_verified_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    is_dev = db.Column(
        db.Boolean,
        default=False)

    def get_printable_id(self):
        return "PS-{:06d}".format(self.id)

    def get_url(self):
        return url_for('session.rec_priority_session_detail', id=self.id)

    def get_printable_duration(self):
        if self.duration is not None:
            return str(timedelta(seconds=int(self.duration)))
        else:
            return 'n/a'

    @hybrid_property
    def get_start_time(self):
        if self.duration is not None:
            return self.created_at - timedelta(seconds=int(self.duration))
        return None

    @hybrid_property
    def num_recordings(self):
        return len(self.recordings)

    @hybrid_property
    def get_user(self):
        if self.user_id is not None:
            return User.query.get(self.user_id)
        return "n/a"

    @hybrid_property
    def get_manager(self):
        if self.manager_id is not None:
            return User.query.get(self.manager_id)
        return "n/a"


class Verification(BaseModel, db.Model):
    __tablename__ = 'Verification'

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True)
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())
    verified_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True)
    recording_id = db.Column(
        db.Integer,
        db.ForeignKey('Recording.id'))
    volume_is_low = db.Column(
        db.Boolean,
        default=False)
    volume_is_high = db.Column(
        db.Boolean,
        default=False)
    recording_has_glitch = db.Column(
        db.Boolean,
        default=False)
    recording_has_wrong_wording = db.Column(
        db.Boolean,
        default=False)
    comment = db.Column(db.String(255))
    is_secondary = db.Column(
        db.Boolean,
        default=False)
    trims = db.relationship(
        "Trim",
        lazy='select',
        backref='verification',
        cascade='all, delete, delete-orphan')

    @property
    def url(self):
        return url_for('verification.verification_detail', id=self.id)

    @property
    def printable_id(self):
        return "G-{:06d}".format(self.id)

    @property
    def recording(self):
        if self.recording_id is not None:
            return Recording.query.get(self.recording_id)
        return None

    @property
    def verifier(self):
        if self.verified_by is not None:
            return User.query.get(self.verified_by)
        return None

    @property
    def recording_is_good(self):
        return not any(
            [self.recording_has_glitch, self.recording_has_wrong_wording,
                self.volume_is_high, self.volume_is_low])

    def set_quality(self, quality_field_data):
        '''
        quality_field_data is a list of string values with
        the following correspondance::
        * 'high'   -> self.volume_is_high
        * 'low'    -> self.volume_is_low
        * 'wrong   -> self.has_wrong_wording
        * 'glitch' -> self.has_glitch
        '''
        for data in quality_field_data:
            if data == 'high':
                self.volume_is_high = True
            elif data == 'low':
                self.volume_is_low = True
            elif data == 'wrong':
                self.recording_has_wrong_wording = True
            elif data == 'glitch':
                self.recording_has_glitch = True
            elif data == 'glitch-outside':
                self.recording_has_glitch_outside_trimming = True

    @hybrid_property
    def dict(self):
        return {
            'volume_is_low': self.volume_is_low,
            'volume_is_high': self.volume_is_high,
            'recording_has_glitch': self.recording_has_glitch,
            'recording_has_wrong_wording': self.recording_has_wrong_wording,
            'comment': self.comment,
            'trims': [{'start': t.start, 'end': t.end} for t in self.trims]}

    def as_tsv_line(self):
        return "\t".join(map(str, [
            int(self.recording_id),
            int(self.volume_is_low),
            int(self.volume_is_high),
            int(self.recording_has_glitch),
            int(self.recording_has_wrong_wording),
            self.comment.replace("\n","\\n"),
        ]))


class Trim(BaseModel, db.Model):
    __tablename__ = 'Trim'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    start = db.Column(db.Float)
    end = db.Column(db.Float)
    index = db.Column(db.Integer)
    verification_id = db.Column(db.Integer, db.ForeignKey('Verification.id'))


roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True)
    uuid = db.Column(db.String)
    name = db.Column(db.String(255))
    email = db.Column(
        db.String(255),
        unique=True)
    password = db.Column(db.String(255))
    sex = db.Column(db.String(255))
    age = db.Column(db.Integer)
    dialect = db.Column(db.String(255))
    audio_setup = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())
    roles = db.relationship(
        'Role',
        secondary=roles_users,
        backref=db.backref('users', lazy='dynamic'))
    assigned_collections = db.relationship(
        "Collection",
        cascade='all, delete, delete-orphan')
    recordings = db.relationship("Recording")

    progression_id = db.Column(
        db.Integer,
        db.ForeignKey('verifier_progression.id'))
    social_posts = db.relationship(
        "SocialPost", lazy="joined", back_populates='user',
        cascade='all, delete, delete-orphan')

    @property
    def progression(self):
        if self.progression_id is not None:
            return VerifierProgression.query.get(self.progression_id)

    def get_url(self):
        return url_for('user.user_detail', id=self.id)

    def get_printable_name(self):
        if self.name is not None:
            return self.name
        else:
            return "Nafnlaus notandi"

    def is_admin(self):
        return self.has_role(ADMIN_ROLE_NAME)

    def is_verifier(self):
        return any(r.name == 'Greinir' for r in self.roles)

    def __str__(self):
        if type(self.name) != str:
            return str("User_{}".format(self.id))
        return self.name

    def get_meta(self):
        '''
        Returns a dictionary of values that are included in meta.json
        when downloading collections
        '''
        return {
            'id': self.id,
            'name': self.get_printable_name(),
            'email': self.email,
            'sex': self.sex,
            'age': self.age,
            'dialect': self.dialect}


progression_icon = db.Table(
    'progression_icon',
    db.Column(
        'progression_id',
        db.Integer(),
        db.ForeignKey('verifier_progression.id')),
    db.Column(
        'icon_id',
        db.Integer(),
        db.ForeignKey('verifier_icon.id')))


progression_title = db.Table(
    'progression_title',
    db.Column(
        'progression_id',
        db.Integer(),
        db.ForeignKey('verifier_progression.id')),
    db.Column(
        'title_id',
        db.Integer(),
        db.ForeignKey('verifier_title.id')))


progression_quote = db.Table(
    'progression_quote',
    db.Column(
        'progression_id',
        db.Integer(),
        db.ForeignKey('verifier_progression.id')),
    db.Column(
        'quote_id',
        db.Integer(),
        db.ForeignKey('verifier_quote.id')))


progression_font = db.Table(
    'progression_font',
    db.Column(
        'progression_id',
        db.Integer(),
        db.ForeignKey('verifier_progression.id')),
    db.Column(
        'font_id',
        db.Integer(),
        db.ForeignKey('verifier_font.id')))


progression_premium_item = db.Table(
    'progression_premium_item',
    db.Column(
        'progression_id', db.Integer(),
        db.ForeignKey('verifier_progression.id')),
    db.Column(
        'premium_item_id',
        db.Integer(), db.ForeignKey('premium_item.id')))


class VerifierProgression(BaseModel, db.Model):
    id = db.Column(
        db.Integer(),
        primary_key=True)

    num_verifies = db.Column(
        db.Integer(),
        default=0)
    num_session_verifies = db.Column(
        db.Integer(),
        default=0)
    num_invalid = db.Column(
        db.Integer(),
        default=0)
    num_streak_days = db.Column(
        db.Integer(),
        default=0)
    weekly_verifies = db.Column(
        db.Integer(),
        default=0)
    weekly_coin_price = db.Column(
        db.Integer(),
        default=0)
    weekly_experience_price = db.Column(
        db.Integer(),
        default=0)
    has_seen_weekly_prices = db.Column(
        db.Boolean(),
        default=False)
    last_spin = db.Column(db.DateTime)
    lobe_coins = db.Column(
        db.Integer(),
        default=0)
    experience = db.Column(
        db.Integer(),
        default=0)
    verification_level = db.Column(
        db.Integer(),
        default=0)
    spy_level = db.Column(
        db.Integer(),
        default=0)
    streak_level = db.Column(
        db.Integer(),
        default=0)
    equipped_icon_id = db.Column(
        db.Integer,
        db.ForeignKey('verifier_icon.id'))
    equipped_title_id = db.Column(
        db.Integer,
        db.ForeignKey('verifier_title.id'))
    equipped_quote_id = db.Column(
        db.Integer,
        db.ForeignKey('verifier_quote.id'))
    equipped_font_id = db.Column(
        db.Integer,
        db.ForeignKey('verifier_font.id'))
    owned_icons = db.relationship(
        "VerifierIcon",
        secondary=progression_icon)
    owned_titles = db.relationship(
        "VerifierTitle",
        secondary=progression_title)
    owned_quotes = db.relationship(
        "VerifierQuote",
        secondary=progression_quote)
    owned_fonts = db.relationship(
        "VerifierFont",
        secondary=progression_font)
    fire_sale = db.Column(
        db.Boolean,
        default=False)
    fire_sale_discount = db.Column(
        db.Float,
        default=0.0)

    def owns_icon(self, icon):
        return any([i.id == icon.id for i in self.owned_icons])

    def is_icon_equipped(self, icon):
        return self.equipped_icon_id == icon.id

    def owns_title(self, title):
        return any([t.id == title.id for t in self.owned_titles])

    def is_title_equipped(self, title):
        return self.equipped_title_id == title.id

    def owns_quote(self, quote):
        return any([q.id == quote.id for q in self.owned_quotes])

    def is_quote_equipped(self, quote):
        return self.equipped_quote_id == quote.id

    def owns_font(self, font):
        return any([f.id == font.id for f in self.owned_fonts])

    def is_font_equipped(self, font):
        return self.equipped_font_id == font.id

    def owns_premium_item(self, item):
        return any([i.id == item.id for i in self.owned_premium_items])

    @property
    def equipped_icon(self):
        if self.equipped_icon_id is not None:
            return VerifierIcon.query.get(self.equipped_icon_id)

    @property
    def equipped_title(self):
        if self.equipped_title_id is not None:
            return VerifierTitle.query.get(self.equipped_title_id)

    @property
    def equipped_quote(self):
        if self.equipped_quote_id is not None:
            return VerifierQuote.query.get(self.equipped_quote_id)

    @property
    def equipped_font(self):
        if self.equipped_font_id is not None:
            return VerifierFont.query.get(self.equipped_font_id)

    @property
    def premium_wheel(self):
        return any([i.wheel_modifier for i in self.owned_premium_items])

    def equip_random_icon(self):
        self.equipped_icon_id =\
            random.choice([i.id for i in self.owned_icons])

    def equip_random_title(self):
        self.equipped_title_id =\
            random.choice([t.id for t in self.owned_titles])

    def equip_random_quote(self):
        self.equipped_quote_id =\
            random.choice([q.id for q in self.owned_quotes])


class VerifierIcon(BaseModel, db.Model):
    id = db.Column(
        db.Integer(),
        primary_key=True)
    fa_id = db.Column(
        db.String(),
        info={
            'validators': [validators.InputRequired()],
            'label': 'Merkisklassar',
            'description': 'Til dæmis: fab fa-apple'})
    title = db.Column(
        db.String(64),
        info={
            'validators': [validators.InputRequired()],
            'label': 'Titill'})
    description = db.Column(
        db.String(255),
        info={
            'validators': [validators.InputRequired()],
            'label': 'Stutt lýsing'})
    price = db.Column(
        db.Integer(),
        default=0,
        info={
            'label': 'Verð', 'min': 0, 'max': 1000})
    color = db.Column(
        db.String(),
        info={
            'label': 'Litur á merki',
            'form_field_class': ColorField,
            'validators': [validators.InputRequired()]})
    rarity = db.Column(
        db.Integer(),
        info={
            'validators': [validators.InputRequired()],
            'label': 'Tegund',
            'choices': [
                (0, 'Basic'),
                (1, 'Rare'),
                (2, 'Epic'),
                (3, 'Legendary')]})
    for_sale = db.Column(db.Boolean(), default=True, info={'label': 'Til sölu'})

    @property
    def edit_url(self):
        return url_for('shop.icon_edit', id=self.id)


class VerifierTitle(BaseModel, db.Model):
    id = db.Column(
        db.Integer(),
        primary_key=True)
    title = db.Column(
        db.String(64),
        info={
            'label': 'Titillinn'})
    description = db.Column(
        db.String(255),
        info={
            'label': 'Stutt lýsing'})
    price = db.Column(
        db.Integer(),
        default=0,
        info={
            'label': 'Verð'})
    rarity = db.Column(
        db.Integer(),
        info={
            'validators': [validators.InputRequired()],
            'label': 'Tegund',
            'choices': [
                (0, 'Basic'),
                (1, 'Rare'),
                (2, 'Epic'),
                (3, 'Legendary')]})
    for_sale = db.Column(db.Boolean(), default=True, info={'label': 'Til sölu'})

    @property
    def edit_url(self):
        return url_for('shop.title_edit', id=self.id)


class VerifierQuote(BaseModel, db.Model):
    id = db.Column(
        db.Integer(),
        primary_key=True)
    quote = db.Column(
        db.String(255),
        info={
            'label': 'Slagorðið'})
    price = db.Column(
        db.Integer(),
        default=0,
        info={
            'label': 'Verð'})
    rarity = db.Column(
        db.Integer(),
        info={
            'validators': [validators.InputRequired()],
            'label': 'Tegund',
            'choices': [
                (0, 'Basic'),
                (1, 'Rare'),
                (2, 'Epic'),
                (3, 'Legendary')]})
    for_sale = db.Column(db.Boolean(), default=True, info={'label': 'Til sölu'})

    @property
    def edit_url(self):
        return url_for('shop.quote_edit', id=self.id)


class VerifierFont(BaseModel, db.Model):
    id = db.Column(
        db.Integer(),
        primary_key=True)
    font_family = db.Column(
        db.String(),
        info={
            'label': 'Font fjölskylda',
            'description': "Til dæmis Megrim"})
    font_type = db.Column(
        db.String(),
        info={
            'label': 'Font týpa',
            'description': "Til dæmis cursive"})
    href = db.Column(
        db.String(),
        info={
            'label': 'Linkur á font CSS'})
    title = db.Column(
        db.String(255),
        info={
            'label': 'Titill'})
    description = db.Column(
        db.String(255),
        info={
            'label': 'Lýsing'})
    price = db.Column(
        db.Integer(),
        default=0,
        info={
            'label': 'Verð (gimsteinar)'})
    rarity = db.Column(
        db.Integer(),
        info={
            'validators': [validators.InputRequired()],
            'label': 'Tegund',
            'choices': [
                (0, 'Basic'),
                (1, 'Rare'),
                (2, 'Epic'),
                (3, 'Legendary')]})
    for_sale = db.Column(db.Boolean(), default=True, info={'label': 'Til sölu'})

    @property
    def edit_url(self):
        return url_for('shop.font_edit', id=self.id)


class PremiumItem(BaseModel, db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    title = db.Column(db.String(255), info={
        'label': 'Titill'})
    description = db.Column(db.String(255), info={
        'label': 'Lýsing'})
    coin_price = db.Column(db.Integer(), default=0, info={
        'label': 'Verð (aurar)'})
    experience_price = db.Column(db.Integer(), default=0, info={
        'label': 'Verð (demantar)'})
    num_available = db.Column(db.Integer(), default=0, info={
        'label': 'Fjöldi í boði'})
    wheel_modifier = db.Column(db.Boolean(), default=False, info={
        'label': 'Breyta þessi verðlaun lukkuhjólinu?'})
    for_sale = db.Column(db.Boolean(), default=True, info={'label': 'Til sölu'})

    @property
    def edit_url(self):
        return url_for('premium_item_edit', id=self.id)


class Posting(BaseModel, db.Model):
    __tablename__ = 'Posting'

    id = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        autoincrement=True)
    name = db.Column(db.String)
    ad_text = db.Column(db.String)
    active = db.Column(db.Boolean, default=True)
    dev = db.Column(db.Boolean, default=False)
    utterances = db.Column(db.String)
    collection = db.Column(
        db.Integer,
        db.ForeignKey("Collection.id"))
    uuid = db.Column(
        db.String,
        default=str(uuid.uuid4()))
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())
    applications = db.relationship(
        "Application",
        lazy="select",
        backref='posting',
        cascade='all, delete, delete-orphan')

    def get_url(self):
        return url_for("application.posting_detail", id=self.id)

    def get_apply_url(self):
        return url_for("application.new_application", posting_uuid=self.uuid)

    @hybrid_property
    def delete_url(self):
        return url_for("application.delete_posting", id=self.id)

    def unique_applications(self):
        apps = Application.query.filter(Application.posting_id == self.id).order_by(Application.created_at.asc())
        unique_apps = dict((app.email, app) for app in apps)
        return list(unique_apps.values())

    def unique_with_recordings(self):
        return [app for app in self.unique_applications() if len(app.recordings().all()) > 0]

    def statistics(self):
        return self.statistics_for_applications(self.unique_with_recordings())

    @staticmethod
    def statistics_for_applications(applications):
        sexes = defaultdict(list)
        for application in applications:
            sexes[application.sex].append(application)

        traces = []
        for sex, apps in sexes.items():
            age_counter = Counter(app.age for app in apps).most_common()
            age_counter.sort(key=lambda i: i[0])
            age, age_count = zip(*age_counter)
            trace = {
                "name": sex,
                "x": list(age),
                "y": list(age_count),
            }
            traces.append(trace)

        info = {
            "total": len(applications),
            "sex": Counter(app.sex for app in applications).most_common(),
            "traces": traces,
        }
        return info


class Application(BaseModel, db.Model):
    __tablename__ = 'Application'

    id = db.Column(
        db.Integer,
        primary_key=True,
        nullable=False,
        autoincrement=True)
    name = db.Column(db.String)
    sex = db.Column(db.String)
    age = db.Column(db.Integer)
    voice = db.Column(db.String)
    email = db.Column(db.String)
    phone = db.Column(db.String)
    terms_agreement = db.Column(
        db.Boolean,
        default=False)
    uuid = db.Column(
        db.String,
        default=str(uuid.uuid4()))
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"))
    posting_id = db.Column(
        db.Integer,
        db.ForeignKey("Posting.id"))
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp())

    def get_url(self):
        return url_for("application.application_detail", id=self.id)

    @hybrid_property
    def delete_url(self):
        return url_for("application.delete_application", id=self.id)

    @hybrid_property
    def user_url(self):
        return url_for("user.user_detail", id=self.user_id)

    def recordings(self):
        return Recording.query.filter(
            Recording.user_id == self.user_id)


class Mos(BaseModel, db.Model):
    __tablename__ = 'Mos'
    id = db.Column(
        db.Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    uuid = db.Column(db.String)
    question = db.Column(db.String)
    form_text = db.Column(db.String)
    help_text = db.Column(db.String)
    done_text = db.Column(db.String)
    use_latin_square = db.Column(db.Boolean, default=False)
    show_text_in_test = db.Column(db.Boolean, default=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('Collection.id'))
    collection = db.relationship(Collection, info={
        'label': 'Söfnun',
    })
    num_samples = db.Column(db.Integer, default=0, info={
        'label': 'Fjöldi setninga'
    })
    mos_objects = db.relationship(
        "MosInstance", lazy='joined', backref="mos",
        cascade='all, delete, delete-orphan')
    num_participants = db.Column(db.Integer, default=0)

    def getAllRatings(self):
        ratings = []
        for m in self.mos_objects:
            for r in m.ratings:
                ratings.append(r)
        return ratings

    def getAllUserRatings(self, user_id):
        ratings = []
        for m in self.mos_objects:
            for r in m.ratings:
                if user_id == r.user_id:
                    ratings.append(r)
        return ratings

    def getAllUsers(self):
        ratings = self.getAllRatings()
        user_ids = []
        for i in ratings:
            user_ids.append(i.user_id)
        user_ids = list(set(user_ids))
        return user_ids

    def getAllVoiceIndices(self):
        voices = set()
        for sample in self.mos_objects:
            voices.add(sample.voice_idx)
        return voices

    def getAllUtteranceIndices(self):
        utterances = set()
        for sample in self.mos_objects:
            utterances.add(sample.utterance_idx)
        return utterances

    def getResultsByVoice(self):
        voice_ratings = defaultdict(list)
        for obj in self.mos_objects:
            for rating in obj.ratings:
                voice_ratings["No ID" if obj.voice_idx is None else obj.voice_idx].append(rating)
        return voice_ratings

    def getResultData(self):
        mos_data = [[
            "instance",
            "question",
            "utterance_idx",
            "voice_idx",
            "is_synth",
            "user",
            "name",
            "age",
            "audio_setup",
            "rating",
            "placement",
        ]]
        for obj in self.mos_objects:
            for rating in obj.ratings:
                mos_data.append([
                    obj.id,
                    obj.question,
                    obj.utterance_idx,
                    obj.voice_idx,
                    int(obj.is_synth),
                    rating.user_id,
                    rating.user.name,
                    rating.user.age,
                    rating.user.audio_setup,
                    rating.rating,
                    rating.placement
                ])
        return mos_data


    def getConfigurations(self):
        """
        Generates a Latin square of sentence-system combinations 
        based on the number of voices/systems being tested.

        Input: none
        Output: an array of arrays, each containing MosInstance objects, wherein each 
        MosInstance object refers to a particular voice rendering a particular utterance.
        This results in a balanced test, which should minimize the effect of each sentence
        and the carry-over effect of speakers on each other.
        """
        voices = list(self.getAllVoiceIndices())
        utterances = list(self.getAllUtteranceIndices())
        num_voices = len(list(voices))
        latinSquareRows = balanced_latin_squares(num_voices)
        configurations = []
        for row in latinSquareRows:
            configuration = []
            while len(configuration) < len(list(utterances)):
                configuration.extend([x for x in self.mos_objects if (
                        x.voice_idx == row[len(configuration) % len(row)]
                        and
                        x.utterance_idx == utterances[len(configuration)]
                    )])
            configurations.append(configuration)
        return configurations

    @property
    def custom_tokens(self):
        tokens = []
        for m in self.mos_objects:
            tokens.append(m.custom_token)
        return tokens

    @property
    def url(self):
        return url_for('mos.mos_detail', id=self.id)

    @property
    def printable_id(self):
        return "MOS-{:04d}".format(self.id)

    @property
    def edit_url(self):
        return url_for('mos.mos_edit', id=self.id)

    @property
    def number_selected(self):
        return sum(r.selected == True for r in self.mos_objects)

    def add_participant(self, user):
        if not self.num_participants:
            self.num_participants = 1
        else:
            self.num_participants += 1


class MosInstance(BaseModel, db.Model):
    __tablename__ = 'MosInstance'
    id = db.Column(
        db.Integer, primary_key=True, nullable=False, autoincrement=True)
    mos_id = db.Column(db.Integer, db.ForeignKey('Mos.id'))
    custom_token = db.relationship(
        "CustomToken", lazy="joined",
        backref=db.backref("mosInstance", uselist=False), uselist=False,
        cascade='all, delete, delete-orphan')
    custom_recording = db.relationship(
        "CustomRecording", lazy="joined",
        backref=db.backref("mosInstance", uselist=False), uselist=False,
        cascade='all, delete, delete-orphan')
    ratings = db.relationship(
        "MosRating", lazy="joined", backref='mosInstance',
        cascade='all, delete, delete-orphan')
    is_synth = db.Column(db.Boolean, default=False)
    voice_idx = db.Column(db.Integer, default=0)
    utterance_idx = db.Column(db.Integer, default=0)
    question = db.Column(db.Text, default="")
    selected = db.Column(db.Boolean, default=False, info={
        'label': 'Hafa upptoku'})

    def __init__(self, custom_token, custom_recording, voice_idx=None, utterance_idx=None):
        self.custom_token = custom_token
        self.custom_recording = custom_recording
        self.voice_idx = voice_idx
        self.utterance_idx = utterance_idx

    def getUserRating(self, user_id):
        for r in self.ratings:
            if r.user_id == user_id:
                return r.rating
        return None

    def getAllUsers(self):
        ratings = self.ratings
        user_ids = []
        for i in ratings:
            user_ids.append(i.user_id)
        user_ids = list(set(user_ids))
        return user_ids

    def get_dict(self):
        token = None
        if self.custom_token is not None:
            token = self.custom_token.get_dict()
        return {
            'id': self.id,
            'token': token,
            'mos_id': self.mos_id,
            'path': self.path,
            'text': self.text,
            'is_synth': self.is_synth,
            'selected': self.selected,
            'voice_idx': self.voice_idx,
            'utterance_idx': self.utterance_idx,
        }

    @property
    def path(self):
        return self.custom_recording.path

    @property
    def text(self):
        return self.custom_token.text

    @property
    def mos(self):
        return Mos.query.get(self.mos_id)

    @property
    def get_printable_id(self):
        return "MOS-Setning {}".format(self.id)

    @property
    def name(self):
        return "MOS-Setning {}".format(self.id)

    @property
    def ajax_edit_action(self):
        return url_for('mos.mos_instance_edit', id=self.id)

    @property
    def average_rating(self):
        if(len(self.ratings) > 0):
            total_ratings = 0
            for i in self.ratings:
                total_ratings += i.rating
            total_ratings = total_ratings/len(self.ratings)
            return round(total_ratings, 2)
        else:
            return "-"

    @property
    def std_of_ratings(self):
        ratings = [r.rating for r in self.ratings]
        if len(ratings) == 0:
            return "-"
        ratings = np.array(ratings)
        return round(np.std(ratings), 2)

    @property
    def number_of_ratings(self):
        return len(self.ratings)


class MosRating(BaseModel, db.Model):
    __tablename__ = 'MosRating'
    __table_args__ = (
        db.UniqueConstraint('mos_instance_id', 'user_id'),
      )
    id = db.Column(
        db.Integer, primary_key=True, nullable=False, autoincrement=True)
    rating = db.Column(db.Integer, default=0, info={
        'label': 'Einkunn',
        'min': 0,
        'max': 5,
    })
    mos_instance_id = db.Column(db.Integer, db.ForeignKey("MosInstance.id"))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = relationship("User", backref="parents")
    placement = db.Column(db.Integer)

    @property
    def get_user(self):
        return User.query.get(self.user_id)

    @property
    def get_instance(self):
        return MosInstance.query.get(self.mos_instance_id)
    

class SocialPost(BaseModel, db.Model):
    __tablename__ = 'SocialPost'
    id = db.Column(
        db.Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = relationship("User", back_populates="social_posts")
    recording_id = db.Column(
        db.Integer,
        db.ForeignKey('Recording.id'))
    recording = relationship("Recording", back_populates="social_posts")
    link = db.Column(db.String(255))
    text = db.Column(db.String(255))
    awards = db.relationship(
        "PostAward", lazy="joined", back_populates='post',
        cascade='all, delete, delete-orphan')

    def __init__(self, user_id, recording_id=None, link=None):
        self.user_id = user_id
        self.recording_id = recording_id
        self.link = link


    @property
    def total_awards(self):
        total = 0
        for a in self.awards:
            total += a.amount
        return total


class PostAward(BaseModel, db.Model):
    __tablename__ = 'PostAward'
    #__table_args__ = (
    #    db.UniqueConstraint('post_id', 'user_id'),
    #  )
    id = db.Column(
        db.Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    amount = db.Column(db.Integer, default=50)
    icon = db.Column(db.Integer, default=0)
    post_id = db.Column(db.Integer, db.ForeignKey("SocialPost.id"))
    post = db.relationship("SocialPost", back_populates="awards")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __init__(self, user_id, post, amount):
        self.user_id = user_id
        self.post = post
        self.amount = amount

