# ---- Build Stage ----
FROM python:3.13-slim AS builder

# Pin uv version
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /usr/local/bin/uv

# Set UV configuration
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Copy project metadata first (for layer caching)
COPY pyproject.toml README.md ./

# Install dependencies into a virtual environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

# Copy source code and install the project
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev


# ---- Runtime Stage ----
FROM python:3.13-slim AS runtime

# I2C and audio tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    i2c-tools \
    libasound2 \
  && rm -rf /var/lib/apt/lists/*

# Create a non-root user in the i2c and audio groups
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser \
 && (getent group i2c   || groupadd -r i2c)   && usermod -aG i2c   appuser \
 && (getent group audio || groupadd -r audio) && usermod -aG audio appuser

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN mkdir /app && chown appuser:appuser /app
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv
COPY --chown=appuser:appuser src/ src/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import http.client; conn = http.client.HTTPConnection('localhost', 8000); conn.request('GET', '/health'); r = conn.getresponse(); exit(0 if r.status == 200 else 1)"

CMD ["uvicorn", "pi_sensors.main:app", "--host", "0.0.0.0", "--port", "8000"]
