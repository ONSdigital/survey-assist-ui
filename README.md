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

To run the application locally execute:

```bash
make run-ui
```

To direct standard error and sys to a log file run use the following command.

```bash
make run-ui > application_output.log 2>&1
```

Set the following environment variables for extra logging of session data and to prettify JSON.

```bash
export JSON_DEBUG=True
export SESSION_DEBUG=True 
```

### GCP Setup

Placeholder

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
make unit-tests
```

### Environment Variables

Placeholder
