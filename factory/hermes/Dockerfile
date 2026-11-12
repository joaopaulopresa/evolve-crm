# Hermes Agent with what this product needs baked in, so it runs without open internet:
#   - the project's toolchain (Python and Node dependencies) to run migrations and tests
#   - the Langfuse plugin, installed at build time
#   - helper commands (evolve-start, evolve-test, evolve-submit) that make the routine steps
#     of a change request deterministic
# One image, two roles (HERMES_ROLE): "builder" implements changes, "analyst" answers
# questions about the data. Build from the repository root.
FROM nousresearch/hermes-agent:stable

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Python toolchain for api/ (same requirements the API image installs).
COPY api/requirements.txt api/requirements-dev.txt /opt/evolve/api/
RUN python3 -m venv /opt/evolve/venv \
    && /opt/evolve/venv/bin/pip install --no-cache-dir -r /opt/evolve/api/requirements-dev.txt

# Node dependencies for web/. The checkout links to this folder instead of running npm.
COPY web/package.json web/package-lock.json /opt/evolve/web/
RUN cd /opt/evolve/web && npm ci --no-audit --no-fund

# Hermes keeps plugins and their dependencies in its data directory, which is a volume. Install
# the Langfuse plugin there now and keep a copy; 00-evolve-setup seeds an empty volume from it.
RUN export PATH="/command:/package/admin/s6/command:$PATH" \
    && /opt/hermes/docker/stage2-hook.sh \
    && s6-setuidgid hermes env HOME=/opt/data hermes plugins install langfuse --enable --yes-deps \
    && cp -a /opt/data /opt/evolve/home-seed

COPY factory/hermes/bin/ /usr/local/bin/
COPY factory/hermes/00-evolve-setup /etc/cont-init.d/00-evolve-setup
# The brief for the builder. Optional at build time so the image builds from a checkout
# that does not have it yet.
COPY AGENTS.m[d] /opt/evolve/
RUN chmod +x /usr/local/bin/evolve-* /etc/cont-init.d/00-evolve-setup

CMD ["gateway", "run"]
