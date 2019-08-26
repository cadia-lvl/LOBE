from wtforms import Form, HiddenField, TextField, TextAreaField, FileField, MultipleFileField, validators, SelectField, PasswordField
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.ext.sqlalchemy.orm import model_form
from flask_wtf import RecaptchaField
from flask_security.forms import RegisterForm, LoginForm
from flask import current_app as app
from models import db, Role

import os

class CollectionForm(Form):
    name = TextField('Nafn', validators=[validators.required()])

class BulkTokenForm(Form):
    files = MultipleFileField('Textaskjöl')

    # TODO add custom validator for files
    '''

    def validate_directory(form, field):
        return
    '''

class RecordForm(Form):
    token = HiddenField('Texti')
    recording = HiddenField('Upptaka')

class ExtendedLoginForm(LoginForm):
    if not os.getenv("FLASK_ENV", 'development') == 'development':
        recaptcha = RecaptchaField()

class ExtendedRegisterForm(RegisterForm):
    name = TextField('Nafn', [validators.required()])
    role = QuerySelectField('Role', query_factory=lambda: Role.query, get_label='name',
        validators=[validators.required()])

class UserEditForm(Form):
    name = TextField('Nafn')
    email = TextField('Netfang')
    role = QuerySelectField('Hlutverk', query_factory=lambda: Role.query, get_label='name',
        validators=[validators.required()])

RoleForm = model_form(model=Role, base_class=Form,
    db_session=db.session)