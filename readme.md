# DEV Environment

## Start without frontend (to use HMR)
``` bash
docker compose -f docker-compose-dev.yml up
```

## Start with frontend
``` bash
docker compose --profile frontend -f docker-compose-dev.yml up
```

## Create an admin user

```bash
docker compose exec api python -m app.cli create-admin --username <user>
```