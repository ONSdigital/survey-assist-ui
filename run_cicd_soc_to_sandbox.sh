#!/bin/bash

# This script is only intended for use in the Sandbox environment.
#
# Please set the environment variable CICD_PROJECT_ID i.e. export CICD_PROJECT_ID=
ENV_NAME=sandbox # Sandbox use only

if [[ ! -v CICD_PROJECT_ID ]]; then 
   echo "Please set the environment variable CICD_PROJECT_ID i.e. export CICD_PROJECT_ID="
   exit 1
fi

ENV_NAME=sandbox # Sandbox use only

GIT_SHA=$(git rev-parse --short HEAD)
API_VERSION="v1"
sandbox_config=$(gcloud parametermanager parameters versions describe $ENV_NAME --parameter=infra-test-config --location=global --project $CICD_PROJECT_ID --format=json | python3 -c "import sys, json; print(json.load(sys.stdin)['payload']['data'])" | base64 --decode)
PROJECT_ID=$(echo $sandbox_config | python3 -c "import sys, json; print(json.load(sys.stdin)['project-id'])")
CICD_SA=$(echo $sandbox_config | python3 -c "import sys, json; print(json.load(sys.stdin)['cicd-sa-email'])")
CR_BUCKET=$(echo $sandbox_config | python3 -c "import sys, json; print(json.load(sys.stdin)['cr-bucket'])")
REGION=$(echo $sandbox_config | python3 -c "import sys, json; print(json.load(sys.stdin)['region'])")

OTP_URL=$(echo $sandbox_config | python3 -c "import sys, json; print(json.load(sys.stdin)['cr-otp-api-url'])") # ok
API_URL=$(echo $sandbox_config | python3 -c "import sys, json; print(json.load(sys.stdin)['cr-api-url'])") # ok

API_SA_EMAIL=$(echo $sandbox_config | python3 -c "import sys, json; print(json.load(sys.stdin)['apigw-sa-email'])")
 
# _BACKEND_SA_EMAIL should be backend-api-access@survey-assist-sandbox.iam.gserviceaccount.com

# NEW Params required:
PROXY_API_URL="https://proxy-api-670504361336.europe-west2.run.app"
GAR_IMAGE="europe-west2-docker.pkg.dev/survey-assist-sandbox/survey-assist-ui/survey-assist-ui"

CB_BUCKET=gs://${PROJECT_ID}_cloudbuild/survey-assist-ui

gcloud beta builds submit . --config=cicd/cloudbuild_dev_and_sandbox.yaml \
	--project $CICD_PROJECT_ID \
	--service-account projects/$CICD_PROJECT_ID/serviceAccounts/$CICD_SA \
	--gcs-source-staging-dir $CB_BUCKET \
	--substitutions=_ENV_NAME=$ENV_NAME,SHORT_SHA=$GIT_SHA,_API_VERSION=$API_VERSION,_BACKEND_API_URL=$API_URL,_BACKEND_SA_EMAIL=$API_SA_EMAIL,_GAR_IMAGE=$GAR_IMAGE,_PROXY_API_URL=$PROXY_API_URL,_GUNICORN_WORKERS=6,_TARGET_PROJECT_ID=$PROJECT_ID,_VERIFY_API_URL=$OTP_URL \
	--region $REGION

#_BACKEND_API_URL=https://survey-assist-api-670504361336.europe-west2.run.app
#_BACKEND_SA_EMAIL=backend-api-access@survey-assist-sandbox.iam.gserviceaccount.com
# -> _GAR_IMAGE=europe-west2-docker.pkg.dev/survey-assist-sandbox/survey-assist-ui/survey-assist-ui
#_GUNICORN_WORKERS=6
#_TARGET_PROJECT_ID=survey-assist-sandbox
# -> _UI_SA_EMAIL=survey-ui-cloud-run@survey-assist-sandbox.iam.gserviceaccount.com
#_VERIFY_API_URL=https://firestore-otp-api-670504361336.europe-west2.run.app