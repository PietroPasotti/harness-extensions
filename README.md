# how to use this template

Cd to the template root dir.

- run `scripts/init.sh <CHARM_NAME> <LIB_NAME> [<LIB_VERSION>]`

This will 
 - Register a charm with name LIB_NAME
 - Initialize a library called LIB_NAME (with version LIB_VERSION or v0 if not provided)
   - Grab the LIBID
   - Use LIBID and the other variables to populate: 
     - `metadata.yaml`
     - `tox.ini`
     - `lib_template.jinja`
     - `scripts/init.sh`
     - `scripts/inline-lib.py`
     - `scripts/publish.sh`
   - Create `./<LIB_NAME>.py`

After that, you should put your lib code in `./<LIB_NAME>.py`
When you're ready to publish the lib for the first time, 
you should run `scripts/inline-lib.py && scripts/publish.sh`

All subsequent times, if you want to publish a new revision, you can run `scripts/update.sh`.
This will 
 - Bump the revision
 - Inline the lib
 - Publish the lib

When you bump to a new (major) version, you'll have to manually change the 
value of `$LIB_V` in `scripts/publish.sh`.
