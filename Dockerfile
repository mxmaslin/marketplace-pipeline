FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV DEMO_MODE=true \
    MOCK_PARSER=true \
    MOCK_LLM=true \
    MOCK_CRM=true

CMD ["marketplace-pipeline"]
