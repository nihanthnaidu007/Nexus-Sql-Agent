FROM python:3.13-slim

WORKDIR /app

# libpq5 is the runtime library psycopg2-binary links against on slim images
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY . .

RUN chmod +x scripts/entrypoint.sh

EXPOSE 8000 8501
