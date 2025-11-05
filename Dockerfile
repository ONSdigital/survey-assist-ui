# syntax=docker/dockerfile:1.7

############################
# Builder
############################
FROM python:3.12-slim AS builder

ARG VERSION
ARG GIT_SHA
ARG BUILD_DATE

LABEL org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$GIT_SHA \
      org.opencontainers.image.created=$BUILD_DATE

ENV APP_VERSION=$VERSION \
    APP_GIT_SHA=$GIT_SHA \
    APP_BUILD_DATE=$BUILD_DATE

# System deps for building wheels (runtime will not include these)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl \
      build-essential \
      gcc \
      libffi-dev \
      libssl-dev \
      libpq-dev \
      git \
 && rm -rf /var/lib/apt/lists/*

# Poetry 2.x
ENV POETRY_HOME="/opt/poetry" \
    POETRY_VERSION=2.1.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR="/var/cache/pypoetry"

RUN curl -fsSLo /tmp/install-poetry.py https://install.python-poetry.org \
 && python3 /tmp/install-poetry.py --version ${POETRY_VERSION} \
 && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry \
 && rm -f /tmp/install-poetry.py

# Create a dedicated virtualenv for app deps
ENV VENV_PATH="/opt/venv"
RUN python -m venv "${VENV_PATH}"
ENV PATH="${VENV_PATH}/bin:${PATH}"

WORKDIR /app

# ---- Dependency layer (maximises cache)
COPY pyproject.toml poetry.lock ./
COPY README.md ./

# Install export plugin for poetry (to enable pip install from reqs)
RUN poetry --version \
 && poetry self add "poetry-plugin-export>=1.8.0"

 RUN poetry export --only main --without-hashes -f requirements.txt -o /tmp/req.txt \
 && pip install --no-cache-dir -r /tmp/req.txt \
 && rm /tmp/req.txt

# ---- App layer
COPY survey_assist_ui ./survey_assist_ui
COPY models ./models
COPY utils ./utils
COPY main.py ./

# Install gunicorn:
RUN pip install --no-cache-dir .

 # Sanity check - verify gunicorn is installed
RUN ls -l /opt/venv/bin/gunicorn && /opt/venv/bin/python -c "import flask; print('flask ok')"

############################
# Runtime
############################
FROM python:3.12-slim AS runtime

# Minimal runtime packages
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1

# Copy virtualenv from builder
ENV VENV_PATH="/opt/venv"
ENV PATH="${VENV_PATH}/bin:${PATH}"
COPY --from=builder ${VENV_PATH} ${VENV_PATH}

# Create non-root early
RUN addgroup --system app && adduser --system --group app

WORKDIR /app
# Copy app as non-root with correct ownership
COPY --chown=app:app --from=builder /app /app

USER app

#Expose the port
EXPOSE 8000

ARG VERSION
ARG GIT_SHA
ARG BUILD_DATE
ARG GUNICORN_WORKERS
ENV APP_VERSION=$VERSION APP_GIT_SHA=$GIT_SHA APP_BUILD_DATE=$BUILD_DATE
LABEL org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$GIT_SHA \
      org.opencontainers.image.created=$BUILD_DATE

# Optional: adjust to your health endpoint
# Disabling in favour of GCP healthchecks in cloud run
# HEALTHCHECK --interval=30s --timeout=3s \
#   CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/').read()" || exit 1

# Production WSGI server (configure via env if you prefer)
# GUNICORN_WORKERS default is single CPU (worker) and single thread
# App code would need some work to enable multi-process/worker processing
ENV GUNICORN_THREADS=1 GUNICORN_BIND=0.0.0.0:8000
CMD ["/bin/sh","-c","exec /opt/venv/bin/gunicorn -w ${GUNICORN_WORKERS:-1} --threads ${GUNICORN_THREADS:-1} -b ${GUNICORN_BIND:-0.0.0.0:8000} main:app"]