FROM python:3.11-slim

RUN groupadd --gid 1000 pipeline \
    && useradd --uid 1000 --gid pipeline --create-home pipeline

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir ".[scale]" \
    && mkdir -p /app/data \
    && chown -R pipeline:pipeline /app

USER pipeline

ENV DEMO_MODE=true \
    MOCK_PARSER=true \
    MOCK_LLM=true \
    MOCK_CRM=true

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["marketplace-pipeline"]
