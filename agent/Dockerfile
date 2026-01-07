# Stage 1: Builder
FROM python:3.13-slim AS builder

WORKDIR /build

# Copy SDK if present (pulumi build), otherwise we'll install from pip
COPY _sdk* /sdk/

# Install SDK: local copy if present, otherwise from pip
RUN if [ -f /sdk/pyproject.toml ]; then \
        pip install --no-cache-dir /sdk; \
    else \
        pip install --no-cache-dir c3-sdk; \
    fi

# Install other requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code (excludes _sdk via .dockerignore)
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
