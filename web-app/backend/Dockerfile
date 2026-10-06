# Backend image for the backend, indexer and test services (dev image: includes the dev group).
FROM python:3.12-slim

# uv, pinned to the version that wrote uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /uvx /bin/

# git: the existing init_vault test (tests/test_conformance.py) runs the vault init script,
# which needs it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# uid/gid 1000 match the usual host user, so files written into the ./backend bind mount
# stay owned by the developer.
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 --create-home app

# The virtualenv lives outside the backend directory so the bind mount cannot hide it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# The existing parser tests find the golden vault by a path relative to the repository
# layout (tests/ -> backend -> web-app -> repo root -> second-brain/). Reproduce that layout
# so they run unchanged: the backend lives at /repo/web-app/backend, and /repo/second-brain
# is where the test service mounts the vault source read-only.
RUN mkdir -p /opt/venv /repo/web-app/backend /repo/second-brain \
    && chown app:app /opt/venv /repo/web-app/backend
WORKDIR /repo/web-app/backend
USER app

# Dependencies first (cached until the lock changes); the dev group is included by default.
COPY --chown=app:app pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/home/app/.cache/uv,uid=1000,gid=1000 \
    uv sync --frozen --no-install-project

COPY --chown=app:app . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
