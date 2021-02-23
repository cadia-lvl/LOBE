import os

from flask import current_app as app
from flask import url_for
from flask_security.forms import LoginForm, RegisterForm
from flask_wtf import RecaptchaField
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (Form, HiddenField, MultipleFileField, SelectMultipleField,
                     SelectField, TextField, IntegerField, BooleanField,
                     validators, ValidationError, FloatField, widgets, StringField, RadioField)

from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.ext.sqlalchemy.orm import model_form
from wtforms.fields.html5 import EmailField
from wtforms.validators import InputRequired
from wtforms_alchemy import ModelForm
from wtforms_components import ColorField

from models import (
    Collection, Configuration, Role, User,
    VerifierIcon, PremiumItem, VerifierQuote, VerifierTitle,
    VerifierFont, db, Posting, Application, Mos, MosInstance)



# TODO: move to app configuration
sex_choices = [('Kona','Kona'), ('Karl','Karl'), ('Annað','Annað')]
dialect_choices = [
    ('Linmæli', 'Linmæli'),
    ('Harðmæli', 'Harðmæli'),
    ('Raddaður framburður', 'Raddaður framburður'),
    ('hv-framburður', 'hv-framburður'),
    ('bð-, gð-framburður', 'bð-, gð-framburður'),
    ('ngl-framburður', 'ngl-framburður'),
    ('rn-, rl-framburður', 'rn-, rl-framburður'),
    ('Vestfirskur einhljóðaframburður', 'Vestfirskur einhljóðaframburður'),
    ('Skaftfellskur einhljóðaframburður', 'Skaftfellskur einhljóðaframburður')
]
voice_choices = [
    ("sopran", "Sópran"),
    ("alt", "Alt"),
    ("tenor", "Tenór"),
    ("bassi", "Bassi"),
]


class MultiCheckboxField(SelectMultipleField):
    """
    A multiple-select, except displays a list of checkboxes.

    Iterating the field will produce subfields, allowing custom rendering of
    the enclosed checkbox fields.
    """
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

class DailySpinForm(Form):
    prize_type = HiddenField('type', validators=[validators.required()])
    prize_value = HiddenField('value')

class VerifierIconForm(ModelForm):
    class Meta:
        model = VerifierIcon


class VerifierTitleForm(ModelForm):
    class Meta:
        model = VerifierTitle


class VerifierQuoteForm(ModelForm):
    class Meta:
        model = VerifierQuote

class VerifierFontForm(ModelForm):
    class Meta:
        model = VerifierFont

class PremiumItemForm(ModelForm):
    class Meta:
        model = PremiumItem


class MosForm(ModelForm):

    class Meta:
        model = Mos
        exclude = ['uuid']
        num_samples = IntegerField('Fjöldi setninga', [validators.required()])
    
    def __init__(self, max_available, *args, **kwargs):
        super(MosForm, self).__init__(*args, **kwargs)
        self.max_available = max_available
    
    def validate_num_samples(form, field):
        if field.data >= form.max_available or field.data < 0:
            raise ValidationError("Ekki nógu markar upptökur til í safni. Sláðu inn tölu á milli 0 og {}".format(form.max_available))


class MosSelectAllForm(Form):
    is_synth = HiddenField()
    select = HiddenField()


class MosItemSelectionForm(ModelForm):
    class Meta:
        model = MosInstance
        exclude = ['is_synth']

class MosTestForm(Form):
    name = StringField("Nafn", [validators.required()])
    age = IntegerField("Aldur", [validators.required(),
                       validators.NumberRange(min=10, max=120)])
    email = EmailField("Netfang", [validators.required()])

class UploadCollectionForm(FlaskForm):
    is_g2p = BooleanField('Staðlað form.',
        description='Hakið við ef uphleðslan er á stöðluðu formi samanber lýsingu hér að ofan',
        default=False)
    is_lobe_collection = BooleanField('LOBE söfnun.',
        description='Hakið við ef uphleðslan er LOBE söfnun á sama formi og LOBE söfnun er hlaðið niður',
        default=False)
    name = TextField('Nafn', validators=[validators.required()])
    assigned_user_id = QuerySelectField('Rödd', query_factory=lambda: User.query,
                                        get_label='name', allow_blank=True)
    configuration_id = QuerySelectField('Stilling', query_factory=lambda: Configuration.query,
                                        get_label='printable_name', allow_blank=False)
    sort_by = SelectField("Röðun", choices=[
        ('score', 'Röðunarstuðull'),
        ('same', 'Sömu röð og í skjali'),
        ('random', 'Slembiröðun')])
    is_dev = BooleanField('Tilraunarsöfnun')
    is_multi_speaker = BooleanField("Margar raddir")
    
    files = FileField(validators=[FileAllowed(['zip'], 'Skrá verður að vera zip mappa'), FileRequired('Hladdu upp zip skrá')])

    
    def validate_assigned_user_id(self, field):
        # HACK to user the QuerySelectField on User objects
        # but then later populate the field with only the pk.
        if field.data is not None:
            field.data = field.data.id

    def validate_configuration_id(self, field):
        if field.data is not None:
            field.data = field.data.id

    def validate_is_g2p(self, field):
        if field.data:
            if not self.is_lobe_collection.data:
                return True
            else:
                raise ValidationError('Velja verður annað hvort staðlað form EÐA LOBE söfnun')
        else:
            if self.is_lobe_collection.data:
                return True
            else:
                raise ValidationError('Velja verður annað hvort staðlað form EÐA LOBE söfnun')
        raise ValidationError('Velja verður annað hvort staðlað form EÐA LOBE söfnun')

    def validate_is_lobe_collection(self, field):
        if field.data:
            if not self.is_g2p.data:
                return True
            else:
                raise ValidationError('Velja verður annað hvort staðlað form EÐA LOBE söfnun')
        else:
            if self.is_g2p.data:
                return True
            else:
                raise ValidationError('Velja verður annað hvort staðlað form EÐA LOBE söfnun')
        raise ValidationError('Velja verður annað hvort staðlað form EÐA LOBE söfnun')
        
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
    is_dev = BooleanField('Tilraunarsöfnun')
    is_multi_speaker = BooleanField("Margar raddir")

    def validate_assigned_user_id(self, field):
        # HACK to user the QuerySelectField on User objects
        # but then later populate the field with only the pk.
        if field.data is not None:
            field.data = field.data.id

    def validate_configuration_id(self, field):
        if field.data is not None:
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

class MosUploadForm(FlaskForm):
    is_g2p = BooleanField('Staðlað form.', description='Hakið við ef uphleðslan er á stöðluðu formi samanber lýsingu hér að ofan',
                          default=False)
    files = FileField(validators=[FileAllowed(['zip'], 'Skrá verður að vera zip mappa'), FileRequired('Hladdu upp zip skrá')])

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


class VerifierRegisterForm(RegisterForm):
    name = TextField('Nafn', [validators.required()])


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


class DeleteVerificationForm(Form):
    verification_id = HiddenField(
        "verification_id", validators=[InputRequired()])



class SessionVerifyForm(Form):
    """Form to verify a recording inside a session
    """
    LOW = "low"
    HIGH = "high"
    WRONG = "wrong"
    GLITCH = "glitch"
    GLITCH_OUTSIDE = "glitch-outside"
    OK = "ok"
    CHOICES = [
        (LOW, "<i class='fa fa-volume-mute text-danger mr-1'></i> Of lágt (a)"),
        (HIGH, "<i class='fa fa-volume-up text-danger mr-1'></i> of hátt (s)"),
        (WRONG, "<i class='fa fa-comment-slash text-danger mr-1'></i> Rangt lesið (d)"),
        (GLITCH, "<i class='fa fa-times text-danger mr-1'></i> Gölluð (f)"),
        (GLITCH_OUTSIDE, "<i class='fa fa-times text-danger mr-1'></i> Galli klipptur (v)"),
        (OK, "<i class='fa fa-check mr-1 text-success'></i> Góð (g)"),
    ]

    quality = MultiCheckboxField(
        "Gæði", choices=CHOICES, validators=[InputRequired()])
    comment = StringField("Athugasemd", widget=widgets.TextArea())

    recording = HiddenField("recording", validators=[InputRequired()])
    verified_by = HiddenField("verified_by", validators=[InputRequired()])
    session = HiddenField('session', validators=[InputRequired()])
    num_verifies = HiddenField("num_verifies", validators=[InputRequired()])
    cut = HiddenField("cut", validators=[InputRequired()])

    def validate_quality(self, field):
        data = self.quality.data
        if self.LOW in data and self.HIGH in data:
            raise ValidationError(
                "Upptakan getur ekki verið bæði of lág og of há")
        if self.OK in data and len(data) > 1:
            raise ValidationError("Upptakan getur ekki verið bæði góð og slæm")


class ConfigurationForm(Form):
    name = TextField('Nafn stillinga')
    session_sz = IntegerField('Fjöldi setninga í lotu',
                              [validators.required(), validators.NumberRange(
                                  min=1, max=100)],
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
                              choices=[
                                  (16, "16 heiltölubitar"), (24, "24 heiltölubitar"), (32, "32 fleytibitar")],
                              coerce=int,
                              description='Ef PCM er valið sem hljóðmerkjamál er sýnisstærðin 32 bitar sjálfgefið')
    audio_codec = SelectField("Hljóðmerkjamál",
                              choices=[("pcm", "PCM")])

    trim_threshold = FloatField("lágmarkshljóð (dB)",
                                [validators.NumberRange(min=0)],
                                default=40,
                                description="Þröskuldur sem markar þögn, því lægri því meira telst sem þögn. " +
                                "Þetta kemur bara af notum þegar sjálfvirk klipping er notuð. Hljóðrófsritið er desíbel-skalað.")
    too_low_threshold = FloatField("Lágmarkshljóð fyrir gæði (dB)",
                                   [validators.NumberRange(min=-100, max=0)],
                                   default=-15,
                                   description="Ef hljóðrófsrit upptöku fer aldrei yfir þennan þröskuld þá mun " +
                                   "gæðastjórnunarkerfi merkja þessa upptöku of lága. Athugið að hér er hljóðrófsritið skalað eftir styrk.")
    too_high_threshold = FloatField("Hámarkshljóð fyrir gæði (dB)",
                                    [validators.NumberRange(min=-100, max=0)],
                                    default=-4.5,
                                    description="Ef hljóðrófsrit upptöku fer yfir þennan þröskuld ákveðin fjölda af römmum í röð " +
                                    "þá mun gæðastjórnunarkerfi merkja þessa upptöku of háa. Athugið að hér er hljóðrófsritið skalað eftir styrk.")
    too_high_frames = IntegerField("Fjöldi of hárra ramma",
                                   [validators.NumberRange(min=0, max=100)],
                                   default=10,
                                   description="Segir til um hversu margir rammar i röð þurfa að vera fyrir ofan gæðastjórnunarþröskuldinn " +
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

PostingForm = model_form(Posting, db_session=db.session,
                         field_args={
                             "name": {"label": "Nafn"},
                             "ad_text": {"label": "Texti auglýsingar", "widget": widgets.TextArea()},
                             "utterances": {"label": "Setningar", "widget": widgets.TextArea()},
                         },
                         exclude=["id", "created_at", "uuid", "collection", "applications"])


class _TermsLazyLabel(object):
    """
    Lazy loadable label for the terms and agreements check field.
    Since app context is not available when forms are imported
    we need to lazy load the label.
    """
    def __repr__(self):
        return f'Ég samþykki <a href="{url_for("tos")}" target="_blank">skilmála og gagnastefnu LVL</a>'


class ApplicationForm(Form):
    name = StringField("Nafn", [validators.required()])
    sex = SelectField("Kyn", [validators.required()], choices=sex_choices)
    age = IntegerField("Aldur", [validators.required(),
                       validators.NumberRange(min=10, max=120)])
    voice = SelectField("Rödd", [validators.required()], choices=voice_choices)
    email = EmailField("Netfang", [validators.required()])
    phone = StringField("Sími")
    terms_agreement = BooleanField(_TermsLazyLabel(), validators=[InputRequired()]
    )
