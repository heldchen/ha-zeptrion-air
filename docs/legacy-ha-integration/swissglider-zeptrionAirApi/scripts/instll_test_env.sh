#  ============================
#  Init
#  ============================
virtualenv venv
. venv/bin/activate
pip install -U pip setuptools twine wheel readme_renderer

#  ============================
#  Install for development
#  ============================
python setup.py develop

#  ============================
#  Build
#  ============================
# python setup.py sdist
# twine upload dist/*

#  ============================
#  Deactivate
#  ============================
# deactivate