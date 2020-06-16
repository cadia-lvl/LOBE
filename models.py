import contextlib
import os
import wave
import json
import subprocess
from datetime import datetime, timedelta

from flask import current_app as app
from flask import url_for
from flask_security import RoleMixin, UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, select, MetaData
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from werkzeug import secure_filename

'''
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
meta = MetaData(naming_convention=convention)
db = SQLAlchemy(metadata=meta)
'''
db = SQLAlchemy()

ADMIN_ROLE_ID = 1
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

    def __init__(self, name, sort_by, assigned_user_id=None,
        configuration_id=None):
        self.name = name
        self.sort_by = sort_by
        self.assigned_user_id = assigned_user_id
        self.configuration_id = configuration_id

    @hybrid_property
    def num_nonrecorded_tokens(self):
        return self.num_tokens - self.num_recorded_tokens

    @hybrid_method
    def get_complete_ratio(self, as_percent=False):
        if self.num_tokens == 0:
            ratio = 0
        else:
            ratio = (self.num_tokens - self.num_nonrecorded_tokens) / self.num_tokens
        if as_percent: ratio = round(ratio*100, 3)
        return ratio

    @hybrid_method
    def get_invalid_ratio(self, as_percent=False):
        if self.num_tokens == 0:
            ratio = 0
        else:
            ratio = (self.num_invalid_tokens) / self.num_tokens
        if as_percent: ratio = round(ratio*100, 3)
        return ratio

    def get_url(self):
        return url_for('collection', id=self.id)

    def get_download_url(self):
        return url_for('stream_collection_zip', id=self.id)

    def get_edit_url(self):
        return url_for('edit_collection', id=self.id)

    def get_trim_url(self, trim_type):
        return url_for('trim_collection', id=self.id) + f'?trim_type={trim_type}'

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
        tokens = Token.query.filter(Token.collection_id==self.id)
        self.num_tokens = tokens.count()
        self.num_invalid_tokens = tokens.filter(Token.marked_as_bad==True).count()
        self.num_recorded_tokens = tokens.filter(Token.num_recordings>0).count()


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
        return round((self.num_tokens - self.num_nonrecorded_tokens)\
            *ESTIMATED_AVERAGE_RECORD_LENGTH/3600, 1)

    @hybrid_property
    def configuration(self):
        if self.configuration_id is not None:
            return Configuration.query.get(self.configuration_id)
        return None

    @property
    def printable_id(self):
        return "T-{:04d}".format(self.id)


    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    name = db.Column(db.String, default=str(datetime.now().date()))

    # the assigned user
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    configuration_id = db.Column(db.Integer, db.ForeignKey('Configuration.id'))
    tokens = db.relationship("Token", lazy='select', backref='collection',
        cascade='all, delete, delete-orphan')
    sessions = db.relationship("Session", lazy='select',
        backref='collection', cascade='all, delete, delete-orphan')
    active = db.Column(db.Boolean, default=True)
    sort_by = db.Column(db.String)
    num_tokens = db.Column(db.Integer, default=0)
    num_recorded_tokens = db.Column(db.Integer, default=0)
    num_invalid_tokens = db.Column(db.Integer, default=0)

    has_zip = db.Column(db.Boolean, default=False)
    zip_token_count = db.Column(db.Integer, default=0)
    zip_created_at = db.Column(db.DateTime)


class Configuration(BaseModel, db.Model):
    __tablename__ = 'Configuration'

    def __init__(self):
        pass

    @hybrid_property
    def printable_name(self):
        if self.name:
            return self.name
        else:
            return "Conf-{:03d}".format(self.id)

    @hybrid_property
    def url(self):
        return url_for("conf", id=self.id)

    @hybrid_property
    def delete_url(self):
        return url_for("delete_conf", id=self.id)

    @hybrid_property
    def edit_url(self):
        return url_for("edit_conf", id=self.id)

    @hybrid_property
    def codec(self):
        codec = self.audio_codec
        if self.has_video:
            codec = f'{self.video_codec}, {codec}'

    @hybrid_property
    def media_constraints(self):
        constraints = {'audio':{
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

    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True)
    name = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    is_default = db.Column(db.Boolean, default=False)
    # general configuration
    session_sz = db.Column(db.Integer, default=50)
    live_transcribe = db.Column(db.Boolean, default=True)
    visualize_mic = db.Column(db.Boolean, default=True)
    auto_trim = db.Column(db.Boolean, default=True)
    analyze_sound = db.Column(db.Boolean, default=True)

    # recording configuration
    auto_gain_control = db.Column(db.Boolean, default=False)
    noise_suppression = db.Column(db.Boolean, default=False)
    channel_count = db.Column(db.Integer, default=1)
    sample_rate = db.Column(db.Integer, default=48000)
    sample_size = db.Column(db.Integer, default=16)

    # MediaRecorder configuration
    blob_slice = db.Column(db.Integer, default=10)
    audio_codec = db.Column(db.String, default='pcm')

    # Video configuration
    video_w = db.Column(db.Integer, default=1280)
    video_h = db.Column(db.Integer, default=720)
    video_codec = db.Column(db.String, default='vp8')
    has_video = db.Column(db.Boolean, default=False)

    # Other
    trim_threshold = db.Column(db.Float, default=40)
    too_low_threshold = db.Column(db.Float, default=-15)
    too_high_threshold = db.Column(db.Float, default=-4.5)
    too_high_frames = db.Column(db.Integer, default=10)


class Token(BaseModel, db.Model):
    __tablename__ = 'Token'

    def __init__(self, text, original_fname, collection_id,
        score:float=-1, pron:str=None, source:str=None):
        self.text = text
        self.original_fname = original_fname
        self.collection_id = collection_id
        self.marked_as_bad = False
        self.score = score
        if pron is not None:
            self.pron = pron
        if source is not None:
            self.source = source

    def get_url(self):
        return url_for('token', id=self.id)

    def get_record_url(self):
        return url_for('record_single', tok_id=self.id)

    @hybrid_property
    def mark_bad_url(self):
        return url_for('toggle_token_bad', id=self.id)

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
        fname = secure_filename("{}_{:09d}.token".format(
            os.path.splitext(self.original_fname)[0], self.id))
        path = os.path.join(
            app.config['TOKEN_DIR'], str(self.collection_id), self.fname)
        return path

    def get_dict(self):
        return {'id':self.id, 'text':self.text, 'file_id':self.get_file_id(),
        'url':self.get_url()}

    def get_file_id(self):
        return os.path.splitext(self.fname)[0]

    def get_printable_id(self):
        return "T-{:09d}".format(self.id)

    def get_directory(self):
        return os.path.dirname(self.path)

    def get_download_url(self):
        return url_for('download_token', id=self.id)

    @hybrid_property
    def delete_url(self):
        return url_for('delete_token', id=self.id)

    def update_numbers(self):
        self.num_recordings = Recording.query.filter(
            Recording.token_id==self.id).count()

    def get_printable_score(self):
        return round(self.score, 3)

    @hybrid_property
    def collection(self):
        return Collection.query.get(self.collection_id)

    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True)
    text = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    original_fname = db.Column(db.String, default='Unknown')
    collection_id = db.Column(db.Integer, db.ForeignKey('Collection.id'))

    fname = db.Column(db.String)
    path = db.Column(db.String)
    marked_as_bad = db.Column(db.Boolean, default=False)
    num_recordings = db.Column(db.Integer, default=0)
    pron = db.Column(db.String)
    score = db.Column(db.Float, default=-1)
    source = db.Column(db.String)

    recordings = db.relationship("Recording", lazy='joined', backref='token')


class Rating(BaseModel, db.Model):
    __tablename__ = 'Rating'

    def __init__(self, recording_id, user_id, value):
        self.recording_id = recording_id
        self.user_id = user_id
        self.value = value

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    recording_id = db.Column(db.Integer, db.ForeignKey('Recording.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    value = db.Column(db.Boolean, default=False)


class Recording(BaseModel, db.Model):
    __tablename__ = 'Recording'

    def __init__(self, token_id, original_fname, user_id,
        bit_depth=None, session_id=None, has_video=False):
        self.token_id = token_id
        self.original_fname = original_fname
        self.user_id = user_id
        self.marked_as_bad = False
        if bit_depth is not None:
            self.bit_depth = bit_depth
        if session_id is not None:
            self.session_id = session_id
        self.has_video = has_video

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
        return url_for('recording', id=self.id)

    def get_fname(self):
        return self.fname

    def get_download_url(self):
        return url_for('download_recording', id=self.id)

    def get_toggle_bad_url(self):
        return url_for('toggle_recording_bad', id=self.id)

    def get_toggle_bad_ajax(self):
        return url_for('toggle_recording_bad_ajax', id=self.id)

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
        if os.getenv('SEMI_PROD', False) or os.getenv('FLASK_ENV', 'development') == 'production':
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
        # TODO: deal with file endings
        self.file_id = '{}_r{:09d}_t{:09d}'.format(
            os.path.splitext(self.original_fname)[0], self.id, self.token_id)
        self.fname = secure_filename(f'{self.file_id}.webm')
        self.path = os.path.join(app.config['VIDEO_DIR'] if self.has_video else app.config['RECORD_DIR'],
            str(self.token.collection_id), self.fname)
        self.wav_path = os.path.join(app.config['WAV_AUDIO_DIR'],
            str(self.token.collection_id),
            secure_filename(f'{self.file_id}.wav'))

    def get_configured_path(self):
        '''
        Get the path the program believes the token should be stored at
        w.r.t. the current TOKEN_DIR environment variable
        '''
        file_id = '{}_r{:09d}'.format(os.path.splitext(self.original_fname)[0], self.id)
        fname = secure_filename('{}.wav'.format(self.file_id))
        path = os.path.join(app.config['RECORD_DIR'],
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

    def get_token(self):
        if self.token_id is not None:
            return Token.query.get(self.token_id)
        return None

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
        return {'id':self.id, 'token': self.token.get_dict()}

    def get_collection_id(self):
        return Token.query.get(self.token_id).collection_id

    def set_trim(self, start, end):
        self.start = start
        self.end = end

    @property
    def has_trim(self):
        return self.start is not None and self.end is not None

    def reset_trim(self):
        self.set_trim(None, None)

    @property
    def is_verified(self):
        return len(self.verifications) == 2

    @property
    def is_half_verified(self):
        return len(self.verifications) == 1

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    original_fname = db.Column(db.String, default='Unknown')

    token_id = db.Column(db.Integer, db.ForeignKey('Token.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey('Session.id'))

    sr = db.Column(db.Integer)
    num_channels = db.Column(db.Integer, default=1)
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

    marked_as_bad = db.Column(db.Boolean, default=False)
    has_video = db.Column(db.Boolean, default=False)

    verifications = db.relationship("Verification", lazy='select',
            backref='recording', cascade='all, delete, delete-orphan')

class Session(BaseModel, db.Model):
    __tablename__ = 'Session'

    def __init__(self, user_id, collection_id, manager_id,
        duration=None, has_video=False):
        self.user_id = user_id
        self.manager_id = manager_id
        self.collection_id = collection_id
        self.has_video = has_video
        if duration is not None:
            self.duration = duration

    def get_printable_id(self):
        return "S-{:06d}".format(self.id)

    def get_url(self):
        return url_for('rec_session', id=self.id)

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

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('Collection.id'))
    duration = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    has_video = db.Column(db.Boolean, default=False)
    recordings = db.relationship("Recording", lazy='joined', backref='session', cascade='all, delete, delete-orphan')

    is_secondarily_verified = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)

    verified_by =  db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    secondarily_verified_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)


class Verification(BaseModel, db.Model):
    __tablename__ = 'Verification'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    verified_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    recording_id = db.Column(db.Integer, db.ForeignKey('Recording.id'))

    volume_is_low = db.Column(db.Boolean, default=False)
    volume_is_high = db.Column(db.Boolean, default=False)
    recording_has_glitch = db.Column(db.Boolean, default=False)
    recording_has_wrong_wording = db.Column(db.Boolean, default=False)

    comment = db.Column(db.String(255))

    is_secondary = db.Column(db.Boolean, default=False)

    trims = db.relationship("Trim", lazy='select',
           backref='verification', cascade='all, delete, delete-orphan')


class Trim(BaseModel, db.Model):
    __tablename__ = 'Trim'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    start = db.Column(db.Float)
    end = db.Column(db.Float)
    index = db.Column(db.Integer)
    verification_id = db.Column(db.Integer, db.ForeignKey('Verification.id'))


roles_users = db.Table('roles_users',
        db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
        db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))

class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))

    sex = db.Column(db.String(255))
    age = db.Column(db.Integer)
    dialect = db.Column(db.String(255))

    active = db.Column(db.Boolean())
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    roles = db.relationship('Role', secondary=roles_users,
        backref=db.backref('users', lazy='dynamic'))

    assigned_collections = db.relationship("Collection", cascade='all, delete, delete-orphan')
    recordings = db.relationship("Recording")

    def get_url(self):
        return url_for('user', id=self.id)

    def get_printable_name(self):
        if self.name is not None:
            return self.name
        else:
            return "Nafnlaus notandi"

    def is_admin(self):
        return len(self.roles) > 0 and self.roles[0].id == ADMIN_ROLE_ID

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



