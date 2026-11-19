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

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md LICENSE ./
COPY internetbox_client/ internetbox_client/

RUN if [ -n "$VERSION" ]; then export SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION"; fi \
    && uv pip install --system --no-cache .

EXPOSE 9101

CMD ["ibox", "export"]
