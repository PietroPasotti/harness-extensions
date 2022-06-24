#!/usr/bin/env bash
LIB_V=${LIB_VERSION:-$LIB_VERSION}
charmcraft publish-lib "charms.$LIB_NAME.$LIB_V.$LIB_NAME"  # $ TEMPLATE: Filled in by ./scripts/init.sh
