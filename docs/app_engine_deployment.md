# App Engine deployment

The monitor uses the App Engine standard Python 3.14 runtime and Gunicorn. `app.yaml`
contains no credentials. The deployed service needs these environment variables:

```text
DATABASE_URL
GCP_PROJECT_ID
GCS_RAW_BUCKET
GCS_PROCESSED_BUCKET
GCS_RUNS_BUCKET
```

`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` may be supplied instead
of `DATABASE_URL`. `DIRECT_DATABASE_URL` is migration-only and is not required by the
web service. Grant the App Engine service identity read access to bucket metadata; the
dashboard health route never creates or deletes objects.

For a deployment that uses App Engine environment variables, make an ignored
`app.deploy.yaml` copy of `app.yaml`, add an `env_variables` mapping with the runtime
configuration, and deploy only that ignored file:

```bash
gcloud app deploy app.deploy.yaml
```

Do not commit `app.deploy.yaml`, database credentials, service-account keys, ADC
files, tokens, or connection strings. Prefer the organization's approved secret
injection process when one is available.
