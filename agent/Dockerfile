FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r agent && useradd -r -g agent -d /app agent

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=agent:agent . .

USER agent

CMD ["python", "main.py"]
