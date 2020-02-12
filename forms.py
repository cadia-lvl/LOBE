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

# TODO: move to app configuration
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
    assigned_user_id = QuerySelectField('Rödd', query_factory=lambda: User.query,
        get_label='name', allow_blank=True)
    sort_by = SelectField("Röðun", choices=[
        ('score', 'Röðunarstuðull'),
        ('same', 'Sömu röð og í skjali'),
        ('random', 'Slembiröðun')])
    has_video = BooleanField(label='Myndbandssöfnun', description='Hakið við ef myndbandsupptökur eru hluti af gagnasöfnun.')

    def validate_assigned_user_id(form, field):
        # HACK to user the QuerySelectField on User objects
        # but then later populate the field with only the pk.
        if field.data is not None:
            field.data = field.data.id

class BulkTokenForm(Form):
    is_g2p = BooleanField('Er G2P skjal.', description='Hakið við ef skjalið er G2P skjal samnber lýsingu hér að ofan',
        default=False)
    files = MultipleFileField('Textaskjöl', description='Veljið eitt eða fleiri textaskjöl.')

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
    role = QuerySelectField('Hlutverk', query_factory=lambda: Role.query, get_label='name',
                            validators=[validators.required()])


class UserEditForm(Form):
    name = TextField('Nafn')
    email = TextField('Netfang')
    role = QuerySelectField('Hlutverk', query_factory=lambda: Role.query, get_label='name',
                            validators=[validators.required()])

class SessionEditForm(Form):
    manager_id = QuerySelectField('Stjórnandi', query_factory=lambda: User.query, get_label='name',
        validators=[validators.required()])

    def validate_manager_id(form, field):
        if field.data is not None:
            field.data = field.data.id

RoleForm = model_form(model=Role, base_class=Form,
                      db_session=db.session)