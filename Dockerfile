# Build a locked Python 3.12 environment; credentials are runtime host variables.
FROM python:3.12-slim AS builder
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.6
COPY pyproject.toml uv.lock README.md .python-version ./
COPY src ./src
COPY migrations ./migrations
COPY config/sources/aha-reviewed.json ./config/sources/aha-reviewed.json
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HOST=0.0.0.0
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
# The scheduled feed service mounts its persistent raw volume here. Keep the
# runtime UID compatible with the host's mounted-volume permissions.
RUN mkdir -p /data/raw
EXPOSE 8000
CMD ["rigbys-mcp"]
