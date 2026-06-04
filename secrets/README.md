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
