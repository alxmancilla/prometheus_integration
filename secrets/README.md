# Secrets

This directory holds runtime secrets that are mounted into the Prometheus
container at `/etc/prometheus/secrets/`. Only the `*.example` files are
committed to git; the real files are excluded via `.gitignore`.

## Setup

```bash
cp secrets/atlas_password.example secrets/atlas_password
# then edit secrets/atlas_password and put the real Atlas Prometheus password
```

The file must contain **only the password** (no trailing whitespace, no
newline-sensitive parsing — Prometheus reads the file verbatim).

## Files

| File | Purpose |
|------|---------|
| `atlas_password` | Real Atlas Prometheus basic-auth password. **Not committed.** |
| `atlas_password.example` | Placeholder; copy to `atlas_password` and edit. |
| `atlas_password_production` / `atlas_password_staging` | Per-project passwords used by `prometheus-atlas.yml`. Copy from the matching `.example`. **Not committed.** |

The Prometheus container runs as `nobody` (UID 65534), so the files must be
readable by that user (e.g. `chmod 644`, or `chown 65534` + `chmod 400`).
