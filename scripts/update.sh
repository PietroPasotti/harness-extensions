tox ./libs/"$1"

if [ $? -eq 0 ]; then
  PYTHONPATH=$PYTHONPATH:./ ./scripts/bump-version.py "$1"
  PYTHONPATH=$PYTHONPATH:./ ./scripts/inline-lib.py "$1"
  ./scripts/publish.sh $1
else
    echo "TESTS FAILED! aborting..."
fi

