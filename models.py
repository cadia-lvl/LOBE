import contextlib
import os
import wave
from datetime import datetime, timedelta

from flask import current_app as app
from flask import url_for
from flask_security import RoleMixin, UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, select
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from werkzeug import secure_filename

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

    def __init__(self, name, sort_by, assigned_user_id=None):
        self.name = name
        self.sort_by = sort_by
        self.assigned_user_id = assigned_user_id

    @hybrid_property
    def num_tokens(self):
        return len(self.tokens)

    @num_tokens.expression
    def num_tokens(cls):
        return (select([func.count(Token.id)]).
                where(Token.collection == cls.id).
                label("num_tokens"))

    @hybrid_property
    def num_nonrecorded_tokens(self):
        return len([t for t in self.tokens if not t.has_recording])

    @num_nonrecorded_tokens.expression
    def num_nonrecorded_tokens(cls):
        return (select([func.count(Token.id)]).
                where(Token.collection == cls.id).
                where(Token.has_recording == False).
                label("num_tokens"))

    @hybrid_property
    def num_invalid_tokens(self):
        return len([t for t in self.tokens if t.marked_as_bad])

    @num_invalid_tokens.expression
    def num_nonrecorded_valid_tokens(cls):
        return (select([func.count(Token.id)]).
                where(Token.collection == cls.id).
                where(Token.marked_as_bad == True).
                label("num_tokens"))

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
        return url_for('download_collection', id=self.id)

    def get_download_index_url(self):
        return url_for('download_collection_index', id=self.id)

    def get_edit_url(self):
        return url_for('edit_collection', id=self.id)

    def get_record_dir(self):
        return os.path.join(app.config['RECORD_DIR'], str(self.id))

    def get_token_dir(self):
        return os.path.join(app.config['TOKEN_DIR'], str(self.id))

    def has_assigned_user(self):
        return self.assigned_user_id is not None

    def get_assigned_user(self):
        if self.has_assigned_user():
            return User.query.get(self.assigned_user_id)

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
            *ESTIMATED_AVERAGE_RECORD_LENGTH / 3600,1)


    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    name = db.Column(db.String, default=str(datetime.now().date()))

    # the assigned user
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    tokens = db.relationship(
        "Token", lazy='select', backref='collection',
        cascade='all, delete, delete-orphan', order_by="desc(Token.score)")
    sessions = db.relationship("Session", lazy='select', backref='collection', cascade='all, delete, delete-orphan')
    active = db.Column(db.Boolean, default=True)
    sort_by = db.Column(db.String)
    #recordings = db.relationship("Recording", lazy='joined', backref='collection')


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

    def get_path(self):
        return self.path

    def get_fname(self):
        return self.fname

    def get_length(self):
        return len(self.text)

    def save_to_disk(self):
        self.set_path()
        f = open(self.path, 'w')
        f.write(self.text)
        f.close()

    def set_path(self):
        self.fname = secure_filename("{}_{:09d}.token".format(
            os.path.splitext(self.original_fname)[0], self.id))
        self.path = os.path.join(app.config['TOKEN_DIR'], str(self.collection_id), self.fname)

    def get_configured_path(self):
        '''
        Get the path the program believes the token should be stored at
        w.r.t. the current TOKEN_DIR environment variable
        '''
        fname = secure_filename("{}_{:09d}.token".format(
            os.path.splitext(self.original_fname)[0], self.id))
        path = os.path.join(app.config['TOKEN_DIR'], str(self.collection_id), self.fname)
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
    def num_recordings(self):
        return len(self.recordings)

    @num_recordings.expression
    def num_recordings(cls):
        return (select([func.count(Recording.id)]).
                where(Recording.token_id == cls.id).
                label("num_recordings"))

    @hybrid_property
    def has_recording(self):
        return self.num_recordings > 0

    def get_printable_score(self):
        return round(self.score, 3)

    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True)
    text = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    original_fname = db.Column(db.String, default='Unknown')
    collection_id = db.Column(db.Integer, db.ForeignKey('Collection.id'))

    fname = db.Column(db.String)
    path = db.Column(db.String)
    marked_as_bad = db.Column(db.Boolean, default=False)
    # a tab seperated string of word pronounciations
    # where phones in each word is space seperated
    pron = db.Column(db.String)
    # default score is -1
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
        transcription):

        self.token_id = token_id
        self.original_fname = original_fname
        self.user_id = user_id
        self.transcription = transcription
        self.marked_as_bad = False

    def set_session_id(self, session_id):
        self.session_id = session_id

    def set_wave_params(self):
        '''
        Should only be callable after self.save_to_disk() has
        been called
        '''
        with contextlib.closing(wave.open(self.path,'r')) as f:
            w_params = f.getparams()
            self.sr = w_params.framerate
            self.num_frames = w_params.nframes
            self.duration = self.num_frames / float(self.sr)
            self.num_channels = w_params.nchannels

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

    def save_to_disk(self, file_obj):
        self.set_path()
        file_obj.filename = self.fname
        file_obj.save(self.path)


    def set_path(self):
        self.file_id = '{}_r{:09d}'.format(os.path.splitext(self.original_fname)[0], self.id)
        self.fname = secure_filename('{}.wav'.format(self.file_id))
        self.path = os.path.join(app.config['RECORD_DIR'],
            str(self.token.collection_id), self.fname)

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
        return Token.query.get(self.token_id)

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

    #@hybrid_property
    def get_collection(self):
        return Token.query.get(self.token_id).collection_id

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    original_fname = db.Column(db.String, default='Unknown')

    token_id = db.Column(db.Integer, db.ForeignKey('Token.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey('Session.id'))

    sr = db.Column(db.Integer)
    num_channels = db.Column(db.Integer, default=2)
    duration = db.Column(db.Float)
    num_frames = db.Column(db.Integer)
    bit_depth = db.Column(db.Integer)

    transcription = db.Column(db.String)

    fname = db.Column(db.String)
    file_id = db.Column(db.String)
    path = db.Column(db.String)

    marked_as_bad = db.Column(db.Boolean, default=False)

class Session(BaseModel, db.Model):
    __tablename__ = 'Session'

    def __init__(self, user_id, collection_id, duration=None):
        self.user_id = user_id
        self.collection_id = collection_id
        if duration is not None:
            self.duration = duration

    def get_printable_id(self):
        return "S-{:09d}".format(self.id)

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

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('Collection.id'))
    duration = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    recordings = db.relationship("Recording", lazy='joined', backref='session', cascade='all, delete, delete-orphan')

# Define models
roles_users = db.Table('roles_users',
        db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
        db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))

class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

class User(db.Model, UserMixin):
    def get_url(self):
        return url_for('user', id=self.id)
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))

    sex = db.Column(db.String(255))
    age = db.Column(db.Integer)
    dialect = db.Column(db.String(255))
    pin = db.Column(db.String(4))

    active = db.Column(db.Boolean())
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    roles = db.relationship('Role', secondary=roles_users,
        backref=db.backref('users', lazy='dynamic'))

    assigned_collections = db.relationship("Collection", cascade='all, delete, delete-orphan')
    recordings = db.relationship("Recording")

    def get_printable_name(self):
        if self.name is not None:
            return self.name
        else:
            return "Nafnlaus notandi"

    def is_admin(self):
        return self.roles[0].id == ADMIN_ROLE_ID

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