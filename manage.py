from flask_script import Manager, Command
from flask_migrate import Migrate, MigrateCommand
from app import app, db, user_datastore
import getpass
from sqlalchemy.exc import IntegrityError

class AddUser(Command):
    def run(self):
        email = input("Email: ")
        password = getpass.getpass("Password: ")
        with app.app_context():
            try:
                user_datastore.create_user(email=email, password=password)
                db.session.commit()
                print("User with email {} has been created".format(email))
            except IntegrityError as e:
                print(e)


migrate = Migrate(app, db)
manager = Manager(app)

manager.add_command('db', MigrateCommand)
manager.add_command('adduser', AddUser)

if __name__ == '__main__':
    manager.run()