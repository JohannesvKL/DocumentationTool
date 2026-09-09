# Python 3.12, Linux; update digest and lockfiles together, then run the test target.
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS builder
WORKDIR /src
COPY requirements-build.lock .
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-build.lock
COPY . .
RUN python -m pip wheel --no-deps --no-build-isolation --wheel-dir /wheels .

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.lock /opt/checker/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /opt/checker/requirements.lock
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-deps /wheels/*.whl && rm -rf /wheels \
    && useradd --create-home --uid 10001 checker && mkdir /work && chown checker /work
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["doccheck"]

FROM runtime AS test
USER root
COPY requirements-build.lock /opt/checker/requirements-build.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /opt/checker/requirements-build.lock
COPY tests /checks/tests
COPY examples /checks/examples
COPY pyproject.toml /checks/pyproject.toml
USER 10001:10001
WORKDIR /checks
RUN python -m pip check && python -m pytest -q -p no:cacheprovider tests

FROM runtime AS release
