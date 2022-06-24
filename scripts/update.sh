tox || echo "TESTS FAILED! aborting..." && exit 1
PYTHONPATH=$PYTHONPATH:./ ./scripts/bump-version.py
PYTHONPATH=$PYTHONPATH:./ ./scripts/inline-lib.py
./scripts/publish.sh
