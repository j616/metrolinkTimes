#!/usr/bin/env bash

# Errors cause this script to exit immediately
set -e

# Sets the working directory to the repository root
# This makes it safe to call this script from anywhere
pushd "$(dirname "$(readlink -f "$0")")/.." > /dev/null

# Clean and build the Python package
rm -rf dist docker/dist
poetry build --format sdist

# Copy the built page to the docker context
cp -rf dist/ docker/

# We want to install the exact same dependencies every build
# Let poetry export a list of all dependencies to a format that Pip can use
poetry export --without-hashes -f requirements.txt -o docker/requirements.txt

# Reset the working directory (mirrors pushd)
popd > /dev/null