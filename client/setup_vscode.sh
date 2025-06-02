#!/bin/sh -x

cd python
python3 -m venv env
. env/bin/activate
pip install -U pip
pip install -U wheel
pip install -U pytest pytest-cov codecov flake8 pep8 autopep8 ipython cart passlib howler
pip install -e .
