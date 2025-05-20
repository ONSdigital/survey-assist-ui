#!/bin/sh

set -e

TMPFILE=`mktemp ./templates.XXXXXXXXXX`

wget https://github.com/ONSdigital/design-system/releases/download/72.9.1/templates.zip -O $TMPFILE
rm -rf ui/templates/components
rm -rf ui/templates/layout

unzip -d ./ui $TMPFILE
rm $TMPFILE