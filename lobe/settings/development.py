from lobe.settings.common import *

SECRET_KEY = 'CHANGE_THIS'
SECURITY_PASSWORD_SALT = 'SOME_SALT'

RECAPTCHA_PUBLIC_KEY = '6Lcan7IUAAAAACXrZazA4OeWJ2ZAC1DdxgNK8wUX'
RECAPTCHA_PRIVATE_KEY = '6Lcan7IUAAAAANSmBbECrHlpz5EzSqNVX4uDiwH4'

SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:password@localhost:5432/lobe_dev_db_4'

TAL_API_TOKEN = 'ak_JLedkaWqqORPpYByLXeZjMG4JN0rQkwZ4zn6zg28WmvE57oK9badDAlV12PY5Xo0'

DEBUG = True
FLASK_DEBUG = True

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
            '3': 200
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
                'title': 'Mt. Fuji',
                'goal': 15000,
                'coin_reward': 1300,
                'experience_reward': 1500,
                'fa_id': 'fa fa-thumbs-up',
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
                'title': 'Spæjaraskólinn',
                'goal': 50,
                'coin_reward': 50,
                'experience_reward': 100,
                'fa_id': 'fa fa-search'
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