# Python processing engine: ingest, analysis, reporting (Typst), Dagster.
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

ARG TYPST_VERSION=0.13.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl xz-utils ca-certificates fonts-dejavu-core \
    && curl -fsSL "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz" \
       | tar -xJ -C /tmp \
    && mv /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst \
    && rm -rf /var/lib/apt/lists/* /tmp/typst-*

WORKDIR /app
COPY pyproject.toml uv.lock* README.md ./
COPY src ./src
RUN uv sync --no-dev --extra orchestration --extra cloud

ENV PATH="/app/.venv/bin:${PATH}" \
    DAGSTER_HOME=/opt/dagster/home
RUN mkdir -p ${DAGSTER_HOME}

CMD ["dagster", "dev", "-h", "0.0.0.0", "-p", "3000"]
