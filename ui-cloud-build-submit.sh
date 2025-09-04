#!/bin/bash
#
# Submit a Cloud Build for the Survey Assist UI

set -e

UI_VERSION=$(poetry version -s)
GIT_SHA=$(git rev-parse --short=12 HEAD)
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "Files for upload: $(gcloud meta list-files-for-upload | tr '\n' ' ')"

echo "Submitting Cloud Build for Survey Assist UI using:"
echo "  IMAGE: $UI_IMAGE_NAME:$UI_VERSION"
echo "  REGION: $REGION"
echo "  CICD_PROJECT_ID: $CICD_PROJECT_ID"
echo "  CICD_CLOUD_BUILD_SA: $CICD_CLOUD_BUILD_SA"
echo "  CICD_CLOUD_BUILD_BUCKET: $CICD_CLOUD_BUILD_BUCKET"
echo "  DEPLOY_PROJECT_ID: $DEPLOY_PROJECT_ID"
echo "  UI_GAR: $UI_GAR"
echo "  GIT_SHA: $GIT_SHA"
echo "  BUILD_DATE: $BUILD_DATE"

# check if user would like to proceed
read -p "Do you want to proceed with the Cloud Build submission? (y/n) " -n 1 -r
echo    # move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborting Cloud Build submission."
  exit 1
fi

gcloud builds submit --config cloudbuild.yaml \
    --project $CICD_PROJECT_ID \
    --region $REGION \
    --service-account $CICD_CLOUD_BUILD_SA \
    --substitutions _REGION=$REGION,_ARTIFACT_REPO_NAME=$UI_GAR,_IMAGE_NAME=$UI_IMAGE_NAME,_IMAGE_TAG=$UI_VERSION,_DEPLOY_PROJECT_ID=$DEPLOY_PROJECT_ID,_BUILD_DATE=$BUILD_DATE,_GIT_SHA=$GIT_SHA\
    --gcs-source-staging-dir gs://$CICD_CLOUD_BUILD_BUCKET/$UI_IMAGE_NAME/$UI_VERSION