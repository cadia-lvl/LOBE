import os

from flask import current_app as app
from flask_security.forms import LoginForm, RegisterForm
from flask_wtf import RecaptchaField
from wtforms import (fields, FileField, Form, HiddenField, MultipleFileField,
                     PasswordField, SelectField, TextAreaField, TextField, IntegerField, BooleanField,
                     validators, ValidationError)
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.ext.sqlalchemy.orm import model_form

from models import Role, User, Collection, db

sex_choices = [('Kona','Kona'), ('Karl','Karl'), ('Annað','Annað')]
dialect_choices = [('Linmæli', 'Linmæli'),
    ('Harðmæli', 'Harðmæli'),
    ('Raddaður framburður', 'Raddaður framburður'),
    ('hv-framburður', 'hv-framburður'),
    ('bð-, gð-framburður', 'bð-, gð-framburður'),
    ('ngl-framburður', 'ngl-framburður'),
    ('rn-, rl-framburður', 'rn-, rl-framburður'),
    ('Vestfirskur einhljóðaframburður', 'Vestfirskur einhljóðaframburður'),
    ('Skaftfellskur einhljóðaframburður', 'Skaftfellskur einhljóðaframburður')]

class CollectionForm(Form):
    name = TextField('Nafn', validators=[validators.required()])
    assigned_user = QuerySelectField('Rödd', query_factory=lambda: User.query,
        get_label='name', allow_blank=True)

class BulkTokenForm(Form):
    is_g2p = BooleanField('Er G2P skjal.', default=False)
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
    sex = SelectField('Kyn',
        [validators.required()], choices=sex_choices)
    dialect = SelectField('Framburður', [validators.required()],
        choices=dialect_choices)
    age = IntegerField('Aldur', [validators.required(),
        validators.NumberRange(min=18, max=100)])
    pin = PasswordField('PIN', [validators.required(),
        validators.length(min=4, max=4)], description='4 tölustafir')
    pin_2 = PasswordField('Endurtaktu PIN', [validators.required(),
        validators.length(min=4, max=4)])
    role = QuerySelectField('Hlutverk', query_factory=lambda: Role.query, get_label='name',
                            validators=[validators.required()])

    def validadate_pin(form, field):
        if form.pin.data != form.pin_2.data:
            raise ValidationError('PIN did not match.')


class UserEditForm(Form):
    name = TextField('Nafn')
    email = TextField('Netfang')
    role = QuerySelectField('Hlutverk', query_factory=lambda: Role.query, get_label='name',
                            validators=[validators.required()])


RoleForm = model_form(model=Role, base_class=Form,
                      db_session=db.session)