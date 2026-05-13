# localez

REST API for managing Apple `.xcstrings` localization files. Translators propose edits, reviewers accept or reject them, and admins import/export the canonical xcstrings files.

## Prerequisites

- Python 3.13
- PostgreSQL 16+ (dev) or Docker + Docker Compose (container)

---

## Development setup

**1. Create and activate a virtual environment**

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

**2. Install dependencies**

```bash
pip install -e ".[dev]"
```

**3. Configure environment**

```bash
cp .env.example .env
# Edit .env — at minimum set POSTGRES_PASSWORD and SECRET_KEY
```

**4. Start PostgreSQL**

```bash
docker compose up db -d
```

**5. Run migrations**

```bash
alembic upgrade head
```

**6. Start the server**

```bash
uvicorn app.main:app --reload
```

The API is now available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

**7. Create an admin user**

```bash
python -m app.cli create-admin --username admin
# Password is prompted securely
```

---

## Running tests

Tests use [testcontainers](https://testcontainers.com/) and spin up a throwaway PostgreSQL instance automatically — no manual DB setup required.

```bash
pytest
```

---

## Container setup

**1. Configure environment**

```bash
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD, SECRET_KEY, and POSTGRES_HOST=db
```

**2. Build and start**

```bash
docker compose up --build
```

The API starts at `http://localhost:8000`. On every startup the container runs `alembic upgrade head` before serving traffic, so schema changes are applied automatically when the image is rebuilt and restarted.

**3. Create an admin user**

```bash
docker compose exec api python -m app.cli create-admin --username admin
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | Database host (`db` when using Docker) |
| `POSTGRES_PORT` | `5432` | Database port |
| `POSTGRES_DB` | `localez` | Database name |
| `POSTGRES_USER` | `localez` | Database user |
| `POSTGRES_PASSWORD` | — | Database password **(required)** |
| `SECRET_KEY` | — | JWT signing key **(required, keep secret)** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token lifetime |
| `WEBAUTHN_RP_ID` | `localhost` | WebAuthn relying party ID (your domain in production) |
| `WEBAUTHN_RP_NAME` | `Localez` | WebAuthn relying party display name |
| `WEBAUTHN_ORIGIN` | `http://localhost:8000` | WebAuthn expected origin |
| `RECOVERY_WORD_LIST_PATH` | `app/core/wordlist.txt` | Path to the recovery word list |
