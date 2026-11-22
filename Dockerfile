FROM python:3.12-slim

# Set by CI from the git tag (e.g. 0.2.0). Local builds without it report 0.0.0.
ARG VERSION=""

LABEL org.opencontainers.image.title="pyinternetbox" \
      org.opencontainers.image.description="Internet Box API client and Prometheus exporter for Swisscom and Wingo routers." \
      org.opencontainers.image.source="https://github.com/oregonpillow/pyinternetbox" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY internetbox_client/ internetbox_client/

# uv is removed in the same step that installs it, so it's in no layer of the image. pip, from the base image, goes too.
# Without root, Python can't write .pyc files at runtime, so they're compiled here.
RUN pip install --no-cache-dir --root-user-action=ignore uv \
    && if [ -n "$VERSION" ]; then export SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION"; fi \
    && uv pip install --system --no-cache --compile-bytecode . \
    && python -m pip uninstall --yes --root-user-action=ignore uv pip \
    && rm -f /usr/local/bin/pip

# A fixed numeric UID, so Kubernetes can check that the image doesn't run as root.
RUN groupadd --gid 10001 ibox \
    && useradd --uid 10001 --gid ibox --no-create-home --no-log-init --shell /usr/sbin/nologin ibox
USER 10001:10001

EXPOSE 9101

CMD ["ibox", "export"]
