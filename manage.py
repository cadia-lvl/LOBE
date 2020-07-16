import getpass
import os
import re
import sys
import json
import traceback
from shutil import copyfile
from tqdm import tqdm

from flask_migrate import Migrate, MigrateCommand
from flask_script import Command, Manager
from flask_security.utils import hash_password
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from termcolor import colored
from collections import defaultdict

from app import app, db, user_datastore
from models import Recording, Token, User, Role, Collection, Configuration, Session, VerifierProgression, VerifierIcon, VerifierQuote, VerifierTitle
from tools.analyze import load_sample, signal_is_too_high, signal_is_too_low
from db import get_verifiers

migrate = Migrate(app, db)
manager = Manager(app)


class AddDefaultRoles(Command):
    def run(self):
        roles = [
            {
                "name": "admin",
                "description": 'Umsjónarhlutverk með aðgang að notendastillingum',
            },
            {
                "name": "Notandi",
                "description": 'Venjulegur notandi með grunn aðgang',
            },
            {
                "name": "Greinir",
                "description": 'Greinir með takmarkað aðgengi',
            },

        ]
        existing_roles = [role.name for role in Role.query.all()]
        for i, r in enumerate(roles):
            if r["name"] not in existing_roles:
                role = Role()
                role.name = r["name"]
                role.description = r["description"]
                db.session.add(role)
                print("Creating role:", r["name"])

        db.session.commit()


class AddDefaultConfiguration(Command):
    def run(self):
        main_conf = Configuration.query.filter_by(name='Aðalstilling')
        if main_conf:
            print("Configuration already exists.")
            return
        conf = Configuration()
        conf.name = 'Aðalstilling'
        db.session.add(conf)
        db.session.commit()


class AddUser(Command):
    def run(self):
        email = input("Email: ")
        name = input("Name: ")
        password = get_pw()

        roles = Role.query.all()
        selected_roles = []
        if len(roles) > 0:
            role_select = None
            while role_select not in [r.id for r in roles]:
                print(role_select, [r.id for r in roles])
                print("Select a role")
                role_select = int(input("".join(["[{}] - {} : {}\n".format(
                    role.id, role.name, role.description) for role in roles])))
            selected_roles.append(Role.query.get(role_select).name)
        with app.app_context():
            try:
                user_datastore.create_user(email=email, password=hash_password(password),
                    name=name, roles=selected_roles)
                db.session.commit()
                print("User with email {} has been created".format(email))
            except IntegrityError as e:
                print(e)


class changePass(Command):
    def run(self):
        email = input("Email: ")
        user = User.query.filter_by(email=email).all()
        assert len(user) == 1, "User with email {} was not found".format(email)
        user = user[0]
        password = get_pw()
        user.password = hash_password(password)
        db.session.commit()
        print("Password has been updated")


def get_pw(confirm=True):
    password = getpass.getpass("Password: ")
    if confirm:
        password_confirm = getpass.getpass("Repeat password: ")
        while password != password_confirm:
            print("Passwords must match")
            password = getpass.getpass("Password: ")
            password_confirm = getpass.getpass("Repeat password: ")
    return password


class changeDataRoot(Command):
    '''
    This can be used to change the recording and token tables
    to reflect changes in app.settings.DATA_BASE_DIR updates
    '''
    def run(self):
        change_all_recordings, change_all_tokens, skip_recording_exceptions = False, False, False
        rec_rxp = re.compile("{}\d+".format(app.config["RECORD_DIR"]))
        tkn_rxp = re.compile("{}/d+".format(app.config["TOKEN_DIR"]))

        print("The configured data directory is "+ colored("{}".format(app.config['DATA_BASE_DIR']), 'yellow'))
        print("Recording directory: " + colored("{}".format(app.config['RECORD_DIR']), 'yellow'))
        print("Token directory: " + colored("{}".format(app.config['TOKEN_DIR']), 'yellow'))

        recordings = Recording.query.all()
        for recording in recordings:
            if recording.path is None or not rec_rxp.match(os.path.dirname(recording.path)):
                print(colored("Updating path for {}".format(recording.get_printable_id()), 'red'))
                try:
                    if change_all_recordings:
                        recording.set_path()
                    else:
                        cont = input("{} will be changed to {} [y/n/all/cancel]?".format(
                            colored(recording.path, 'red'), colored(recording.get_configured_path(), 'green')))
                        if cont == 'y':
                            recording.set_path()
                        elif cont == 'all':
                            recording.set_path()
                            change_all_recordings = True
                        elif cont == 'cancel':
                            print("Quitting, no recording has been committed to database")
                            sys.exit()
                        else:
                            print("skipping")
                except Exception:
                    if not skip_recording_exceptions:
                        cont = input("""
                            This recording does not have collection set in the database and therefore
                            the path is also wrong. We cannot update this recording in the database. [continue/all/cancel] """)
                        if cont == 'cancel':
                            print("Quitting, no recording has been committed to database")
                            sys.exit()
                        elif cont =='all':
                            print("Will skip all exceptions and recordings will be unchanged in DB.")
                            skip_recording_exceptions = True
                    else:
                        print(colored("Skipping exception", 'red'))
            else:
                print(colored("Path correct", 'green'))
        db.session.commit()

        tokens = Token.query.all()
        for token in tokens:
            if token.path is None or not tkn_rxp.match(os.path.dirname(token.path)):
                print(colored("Updating path for {}".format(token.get_printable_id()), 'red'))
                if change_all_tokens:
                    token.set_path()
                else:
                    cont = input("{} will be changed to {} [y/n/all/cancel]: ".format(
                        colored(token.path, 'red'), colored(token.get_configured_path(), 'green')))
                    if cont == 'y':
                        token.set_path()
                    elif cont == 'all':
                        token.set_path()
                        change_all_tokens = True
                    elif cont == 'cancel':
                        print("Quitting, no token has been committed to database but recording paths have possibly been changed")
                        sys.exit()
                    else:
                        print("skipping")
            else:
                print(colored("Path correct", 'green'))
        db.session.commit()


@manager.command
def download_collection(collection_id, out_dir):
    '''
    Will create:
    * out_dir/audio/...
    * out_dir/text/...
    * out_dir/index.tsv
    * out_dir/info.json
    * out_dir/meta.json
    '''
    collection = Collection.query.get(collection_id)
    tokens = collection.tokens
    dl_tokens = []
    for token in tokens:
        if token.num_recordings > 0:
            dl_tokens.append(token)
    if not os.path.exists(out_dir):
        os.makedirs(os.path.join(out_dir, 'audio'))
        os.makedirs(os.path.join(out_dir, 'text'))
    index_f = open(os.path.join(out_dir, 'index.tsv'), 'w')

    user_ids = set()
    recording_info = {}
    try:
        for token in tqdm(dl_tokens):
            copyfile(token.get_path(),
                os.path.join(out_dir, 'text/{}'.format(token.get_fname())))
            for recording in token.recordings:
                if recording.get_path() is not None:
                    user_name = recording.get_user().name
                    user_ids.add(recording.user_id)
                    if not os.path.exists(os.path.join(out_dir, 'audio', user_name)):
                        os.makedirs(os.path.join(out_dir, 'audio', user_name))
                    copyfile(recording.get_path(),
                        os.path.join(out_dir, 'audio/{}/{}'.format(
                            user_name, recording.get_fname())))
                    recording_info[recording.id] = {
                        'collection_info':{
                            'recording_fname': recording.get_fname(),
                            'text_fname': token.get_fname(),
                            'text': token.text,
                            'user_name': user_name,
                            'user_id': recording.user_id,
                            'session_id': recording.session.id
                        },'recording_info':{
                            'sr': recording.sr,
                            'num_channels': recording.num_channels,
                            'bit_depth': recording.bit_depth,
                            'duration': recording.duration,
                        },'other':{
                            'transcription': recording.transcription,
                            'recording_marked_bad': recording.marked_as_bad,
                            'text_marked_bad': token.marked_as_bad}}
                    index_f.write('{}\t{}\n'.format(
                        user_name, recording.get_fname(), token.get_fname()))
                else:
                    print("Error - token {} does not have a recording".format(token.id))
        index_f.close()
        with open(os.path.join(out_dir, 'info.json'), 'w', encoding='utf-8') as info_f:
            json.dump(recording_info, info_f, ensure_ascii=False, indent=4)
        meta = {'speakers':[]}
        for id in user_ids:
            meta['speakers'].append(User.query.get(id).get_meta())
        meta['collection'] = collection.get_meta()
        with open (os.path.join(out_dir, 'meta.json'), 'w', encoding='utf-8') as meta_f:
            json.dump(meta, meta_f, ensure_ascii=False, indent=4)
        print("Done!, data available at {}".format(out_dir))
    except Exception as error:
        print("{}\n{}".format(error, traceback.format_exc()))


@manager.command
def update_session_verifications():
    '''
    Sets session.is_verified and session.is_secondarily_verified to False
    on all prior tuples in Session table
    '''
    sessions = Session.query.all()
    for session in tqdm(sessions):
        if session.is_verified is None:
            session.is_verified = False
        if session.is_secondarily_verified is None:
            session.is_secondarily_verified = False
    db.session.commit()

@manager.command
def release_unverified_sessions():
    '''
    To avoid double verification, a user id is attached to each
    session before it is verified. If a user repeatedly requests
    a session to verify without completing the verification the
    user hogs upp sessions and other users have no sessions to verify.
    This releases the user id from those sessions that have a user id
    but have not been fully verified.

    Note: this likely never happens as the hogging user will be
    queued with the first session with its user id.
    '''
    releasable_sessions = Session.query.filter(
        and_(Session.is_verified==False, Session.is_secondarily_verified==False))

    for session in releasable_sessions:
        session.verified_by = None
        session.secondarily_verified_by = None
    db.session.commit()


@manager.command
def update_numbers():
    '''
    Updates out-of-date values for the following columns in the Colleciton
    class:
        * num_tokens
        * num_recorded_tokens
        * num_invalid_tokens
    And the following of the Token class:
        * num_recordings
    '''
    recordings = Recording.query.all()
    token_recordings = defaultdict(int)

    for token in tqdm(Token.query.all()):
        token.num_recordings = 0

    for recording in tqdm(recordings):
        if recording.token_id is not None:
            token_recordings[recording.token_id] += 1
        else:
            print("Recording with id {} has no token id".format(recording.id))
    for token_id, num_recordings in token_recordings.items():
        token = Token.query.get(token_id)
        token.num_recordings = num_recordings
    db.session.commit()

    collections = Collection.query.all()
    for collection in tqdm(collections):
        collection.update_numbers()
    db.session.commit()


@manager.command
def set_dev_sessions():
    '''
    sets session.is_dev for all sessions on development collections
    '''
    dev_collections = Collection.query.filter(Collection.is_dev==True)
    for collection in dev_collections:
        for session in collection.sessions:
            session.is_dev = True
    db.session.commit()

@manager.command
def set_not_dev_sessions():
    '''
    sets session.is_dev for all sessions on non developmental collections
    '''
    non_dev_collections = Collection.query.filter(Collection.is_dev!=True)
    for collection in non_dev_collections:
        for session in collection.sessions:
            session.is_dev = False
    db.session.commit()


@manager.command
def set_not_dev_collections():
    '''
    Sets all collections as NOT developmental
    '''
    not_dev_collections = Collection.query.all()
    for collection in not_dev_collections:
        collection.is_dev = False
    db.session.commit()



@manager.command
def update_analysis():
    '''
    Performs analysis on all recordings that don't have analysis
    '''
    recordings = Recording.query.filter(Recording.analysis == None)
    for r in tqdm(recordings):
        # load the sample
        sample, _ = load_sample(r.path)
        # check the sample and return the response
        if signal_is_too_high(sample):
            r.analysis = 'high'
        elif signal_is_too_low(sample):
            r.analysis = 'low'
        else:
            r.analysis = 'ok'
    db.session.commit()


@manager.command
def update_collection_configuration():
    '''
    Sets the configuration of all non-configured
    collections to the default configuration
    '''
    try:
        default_config = Configuration.query.filter(
            Configuration.is_default==True)
    except MultipleResultsFound as e:
        print(e)
    except NoResultFound as e:
        print(e)
    collections = Collection.query.filter(Collection.configuration_id != None)
    for collection in collections:
        collection.configuration_id = default_config
    db.session.commit()


@manager.command
def debug_numbers(collection_id):
    '''
    Return a list of all tokens that have been recorded
    but do not have exactly one associated recording
    '''
    tokens = Collection.query.get(collection_id).tokens
    for token in tqdm(tokens):
        recordings = token.recordings
        if(len(recordings) > 0):
            if(len(recordings) != token.num_recordings):
                print(f'Token {token.id} has {token.num_recordings} but there are actually {len(recordings)}')
            elif(len(recordings) == 2):
                print(f'Token {token.id} has {len(recordings)}')
                print(' '.join(str(r.session_id) for r in recordings))


@manager.command
def add_missing_dirs():
    colls = Collection.query.all()
    for coll in colls:
        if not os.path.exists(coll.get_video_dir()):
            os.makedirs(coll.get_video_dir())
        if not os.path.exists(coll.get_wav_audio_dir()):
            os.makedirs(coll.get_wav_audio_dir())

@manager.command
def fix_verified_status():
    '''
    Use this if recordings are marked verified without verifications
    '''
    verified_recordings = Recording.query.filter(Recording.is_verified==True)
    for rec in verified_recordings:
        if len(rec.verifications) == 0:
            rec.is_verified = False
            session = Session.query.get(rec.session_id)
            session.is_verified = False
    db.session.commit()

    secondarily_verified_recordings = Recording.query.filter(Recording.is_secondarily_verified==True)
    for rec in secondarily_verified_recordings:
        if len(rec.verifications) < 2:
            rec.is_secondarily_verified = False
            session = Session.query.get(rec.session_id)
            session.is_secondarily_verified = False
    db.session.commit()

@manager.command
def add_progression_to_verifiers():
    verifiers = get_verifiers()
    for verifier in verifiers:
        if verifier.progression_id is None:
            progression = VerifierProgression()
            db.session.add(progression)
            db.session.flush()
            verifier.progression_id = progression.id
        db.session.commit()

@manager.command
def set_rarity():
    icons = VerifierIcon.query.all()
    titles = VerifierTitle.query.all()
    quotes = VerifierQuote.query.all()
    items = icons + titles + quotes
    for item in items:
        if item.rarity is None:
            item.rarity = 0
    db.session.commit()

@manager.command
def initialize_verifiers():
    add_progression_to_verifiers()
    verifiers = get_verifiers()
    for verifier in verifiers:
        progression = verifier.progression
        if progression.verification_level is None:
            progression.verification_level = 0
        if progression.spy_level is None:
            progression.spy_level = 0
        if progression.streak_level is None:
            progression.streak_level = 0
        if progression.num_verifies is None:
            progression.num_verifies = 0
        if progression.num_session_verifies is None:
            progression.num_session_verifies = 0
        if progression.num_invalid is None:
            progression.num_invalid = 0
        if progression.num_streak_days is None:
            progression.num_streak_days = 0
        if progression.lobe_coins is None:
            progression.lobe_coins = 0
        if progression.experience is None:
            progression.experience = 0
        if progression.weekly_verifies is None:
            progression.weekly_verifies = 0
        if progression.last_spin is None:
            progression.last_spin = db.func.current_timestamp()
        if progression.fire_sale is None:
            progression.fire_sale = False
        if progression.fire_sale_discount is None:
            progression.fire_sale_discount = 0.0
    db.session.commit()

@manager.command
def give_coins():
    verifiers = get_verifiers()
    print("Select a verifier id from the ones below:")
    for verifier in verifiers:
        print(f'{verifier.name} - [{verifier.id}]')
    user_id = int(input('user id: '))
    coins = int(input('amount: '))
    user = User.query.get(user_id)
    progression = user.progression
    progression.lobe_coins += coins
    db.session.commit()

@manager.command
def give_all_coins():
    verifiers = get_verifiers()
    coins = int(input('amount: '))
    for verifier in verifiers:
        progression = verifier.progression
        progression.lobe_coins += coins
        db.session.commit()

@manager.command
def give_experience():
    verifiers = get_verifiers()
    print("Select a verifier id from the ones below:")
    for verifier in verifiers:
        print(f'{verifier.name} - [{verifier.id}]')
    user_id = int(input('user id: '))
    experience = int(input('amount: '))
    user = User.query.get(user_id)
    progression = user.progression
    progression.experience += experience
    db.session.commit()

@manager.command
def reset_weekly_challenge():
    verifiers = get_verifiers()
    best_verifier = sorted(verifiers, key=lambda v: -v.progression.weekly_verifies)[0]

    # check for price and award
    coin_price, experience_price = 0, 0
    weekly_verifies = sum([v.progression.weekly_verifies for v in verifiers])
    weekly_goal = app.config['ECONOMY']['weekly_challenge']['goal']
    if weekly_verifies > weekly_goal:
        coin_price = app.config['ECONOMY']['weekly_challenge']['coin_reward']
        experience_price = app.config['ECONOMY']['weekly_challenge']['experience_reward']

        extra = int((weekly_verifies-weekly_goal)/app.config['ECONOMY']['weekly_challenge']['extra_interval'])
        coin_price += extra*app.config['ECONOMY']['weekly_challenge']['extra_coin_reward']
        experience_price += extra*app.config['ECONOMY']['weekly_challenge']['extra_experience_reward']

    # give prices and reset counters
    for verifier in verifiers:
        v_coin_price, v_experience_price = coin_price, experience_price
        if verifier.id == best_verifier.id:
            v_coin_price += app.config['ECONOMY']['weekly_challenge']['best_coin_reward']
            v_experience_price += app.config['ECONOMY']['weekly_challenge']['best_experience_reward']

        progression = verifier.progression
        progression.weekly_verifies = 0
        progression.lobe_coins += coin_price
        progression.experience += experience_price
        progression.weekly_coin_price = coin_price
        progression.weekly_experience_price = experience_price
        progression.has_seen_weekly_prices = False

    db.session.commit()


@manager.command
def set_firesale():
    do_fire_sale = bool(int(input('Do 1 for firesale, 0 to deactivate: ')))
    if do_fire_sale:
        fire_sale_discount = float(input('Select discount, e.g. 0.3 for 30 percent off: '))
    else:
        fire_sale_discount = 0.0

    verifiers = get_verifiers()
    for verifier in verifiers:
        progression = verifier.progression
        progression.fire_sale = do_fire_sale
        progression.fire_sale_discount = fire_sale_discount

    db.session.commit()



manager.add_command('db', MigrateCommand)
manager.add_command('add_user', AddUser)
manager.add_command('change_pass', changePass)
manager.add_command('change_dataroot', changeDataRoot)
manager.add_command('add_default_roles', AddDefaultRoles)
manager.add_command('add_default_configuration', AddDefaultConfiguration)

if __name__ == '__main__':
    manager.run()
