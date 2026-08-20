FROM python:3.13-slim AS runtime

ARG APP_VERSION=1.0.0
ARG APP_REVISION=unknown

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=$APP_VERSION \
    APP_REVISION=$APP_REVISION

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY data ./data
COPY migrations ./migrations

RUN pip install --no-cache-dir .

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
