# Howler Client Library

The Howler client library facilitates issuing requests to Howler.

## Requirements

1. Python 3.9 and up

## Running the Tests

1. Prepare the howler-api:
   1. Start dependencies
   1. `howler-api > python howler/app.py`
   1. `howler-api > python howler/odm/random_data.py`
2. Run python integration tests:
   1. `python -m venv env`
   1. `. env/bin/activate`
   1. `pip install -r requirements.txt`
   1. `pip install -r test/requirements.txt`
   1. `pip install -e .`
   1. `pytest -s -v test`

## \_sqlite3 error

You'll likely have to reinstall python3.9 while libsqlite3-dev is installed

1. libsqlite3-dev
   `sudo apt install libsqlite3-dev`
2. Python3.9 with loadable-sqlite-extensions enabled
   - `./configure --enable-loadable-sqlite-extensions --enable-optimizations`
   - `make altinstall`
