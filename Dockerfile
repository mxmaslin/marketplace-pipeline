FROM python:3.11-slim

RUN groupadd --gid 1000 pipeline \
    && useradd --uid 1000 --gid pipeline --create-home pipeline

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN pip install --no-cache-dir ".[scale]" \
    && mkdir -p /app/data \
    && chown -R pipeline:pipeline /app

USER pipeline

ENV DEMO_MODE=true \
    MOCK_PARSER=true \
    MOCK_LLM=true \
    MOCK_CRM=true

CMD ["marketplace-pipeline"]
