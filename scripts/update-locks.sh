#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  --mount "type=bind,src=$(pwd),dst=/src" --workdir /src \
  python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 \
  sh -ec 'python -m venv /tmp/lockenv
    /tmp/lockenv/bin/pip install pip-tools==7.5.1
    /tmp/lockenv/bin/pip-compile --upgrade --allow-unsafe --extra ai --generate-hashes --strip-extras --no-emit-index-url -o requirements.lock pyproject.toml
    /tmp/lockenv/bin/pip-compile --upgrade --allow-unsafe --generate-hashes --strip-extras --no-emit-index-url -o requirements-build.lock requirements-build.in'
