# Survey Assist UI

## Overview

User interface for Survey Assist backend implemented in Flask using the ONS Design System.  

## Features

- Flask web interface. This interface will be used to mock a survey interface that can interact with Survey Assist to generate dynamic content and make in-line decisions based from user input.
- Deployed in GCP using Terraform
- Uses the following cloud services:
  - Cloud Run
  - Load Balancer
  - Cloud Armour
  - Supports JWT Authentication with backend API
  - CI/CD pipeline for automated deployment

## Prerequisites

Ensure you have the following installed on your local machine:

- [ ] Python 3.12 (Recommended: use `pyenv` to manage versions)
- [ ] `poetry` (for dependency management)
- [ ] Colima (if running locally with containers)
- [ ] Terraform (for infrastructure management)
- [ ] Google Cloud SDK (`gcloud`) with appropriate permissions
- [ ] `wget` to pull down the latest version of the ONS Design System

### Local Development Setup

The Makefile defines a set of commonly used commands and workflows.  Where possible use the files defined in the Makefile.

#### Clone the repository

```bash
git clone https://github.com/ONSdigital/survey_assist_ui.git
cd survey_assist_ui
```

#### Get the ONS Design System

**Note**: `wget` is required to pull in the latest ONS Design System, this can be installed on mac using `brew`

```bash
make load-design-system-templates
```

#### Install Dependencies

```bash
poetry install
```

#### Run the Application Locally

See the [Environment Variables](#environment-variables) section prior to execution.

To run the application locally execute:

```bash
make run-ui
```

To direct standard error and sys to a log file run use the following command.

```bash
make run-ui > application_output.log 2>&1
```

#### UI Access Credentials

The UI will be accessed using a unique ID and access code.  These credentials are generated using a separate verification service (see [firestore-otp](https://github.com/ONSdigital/firestore-otp)).

It is assumed such a service is running and you have access to a list of ID and code pairs.  See the environment section for details on how to setup the base url for this service.

#### Run the Application in a Container

To run the application in a container against API gateway deployed in GCP then you can do the following:

##### Build the Docker Image

The docker image will bake in build date and version (from pyproject.toml) by default.

View the build parameters:

```bash
make show-docker-build
```

To override the env settings for the build you can set the following environment variables:

```bash
export VERSION=<desired version name>
export GIT_SHA=<specific git sha>
export BUILD_DATE=<specific date in format - YYYY-MM-DDTHH:MM:SSZ>
```

```bash
make build-docker
```

#### Set Appropriate Credentials

When running locally the container needs to be passed a credential file for a service account that has permissions to generate an API token (this would typically be the UI service account assuming the role of the API account to generate a token). You will need to
download the key file associated with the UI service account from the appropriate GCP account.

#### Run the Docker Image

See the section [Set environment variables](#set-the-required-environment-variables) for the values to set in shell before running the container.

```bash
make run-docker CRED_FILE=/path/to/service-account-cred.json
```

### Code Quality

Code quality and static analysis will be enforced using isort, black, ruff, mypy and pylint. Security checking will be enhanced by running bandit.

To check the code quality, but only report any errors without auto-fix run:

```bash
make check-python-nofix
```

To check the code quality and automatically fix errors where possible run:

```bash
make check-python
```

### Documentation

Documentation is available in the docs folder and can be viewed using mkdocs

```bash
make run-docs
```

### Testing

Unit testing for utility functions is added to the [/tests](./tests/)

```bash
make all-tests
```

### Environment Variables

As the UI uses Google Application Default Credentials to generate tokens it is **important** to ensure that:

#### Unset the GOOGLE_APPLICATION_CREDENTIALS variable

Ensure the environment variable is not set in your poetry virtual environment:

```bash
unset GOOGLE_APPLICATION_CREDENTIALS
poetry run python -c 'import os; print(repr(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")))'

None
```

#### Project setting for default application credentials

The application default credentials are governed by a json file usually stored at:

```bash
cat ~/.config/gcloud/application_default_credentials.json
```

The project is indicated by the **quota_project_id** field, this can be set by using the command:

```bash
gcloud auth application-default set-quota-project survey-assist-sandbox
```

#### Set the required environment variables

The following environment variables must be set to run the UI against a backend API.

```bash
export BACKEND_API_URL=<URL where API Gateway is running>
export BACKEND_API_VERSION=v1 (or desired version)
export SA_EMAIL=<service account email associated with API access>
```

The following environment variable is set to connect with the verification service.

```bash
export VERIFY_API_URL=<URL for cloud run where firestore otp verification service is running>
```

Set the following environment variables for extra logging of session data and to prettify JSON.

```bash
export JSON_DEBUG=True
export SESSION_DEBUG=True 
```

### Scripts

You can test API endpoints from the CLI using the [run_api.py script](scripts/run_api.py) with the following command:

#### Execute API GET /config

```bash
poetry run python scripts/run_api.py --action config
```

#### Execute API GET /sic-lookup

Note: "pubs" for the 'Enter organisation description' question will return a match.

```bash
poetry run python scripts/run_api.py --type sic --action lookup
```

#### Execute API POST /classify

```bash
poetry run python scripts/run_api.py --type sic --action classify
```

#### Execute API GET /sic-lookup and POST /classify

```bash
poetry run python scripts/run_api.py --type sic --action both
```

#### Execute Verify API root "/"

```bash
poetry run python scripts/run_api.py --type sic --action root-otp
```

#### Execute Verify API Post /verify

```bash
poetry run python scripts/run_api.py --type sic --action verify-otp --id_str=<ID> --otp=EXAM-PLE1-23FO-UR56
```

#### Execute Verify API Post /delete

```bash
poetry run python scripts/run_api.py --type sic --action delete-otp --id_str=<ID>
```
