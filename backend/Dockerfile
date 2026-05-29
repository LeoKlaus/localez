FROM python:3.13-slim

WORKDIR /app

ARG APP_VERSION=dev
ARG CHANNEL=preview
ENV APP_VERSION=${APP_VERSION}
ENV CHANNEL=${CHANNEL}

# Install the package and its dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application source
COPY . .

EXPOSE 8000

# Run migrations then start the server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
