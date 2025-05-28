#!/bin/sh

echo "  ### flake8 test - "+$1
flake8 $1

echo "  ### pydocstyle test - "+$1
pydocstyle $1

echo "  ### pycodestyle --show-source --show-pep8  test - "+$1
pycodestyle --show-source --show-pep8 $1

echo "  ### pycodestyle --first test - "+$1
pycodestyle --first $1

echo "  ### pylint 3.6 test - "+$1
# /Users/diener/Library/Python/3.6/bin/pylint ../zeptrion_air_api
pylint ./zeptrion_air_api
# python -m pylint /data/test.py

echo "  ### python3 setup.py test"
python3 setup.py test

echo "  ### pytest and coverage"
py.test --cov ./zeptrionAirApi

# py.test -s --cov-report html --cov ../zeptrionAirApi
