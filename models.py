from flask_sqlalchemy import SQLAlchemy
from flask_security import UserMixin, RoleMixin
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy import select, func

from datetime import datetime

from flask import url_for
from flask import current_app as app

from werkzeug import secure_filename

import os
import wave
import contextlib


db = SQLAlchemy()

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

    def __init__(self, name):
        self.name = name

    def get_tokens(self):
        '''
        Get all tokens associated with this collection.
        If only_nonrec is set to True, only tokens without
        recordings are returned
        '''
        return Token.query.filter_by(collection=self.id)

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

    @hybrid_method
    def get_complete_ratio(self, as_percent=False):
        if self.num_tokens == 0:
            ratio = 0
        else:
            ratio = (self.num_tokens - self.num_nonrecorded_tokens) / self.num_tokens
        if as_percent: ratio *= 100
        return ratio


    def get_url(self):
        return url_for('collection', id=self.id)

    def get_record_dir(self):
        return os.path.join(app.config['RECORD_DIR'], str(self.id))

    def get_token_dir(self):
        return os.path.join(app.config['TOKEN_DIR'], str(self.id))

    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)
    name = db.Column(db.String, default=str(datetime.now().date()), nullable=False)

    tokens = db.relationship("Token", lazy='joined')

class Token(BaseModel, db.Model):
    __tablename__ = 'Token'

    def __init__(self, text, original_fname, collection):
        self.text = text
        self.original_fname = original_fname
        self.collection = collection

    def get_url(self):
        return url_for('token', id=self.id)

    def get_record_url(self):
        return url_for('record_single', tok_id=self.id)

    def get_path(self):
        return self.path

    def get_fname(self):
        return self.fname

    '''
    def get_collection(self):
        return Collection.query.get(self.collection)
    '''

    '''
    def get_recordings(self):
        recs = Recording.query.filter_by(token=self.id)
        return recs
    '''

    def get_length(self):
        return len(self.text)

    def save_to_disk(self):
        self.fname = secure_filename("{}_{:09d}.token".format(
            os.path.splitext(self.original_fname)[0], self.id))
        self.path = os.path.join(app.config['TOKEN_DIR'], str(self.collection), self.fname)

        f = open(self.path, 'w')
        f.write(self.text)
        f.close()

    def get_dict(self):
        return {'id':self.id, 'text':self.text, 'file_id':self.get_file_id()}

    def get_file_id(self):
        return os.path.splitext(self.fname)[0]

    @hybrid_property
    def num_recordings(self):
        return len(self.recordings)

    @num_recordings.expression
    def num_recordings(cls):
        return (select([func.count(Recording.id)]).
                where(Recording.token == cls.id).
                label("num_recordings")
                )

    @hybrid_property
    def has_recording(self):
        return self.num_recordings > 0

    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True)
    text = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)

    original_fname = db.Column(db.String, default='Unknown')
    collection = db.Column(db.Integer, db.ForeignKey('Collection.id'), nullable=False)

    fname = db.Column(db.String)
    path = db.Column(db.String)

    recordings = db.relationship("Recording", lazy='joined')

class Recording(BaseModel, db.Model):
    __tablename__ = 'Recording'

    def __init__(self, token, original_fname, user, transcription):
        self.token = token
        self.original_fname = original_fname
        self.user = user
        self.transcription = transcription

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

    def get_url(self):
        return url_for('recording', id=self.id)

    def get_download_url(self):
        return url_for('download_recording', id=self.id)

    def get_directory(self):
        return os.path.dirname(self.path)

    def get_path(self):
        return self.path

    def save_to_disk(self, file_obj):
        self.fname = secure_filename(
            '{}_r{:09d}.wav'.format(os.path.splitext(self.original_fname)[0], self.id))
        self.path = os.path.join(app.config['RECORD_DIR'],
            str(Token.query.get(self.token).collection), self.fname)
        file_obj.filename = self.fname
        file_obj.save(self.path)

    def get_file_id(self):
        return os.path.splitext(self.fname)[0]

    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)
    original_fname = db.Column(db.String, default='Unknown')
    token = db.Column(db.Integer, db.ForeignKey('Token.id'), nullable=False)
    user = db.Column(db.Integer, db.ForeignKey('user.id'))

    sr = db.Column(db.Integer)
    num_channels = db.Column(db.Integer, default=2)
    duration = db.Column(db.Float)
    num_frames = db.Column(db.Integer)

    transcription = db.Column(db.String)

    fname = db.Column(db.String)
    path = db.Column(db.String)

# Define models
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
    active = db.Column(db.Boolean())
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    roles = db.relationship('Role', secondary=roles_users,
        backref=db.backref('users', lazy='dynamic'))