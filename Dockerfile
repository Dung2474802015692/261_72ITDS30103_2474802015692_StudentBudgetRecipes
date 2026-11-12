# Production image for Student Budget Recipes.
# python:3.12-slim matches .python-version (3.12.10) and has the wheels that
# psycopg[binary] needs, so no compiler is installed.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies change rarely, so their layer comes before the source code.
# A commit that only edits templates or services rebuilds from COPY src onward.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY src ./src

# Run as a non-root user. The app writes nothing to disk in production
# (data lives in DATABASE_URL), so the code directory stays read-only to it.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Render and Compose set PORT; 8000 is the default for local runs.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --app-dir src --host 0.0.0.0 --port ${PORT}"]
