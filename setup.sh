#!/bin/bash
# Prerequisite: sudo apt-get install libjpeg-dev
type virtualenv >/dev/null 2>&1 || { echo >&2 "setup.sh requires virtualenv, but it's not installed. Aborting."; exit 1; }
virtualenv flask
flask/bin/pip install -r requirements.txt
