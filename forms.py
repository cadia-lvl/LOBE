from wtforms import Form, HiddenField, TextField, TextAreaField, FileField, MultipleFileField, validators, SelectField
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from flask_wtf import RecaptchaField
from flask_security.forms import RegisterForm, LoginForm

from models import Role

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
    recaptcha = RecaptchaField()

class ExtendedRegisterForm(RegisterForm):
    name = TextField('Nafn', [validators.required()])
    role = QuerySelectField('Role', query_factory=lambda: Role.query, get_label='name',
        validators=[validators.required()])