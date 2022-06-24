# to initialize the lib
./scripts/init

# to publish if there's changes
tox || ./scripts/bump-and-publish

# manually
PYTHONPATH=$PYTHONPATH:./ ./scripts/bump-version.py
PYTHONPATH=$PYTHONPATH:./ ./scripts/inline-lib.py
./scripts/publish