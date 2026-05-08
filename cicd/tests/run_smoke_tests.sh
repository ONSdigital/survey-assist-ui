#!/bin/bash

# Wrapper script to run the smoke tests locally
#
# Expected Env variables: 
# SURVEY_ASSIST_UI_URL - The URL of the Survey Assist UI to run the tests against
# SA_ID_TOKEN - A valid Google Identity Token generated from your credentials (assuming you're running locally) 
#
#
# Expected parameter: [sandbox|dev]
#
# Example ./run_smoke_tests.sh dev

if [[ $1 = "sandbox" ]] || [[ $1 = "dev" ]]; then
   echo Test environment "$1"
else
  echo "Please pass test environment of 'sandbox' or 'dev' e.g. ./run_smoke_tests.sh sandbox"
  exit 1
fi

if [[ -z "${SURVEY_ASSIST_UI_URL}" ]]; then
    echo Environment variable SURVEY_ASSIST_UI_URL was not set, getting $1 url from parameter store:
    # TODO This needs to be the address of the proxy-api
    #SURVEY_ASSIST_UI_URL=$(gcloud parametermanager parameters versions describe $1 --parameter=infra-test-config --location=global --project ons-cicd-surveyassist --format=json | python3 -c "import sys, json; print(json.load(sys.stdin)['payload']['data'])" | base64 --decode | python3 -c "import sys, json; print(json.load(sys.stdin)['alb-survey-url'])")
    SURVEY_ASSIST_UI_URL="https://proxy-api-670504361336.europe-west2.run.app" # TOTO get from paremeter store for each env
    export SURVEY_ASSIST_UI_URL
    echo "$SURVEY_ASSIST_UI_URL"
else
    echo Using SURVEY_ASSIST_UI_URL="$SURVEY_ASSIST_UI_URL"
fi
#
# Example way to set token after gcloud auth login
# export SA_ID_TOKEN=`gcloud auth print-identity-token`
if [[ -z "${UI_SA_ID_TOKEN}" ]]; then
    echo Environment variable SA_ID_TOKEN was not set, getting a new identity token from local credentials, if authenticated.
    UI_SA_ID_TOKEN=$(gcloud auth print-identity-token)   
    export UI_SA_ID_TOKEN 
else
    echo Using currently set SA_ID_TOKEN. If this becomes stale, run export UI_SA_ID_TOKEN=\`gcloud auth print-identity-token\`
fi

if [[ -z "${GIT_SHORT_SHA}" ]]; then
    echo Environment variable GIT_SHORT_SHA was not set.
    export GIT_SHORT_SHA 
else
    echo Using currently set GIT_SHORT_SHA=$GIT_SHORT_SHA.
fi
pytest -s