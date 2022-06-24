#!/usr/bin/env bash
CHARM_NAME=$1
LIB_NAME=$2
LIB_VERSION="${3:-v0}"

[ -z "$LIB_NAME" ] && echo "need to provide LIB_NAME as first argument" && exit 1
[ -z "$CHARM_NAME" ] && echo "need to provide CHARM_NAME as second argument" && exit 1

LIB_NAME=${LIB_NAME/-/_} # to be safe...

echo "will initialize charm lib ${CHARM_NAME}:${LIB_NAME} (${LIB_VERSION})"

function fill_in() {
    echo "$3:: replacing $1 -> $2"
    sed -i "s/$1/$2/g" "$3"
}

# populate templates
fill_in "\$LIB_NAME" "$LIB_NAME" "./scripts/publish.sh"
fill_in "\$CHARM_NAME" "$CHARM_NAME" "./scripts/publish.sh"
fill_in "\$LIB_VERSION" "$LIB_VERSION" "./scripts/publish.sh"

fill_in "\$LIB_NAME" "$LIB_NAME" "./scripts/inline-lib.py"
fill_in "\$CHARM_NAME" "$CHARM_NAME" "./scripts/inline-lib.py"

fill_in "\$LIB_NAME" "$LIB_NAME" "./metadata.yaml"
fill_in "\$CHARM_NAME" "$CHARM_NAME" "./metadata.yaml"
fill_in "\$LIB_NAME" "$LIB_NAME" "./tox.ini"

echo "registering charm $CHARM_NAME"
# create the 'charm' placeholder
charmcraft register "$CHARM_NAME"

echo "registering lib $LIB_NAME"
# register the lib to that charm
charmcraft create-lib "$LIB_NAME"
# create the source file for the lib
touch  "./$LIB_NAME.py"

CHARM_PATH=${CHARM_NAME/-/_}
# extract LIBID
LIBID_RAW=$(cat "./lib/charms/$CHARM_PATH/$LIB_VERSION/$LIB_NAME.py" | grep LIBID)
LIBID=${LIBID_RAW#*LIBID = }

fill_in "\$LIBID" "$LIBID" "lib_template.jinja"

# get rid of the lib file
rm "./lib/charms/$CHARM_PATH/$LIB_VERSION/$LIB_NAME.py"

echo "lib ready at lib/charms/$CHARM_PATH/$LIB_VERSION/$LIB_NAME! Happy coding."