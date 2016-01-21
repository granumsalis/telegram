#!/bin/bash -eux

VENV_DIR=venv
PIP=$VENV_DIR/bin/pip
PIP_PACKAGES="requests pony parse pdfkit pyslack-real python-telegram-bot"

sudo apt install python-pip python-virtualenv
sudo apt-get --reinstall install python-pyasn1 python-pyasn1-modules

virtualenv --no-site-packages --prompt="(granumsalis)" $VENV_DIR

$PIP install pyasn1
$PIP install $PIP_PACKAGES

#source $VENV_DIR/bin/activate
#deactivate
