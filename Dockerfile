FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml .
COPY app ./app
COPY alembic.ini .
COPY migrations ./migrations

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS test

USER root
ENV PYTEST_ADDOPTS="-p no:cacheprovider"
RUN pip install --no-cache-dir ".[dev]"
COPY tests ./tests
USER appuser

CMD ["python", "-m", "pytest", "-q"]
