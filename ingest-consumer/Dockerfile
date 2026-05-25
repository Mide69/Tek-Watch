FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd -r consumer && useradd -r -g consumer -d /app consumer

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=consumer:consumer . .

USER consumer

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import boto3; print('ok')" || exit 1

CMD ["python", "main.py"]
