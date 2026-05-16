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

## GitHub Action Template

```yaml
- name: Push xcstrings
  run: |
    curl -sf -X POST https://your-host/api/projects/$PROJECT_ID/import \
      -H "Authorization: Bearer ${{ secrets.LOCALEZ_PROJECT_TOKEN }}" \
      -F "file=@Localizable.xcstrings" \
      -F "conflict=overwrite"
```