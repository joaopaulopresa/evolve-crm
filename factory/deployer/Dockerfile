# The deployer: the only container with the Docker socket. It runs the scripts in deploy/.
# Build from the repository root: docker build -f factory/deployer/Dockerfile .
FROM docker:29-cli AS docker

FROM python:3.13-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl openssl \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'
COPY --from=docker /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/deployer
COPY factory/deployer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY factory/deployer/ .

EXPOSE 8700
CMD ["uvicorn", "deployer.app:app", "--host", "0.0.0.0", "--port", "8700"]
