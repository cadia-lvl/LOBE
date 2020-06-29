# L.O.B.E.
LOBE is a recording client made specifically for TTS data collections. It supports multiple collections, single and multi-speaker, and can prompt sentences based on phonetic coverage.

# Setup
* Other system requirements (installed via apt):
    * postgresql
    * python-psycopg2
    * libpq-dev
    * libffi-dev

* Install Python requirements using `pip3 install -r requirements.txt`
    * ffmpeg (or avconv)

* Create a Postgres database. Relevant parameters need to be supplied to the flask via the setting files at `settings/development.py` or `settings/production.py`.
* Spin up a simple development server using `./dev.sh`.
    * Use `SEMI_PROD=True` to use `avconc` instead of `ffmpeg`
# Creating a development database
Start by creating a databese and a user:

```
# Log in as postgres user
sudo -u postgres -i
# Create role for lobe and select password
createuser lobe --pwprompt
# Create lobe database with the new user as owner
createdb lobe --owner=lobe
```
Remember to change settings/development.py accordingly. Replace all the values in \<BRACKETS\> with the postgres information you created just now.
`SQLALCHEMY_DATABASE_URI = 'postgresql://<POSTGRES-USERNAME>:<POSTGRES-PWD>@localhost:5432/<DATABASENAME>'`

Finally run `python manage.py db upgrade`

To add defaults to the database run:

```
python manage.py add_default_roles
python manage.py add_default_configuration
```

Create a super user with `python manage.py add_user`

# Backing up & restoring
1. Create a new database.
    1. sudo su postgres
    2. psql
    3. CREATE DATABASE <name>;
    4. GRANT ALL PRIVILEGES ON DATABASE <name> TO <db_user>;

2. Create a database dump of the previous database
    1. su <lobe_linux_user>
    2. pg_dump <old_db_name> > <old_db_name>.sql

3. Migrate the schema to the new database
    1. In settings.<env_name>.py add <name> as the new database name
    2. run `python3 manage.py db upgrade`
    3. sudo su postgres
    4. try to restore from the backup with psql <name> < <old_db_name>.sql

4. If that didn't work the following is perhaps helpful
    1. Rename the migrations folder to e.g. `migrations_old`
    2. Recreate the new database by e.g. DROP DATABASE <name> and then create.
    3. Try to restore from the same backup as before

5. If that didn't work, try this
    1. Recreate a fresh database and run python3 manage.py db init and then run migrates to get schema updates on new database.
    2. Try creating a dump using `pg_dump -U <user> -Fc '<old_db_name>' > <old_db_name>.dump`
    3. Restore one table at a time using only data :`pg_restore -U <user> --data-only -d <new_db_name> -t <table> <old_db_name>.dump`
    4. Finally restore each sequence by first listing the sequences of the connected database with `\ds`
    5. For each table do SELECT max(id) from <table>;
    6. Then alter each sequence with ALTER SEQUENCE <sequence_name> RESTART WITH value+1;
