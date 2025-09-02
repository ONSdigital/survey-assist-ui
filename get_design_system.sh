#!/bin/sh

set -e

TMPFILE=`mktemp ./templates.XXXXXXXXXX`

wget https://github.com/ONSdigital/design-system/releases/download/72.9.1/templates.zip -O $TMPFILE
rm -rf survey_assist_ui/templates/components
rm -rf survey_assist_ui/templates/layout

unzip -d ./survey_assist_ui $TMPFILE
rm $TMPFILE