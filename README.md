# Setup
* Install Python requirements using `pip3 install -r requirements.txt`
* Other system requirements (installed via apt):
    * postgresql
    * python-psycopg2
    * libpq-dev
* Create a Postgres database. Relevant parameters need to be supplied to the flask via the setting files at `settings/development.py` or `settings/production.py`.
* Spin up a simple development server using `./dev.sh`.