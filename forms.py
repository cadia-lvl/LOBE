import os

from flask import current_app as app
from flask_security.forms import LoginForm, RegisterForm
from flask_wtf import RecaptchaField
from wtforms import (fields, FileField, Form, HiddenField, MultipleFileField,
                     PasswordField, SelectField, TextAreaField, TextField, IntegerField, BooleanField,
                     validators, ValidationError, FloatField)
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.ext.sqlalchemy.orm import model_form

from models import Role, User, Collection, Configuration, db

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
    configuration_id = QuerySelectField('Stilling', query_factory=lambda: Configuration.query,
        get_label='printable_name', allow_blank=False)
    sort_by = SelectField("Röðun", choices=[
        ('score', 'Röðunarstuðull'),
        ('same', 'Sömu röð og í skjali'),
        ('random', 'Slembiröðun')])

    def validate_assigned_user_id(self, field):
        # HACK to user the QuerySelectField on User objects
        # but then later populate the field with only the pk.
        if field.data is not None:
            print(field.data)
            print(field.data.id)
            field.data = field.data.id

    def validate_configuration_id(self, field):
        print(field.data)
        if field.data is not None:
            print(field.data)
            print(field.data.id)
            field.data = field.data.id


def collection_edit_form(collection):
    form = CollectionForm()
    form.assigned_user_id.default = collection.get_assigned_user()
    form.configuration_id.default = collection.configuration
    form.sort_by.default = collection.sort_by
    form.process()
    form.name.data = collection.name
    return form


class BulkTokenForm(Form):
    is_g2p = BooleanField('G2P skjal.', description='Hakið við ef skjalið er G2P skjal samanber lýsingu hér að ofan',
        default=False)
    files = MultipleFileField('Textaskjöl', description='Veljið eitt eða fleiri textaskjöl.',
        validators=[validators.required()])
    '''
    collection_id = QuerySelectField('Önnur söfnun', description='Veljið söfnun ef á að nota sömu setningar og í annarri söfnun',
        query_factory=lambda: User.query, get_label='name', allow_blank=True)
    '''

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
    is_admin = BooleanField("Notandi er vefstjóri")

class UserEditForm(Form):
    name = TextField('Nafn')
    email = TextField('Netfang')
    dialect = SelectField('Framburður', [validators.required()],
        choices=dialect_choices)
    sex = SelectField('Kyn',
        [validators.required()], choices=sex_choices)
    age = IntegerField('Aldur')

class SessionEditForm(Form):
    manager_id = QuerySelectField('Stjórnandi', query_factory=lambda: User.query, get_label='name',
        validators=[validators.required()])

    def validate_manager_id(self, field):
        if field.data is not None:
            field.data = field.data.id

class ConfigurationForm(Form):
    name = TextField('Nafn stillinga')
    session_sz = IntegerField('Fjöldi setninga í lotu',
        [validators.required(), validators.NumberRange(min=1, max=100)],
        default=50)
    live_transcribe = BooleanField('Nota talgreini',
        description="Getur haft áhrif á hljóðgæði")
    visualize_mic = BooleanField('Sýna hljóðnemaviðmót',
        description="Getur haft áhrif á hljóðgæði")
    analyze_sound = BooleanField("Sjálfvirk gæðastjórnun")
    auto_trim = BooleanField('Klippa hljóðbrot sjálfkrafa')
    channel_count = SelectField("Fjöldi hljóðrása",
        choices=[(1, "1 rás"), (2, "2 rásir")],
        coerce=int,
        description='Athugið að hljóðrásir eru núna alltaf samþjappaðar eftir upptökur.')
    sample_rate = SelectField("Upptökutíðni",
        choices=[(16000, "16,000 Hz"), (32000, "32,000 Hz"),
            (44100, "44,100 Hz"), (48000, "48,000 Hz")],
        coerce=int)
    sample_size = SelectField("Sýnisstærð",
        choices=[(16, "16 heiltölubitar"), (24, "24 heiltölubitar"), (32, "32 fleytibitar")],
        coerce=int,
        description='Ef PCM er valið sem hljóðmerkjamál er sýnisstærðin 32 bitar sjálfgefið')
    audio_codec = SelectField("Hljóðmerkjamál",
        choices=[("pcm", "PCM")])

    trim_threshold = FloatField("lágmarkshljóð (dB)",
        [validators.NumberRange(min=0)],
        default=40,
        description="Þröskuldur sem markar þögn, því lægri því meira telst sem þögn. "+\
            "Þetta kemur bara af notum þegar sjálfvirk klipping er notuð. Hljóðrófsritið er desíbel-skalað.")
    too_low_threshold = FloatField("Lágmarkshljóð fyrir gæði (dB)",
        [validators.NumberRange(min=-100, max=0)],
        default=-15,
        description="Ef hljóðrófsrit upptöku fer aldrei yfir þennan þröskuld þá mun "+\
            "gæðastjórnunarkerfi merkja þessa upptöku of lága. Athugið að hér er hljóðrófsritið skalað eftir styrk.")
    too_high_threshold = FloatField("Hámarkshljóð fyrir gæði (dB)",
        [validators.NumberRange(min=-100, max=0)],
        default=-4.5,
        description="Ef hljóðrófsrit upptöku fer yfir þennan þröskuld ákveðin fjölda af römmum í röð "+\
            "þá mun gæðastjórnunarkerfi merkja þessa upptöku of háa. Athugið að hér er hljóðrófsritið skalað eftir styrk.")
    too_high_frames = IntegerField("Fjöldi of hárra ramma",
        [validators.NumberRange(min=0, max=100)],
        default=10,
        description="Segir til um hversu margir rammar i röð þurfa að vera fyrir ofan gæðastjórnunarþröskuldinn "+\
            "til að vera merkt sem of há upptaka.")
    auto_gain_control = BooleanField("Sjálfvirk hljóðstýring",
        description="Getur haft áhrif á hljóðgæði")
    noise_suppression = BooleanField("Dempun bakgrunnshljóðs",
        description="Getur haft áhrif á hljóðgæði")
    has_video = BooleanField('Myndbandssöfnun', default=False)
    video_w = IntegerField("Vídd myndbands í pixlum",
        [validators.NumberRange(min=0)],
        default=1280,
        description="Einungis notað ef söfnun er myndbandssöfnun.")
    video_h = IntegerField("Hæð myndbands í pixlum",
        [validators.NumberRange(min=0)],
        default=720,
        description="Einungis notað ef söfnun er myndbandssöfnun.")
    video_codec = SelectField("Myndmerkjamál",
        choices=[("vp8", "VP8")])

RoleForm = model_form(model=Role, base_class=Form,
                      db_session=db.session)