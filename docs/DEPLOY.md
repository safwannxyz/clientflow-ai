# Deployment

Three levels, in order of how much you are willing to depend on someone else.

## 1. Local (always works)

```bash
python -m clientflow.cli fetch-cuad && python -m clientflow.cli train
python -m clientflow.cli demo --reset
python -m clientflow.cli serve           # http://127.0.0.1:8770
```

No network needed after the first two commands. This is what to use in an interview room.

## 2. Static snapshot (shareable file, no server)

```bash
python scripts/snapshot.py --out dist
```

Produces `dist/index.html` and `dist/review.html` — self-contained pages you can open from disk,
email, or drop on Netlify Drop / GitHub Pages with no account configuration.

## 3. Container (a real URL)

```bash
docker build -t clientflow .
docker run -p 8770:8770 -e CLIENTFLOW_API_TOKEN=change-me -v clientflow-data:/data clientflow
```

Or use the Render blueprint (`render.yaml`):

1. Push to GitHub.
2. Render → New → Blueprint → point at the repo.
3. Render generates `CLIENTFLOW_API_TOKEN` for you; do not set it by hand in the file.
4. Health check is `/health`; SQLite lives on the mounted disk at `/data`.

### Two limits to say out loud if you deploy this for real

- **One instance only.** SQLite plus a file-backed queue does not scale horizontally. That is a
  deliberate trade, not an oversight; Postgres plus a real queue is the upgrade path.
- **A public URL is not appropriate for client data.** There is one shared token, no per-user
  accounts, no SSO and no TLS within the app. The dashboard is for a local or authenticated
  environment; anything with real matters needs the firm's identity provider in front of it.

## CI

`.github/workflows/ci.yml` installs dependencies, fetches CUAD, trains, runs the 52 tests, smoke-tests
the CLI and fails the build on an obvious committed secret.
