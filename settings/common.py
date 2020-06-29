import os

APP_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir))

# these should all have a trailing slash
DATA_BASE_DIR = os.path.join(APP_ROOT, 'data/')
TOKEN_DIR = os.path.join(DATA_BASE_DIR, 'tokens/')
RECORD_DIR = os.path.join(DATA_BASE_DIR, 'records/')
VIDEO_DIR = os.path.join(DATA_BASE_DIR, 'videos/')
ZIP_DIR = os.path.join(DATA_BASE_DIR, 'zips/')
TEMP_DIR = os.path.join(DATA_BASE_DIR, 'temp/')
WAV_AUDIO_DIR = os.path.join(DATA_BASE_DIR, 'wav_audio/')

OTHER_PATH = os.path.join(APP_ROOT, 'other')
MANUAL_FNAME = 'LOBE_manual.pdf'

TOKEN_PAGINATION = 500
VERIFICATION_PAGINATION = 100
RECORDING_PAGINATION = 20
COLLECTION_PAGINATION = 20
USER_PAGINATION = 30
SESSION_PAGINATION = 50
CONF_PAGINATION = 30

SESSION_SZ = 50

RECAPTCHA_USE_SSL = False
RECAPTCHA_DATA_ATTRS = {'theme':'dark'}

SQLALCHEMY_TRACK_MODIFICATIONS = False

# DEFAULT MEDIA PARAMETERS
# not used currently
AUDIO_CODEC = 'pcm'
VIDEO_W = 1280
VIDEO_H = 720
VIDEO_CODEC = 'vp8'
