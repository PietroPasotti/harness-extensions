tox ./libs/"$1" || echo "TESTS FAILED! aborting..." && exit 1
PYTHONPATH=$PYTHONPATH:./ ./scripts/bump-version.py "$1"
PYTHONPATH=$PYTHONPATH:./ ./scripts/inline-lib.py "$1"
./scripts/publish.sh $1
