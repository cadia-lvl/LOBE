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
from sqlalchemy.exc import IntegrityError
from termcolor import colored
from collections import defaultdict

from app import app, db, user_datastore
from models import Recording, Token, User, Role, Collection

migrate = Migrate(app, db)
manager = Manager(app)

class AddDefaultRoles(Command):
    def run(self):
        admin_role = Role()
        admin_role.name = 'admin'
        admin_role.description = 'Umsjónarhlutverk með aðgang að notendastillingum'

        user_role = Role()
        user_role.name = 'Notandi'
        user_role.description = 'Venjulegur notandi með grunn aðgang'

        db.session.add(admin_role)
        db.session.add(user_role)
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
def download_collection(coll_id, out_dir):
    '''
    Will create:
    * out_dir/audio/...
    * out_dir/text/...
    * out_dir/index.tsv
    * out_dir/info.json
    * out_dir/meta.json
    '''
    collection = Collection.query.get(coll_id)
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
        token_recordings[recording.token_id] += 1
    for token_id, num_recordings in token_recordings.items():
        token = Token.query.get(token_id)
        token.num_recordings = num_recordings
    db.session.commit()

    collections = Collection.query.all()
    for collection in tqdm(collections):
        collection.update_numbers()
    db.session.commit()

manager.add_command('db', MigrateCommand)
manager.add_command('adduser', AddUser)
manager.add_command('changepass', changePass)
manager.add_command('changedataroot', changeDataRoot)
manager.add_command('adddefaultroles', AddDefaultRoles)

if __name__ == '__main__':
    manager.run()
