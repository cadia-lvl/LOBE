import getpass
import os
import re
import sys

from flask_migrate import Migrate, MigrateCommand
from flask_script import Command, Manager
from flask_security.utils import hash_password
from sqlalchemy.exc import IntegrityError
from termcolor import colored

from app import app, db, user_datastore
from models import Recording, Token, User, Role

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

class changeDataRoot(Command):
    '''
    This can be used to change the recording and token tables
    to reflect changes in app.settings.DATA_BASE_DIR updates
    '''
    def run(self):
        change_all_recordings, change_all_tokens = False, False
        rec_rxp = re.compile("{}\d+".format(app.config["RECORD_DIR"]))
        tkn_rxp = re.compile("{}/d+".format(app.config["TOKEN_DIR"]))

        print("The configured data directory is "+ colored("{}".format(app.config['DATA_BASE_DIR']), 'yellow'))
        print("Recording directory: " + colored("{}".format(app.config['RECORD_DIR']), 'yellow'))
        print("Token directory: " + colored("{}".format(app.config['TOKEN_DIR']), 'yellow'))

        recordings = Recording.query.all()
        for recording in recordings:
            if recording.path is None or not rec_rxp.match(os.path.dirname(recording.path)):
                print(colored("Updating path for {}".format(recording.get_printable_id()), 'red'))
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
                        print("Quitting, no recording has beeb committed to database")
                        sys.exit()
                    else:
                        print("skipping")
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
                        print("Quitting, no token has beeb committed to database but recording paths have possibly been changed")
                        sys.exit()
                    else:
                        print("skipping")
            else:
                print(colored("Path correct", 'green'))
        db.session.commit()

def get_pw(confirm=True):
    password = getpass.getpass("Password: ")
    if confirm:
        password_confirm = getpass.getpass("Repeat password: ")
        while password != password_confirm:
            print("Passwords must match")
            password = getpass.getpass("Password: ")
            password_confirm = getpass.getpass("Repeat password: ")
    return password


migrate = Migrate(app, db)
manager = Manager(app)

manager.add_command('db', MigrateCommand)
manager.add_command('adduser', AddUser)
manager.add_command('changepass', changePass)
manager.add_command('changedataroot', changeDataRoot)
manager.add_command('adddefaultroles', AddDefaultRoles)

if __name__ == '__main__':
    manager.run()
