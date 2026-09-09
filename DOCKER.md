# Docker usage

Run these commands from the **DocumentationTool repository**. The images package the checker only; the collaborator's runner remains responsible for producing workflow results.

## Build and test

```bash
docker build --target test -t workflow-documentation:test .
docker build --target release -t workflow-documentation:0.2.0 .
```

The test target installs the built wheel in a clean Linux image and runs the test suite. The release target excludes tests and build dependencies. Both stages use a digest-pinned Python 3.12 base and hash-verified Python dependency locks. Default runtime user: UID/GID `10001:10001`.

The lockfiles were resolved for Linux/Python 3.12. Local Docker validation uses Linux ARM64 on this Mac. The Docker CI job targets Linux AMD64; cross-platform success must be verified by that job before release. No images are pushed by CI.

## Run the bundled example

```bash
mkdir -p reports
docker run --rm --network none --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$(pwd)/examples,dst=/inputs,readonly" \
  --mount "type=bind,src=$(pwd)/reports,dst=/reports" \
  workflow-documentation:0.2.0 /inputs/workflow --source-type local \
  --config /inputs/files.json --usage-check \
  --output /reports/documentation.txt --json-output /reports/documentation.json
```

The image includes Git for repository URL inputs and the optional AI dependencies. For repository URLs or Gemini calls, omit `--network none`. Pass an existing API key with `-e GOOGLE_API_KEY` at runtime and enable `--ai-analysis`; credentials are never built into the image. The tests do not call external AI services.

Git and its OS dependencies are installed from Debian Bookworm repositories during the build. Those OS packages are not snapshot-locked; record the built image digest for a released environment. Python dependencies and the base image are pinned.

## Outputs, updates and verification

Inputs are read-only, the container root is read-only and `/tmp` is writable. `--user` maps the current host UID/GID so report files remain writable by the host user. Ensure the reports directory exists and is writable. Exit codes from the checker are preserved: 0 PASS, 1 failed/incomplete assessment, 2 execution/input error.

Refresh dependency locks deliberately, then rebuild/test:

```bash
./scripts/update-locks.sh
```

Update the pinned Python digest in both `Dockerfile` and the lock-update script together. Normal image builds do not resolve newer Python versions; they verify package hashes in `requirements.lock`. `requirements-build.lock` includes setuptools, wheel and pytest explicitly.

The image smoke test can run with no network and read-only input mounts. Image build and dependency updates need network access. Publishing images and adding workflow execution are outside this change.
