#!/usr/bin/env bash
LIB_V=${LIB_VERSION:-v0}
charmcraft publish-lib "charms.harness_extensions.$LIB_V.$1"
