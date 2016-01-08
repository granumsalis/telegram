#!/bin/bash -eux

VENV_DIR=venv
PIP=$VENV_DIR/bin/pip
PIP_PACKAGES="requests pony parse pdfkit pyslack-real python-telegram-bot"

virtualenv --no-site-packages --prompt="(granumsalis)" $VENV_DIR

$PIP install $PIP_PACKAGES

#source $VENV_DIR/bin/activate
#deactivate
