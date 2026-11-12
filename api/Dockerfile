# Build from the repository root: docker build -f api/Dockerfile .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/api

COPY api/requirements.txt api/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY api/ .
COPY seed/data.json /srv/seed/data.json

EXPOSE 8000
CMD ["./entrypoint.sh"]
