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

COLORS = {
    'common': "#bdbdbd",
    'rare': "#42a5f5",
    'epic': "#7e57c2",
    'legendary': "#ffc107",
    'danger': "#ff4444",
    'primary': "#0275d8",
    'success': "#5cb85c",
    'info': "#5bc0de",
    'warning': "#f0ad4e",
    'lootarrows': "#ffee58",
    'diamond': "#ff4444",
}

ECONOMY = {
    'weekly_challenge': {
        'goal': 15000,
        'coin_reward': 100,
        'experience_reward': 500,
        'extra_interval': 2000,
        'extra_coin_reward': 50,
        'extra_experience_reward': 200,
        'best_coin_reward': 50,
        'best_experience_reward': 500,
    },
    'loot_boxes':{
        'prices':{
            '0': 100,
            '1': 200,
            '2': 300,
            '3': 400
        },
        'rarity_weights':{
            '0': 1,
            '1': 0.2,
            '2': 0.1,
            '3': 0.05,
        },
        'num_items': 3
    },
    'verification':{
        'coin_reward': 0,
        'experience_reward': 5
    },
    'session':{
        'coin_reward': 5,
        'experience_reward': 50,
    },
    'achievements':{
        'verification':{
            '0':{
                'title': 'Leiðangur hefst',
                'goal': 50,
                'coin_reward': 10,
                'experience_reward': 50,
                'fa_id': "fa fa-play"
            },
            '1':{
                'title': 'Upp á við',
                'goal': 500,
                'coin_reward': 50,
                'experience_reward': 100,
                'fa_id': "fa fa-check"
            },
            '2':{
                'title': 'Veggjaklifur',
                'goal': 1000,
                'coin_reward': 100,
                'experience_reward': 200,
                'fa_id': "fa fa-coins"
            },
            '3':{
                'title': 'Hástökk',
                'goal': 2000,
                'coin_reward': 200,
                'experience_reward': 300,
                'fa_id': "fa fa-gem"
            },
            '4':{
                'title': 'Everest',
                'goal': 5000,
                'coin_reward': 300,
                'experience_reward': 500,
                'fa_id': 'fa fa-crown',
            },
            '5':{
                'title': 'Út í geim',
                'goal': 15000,
                'coin_reward': 1000,
                'experience_reward': 10000,
                'fa_id': 'fa fa-user-astronaut',
            }
        }, 'spy':{
            '0':{
                'title': 'Spæjaraskólinn',
                'goal': 10,
                'coin_reward': 10,
                'experience_reward': 50,
                'fa_id': 'fa fa-search'
            },
            '1':{
                'title': 'A+ í spæjarafræðum',
                'goal': 50,
                'coin_reward': 50,
                'experience_reward': 100,
                'fa_id': 'fa fa-binoculars'
            },
            '2':{
                'title': 'Fyrsta spæjaravinnan',
                'goal': 100,
                'coin_reward': 100,
                'experience_reward': 500,
                'fa_id': 'fa fa-user-tie'
            },
            '3':{
                'title': 'Yfirmaður spæjaradeildarinnar',
                'goal': 200,
                'coin_reward': 500,
                'experience_reward': 1500,
                'fa_id': 'fa fa-user-secret'
            }
        },
        'streak_minimum': 500,
        'streak':{
            '0':{
                'title': 'Hlaupaskólinn',
                'goal': 1,
                'coin_reward': 10,
                'experience_reward': 50,
                'fa_id': 'fa fa-search'
            },
            '1':{
                'title': 'Hlaupaakademían',
                'goal': 2,
                'coin_reward': 50,
                'experience_reward': 100,
                'fa_id': 'fa fa-search'
            },
            '5':{
                'title': 'Hlaupaháskólinn',
                'goal': 2,
                'coin_reward': 50,
                'experience_reward': 100,
                'fa_id': 'fa fa-search'
            },
            '10':{
                'title': 'Hlaupaólympíuleikar',
                'goal': 2,
                'coin_reward': 50,
                'experience_reward': 100,
                'fa_id': 'fa fa-search'
            }
        }
    }
}

LOOT_BOXES = [
        {'rarity': 0, 'price': ECONOMY['loot_boxes']['prices']['0']},
        {'rarity': 0, 'price': ECONOMY['loot_boxes']['prices']['0']},
        {'rarity': 0, 'price': ECONOMY['loot_boxes']['prices']['0']},
        {'rarity': 1, 'price': ECONOMY['loot_boxes']['prices']['1']},
        {'rarity': 1, 'price': ECONOMY['loot_boxes']['prices']['1']},
        {'rarity': 2, 'price': ECONOMY['loot_boxes']['prices']['2']},
        {'rarity': 2, 'price': ECONOMY['loot_boxes']['prices']['2']},
        {'rarity': 3, 'price': ECONOMY['loot_boxes']['prices']['3']}
]