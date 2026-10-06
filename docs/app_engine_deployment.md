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

The annotation migration must be applied separately before the deployed monitor
can query `/annotations`; see `docs/annotations.md`. UI annotation execution is
disabled by default. Do not enable it by merely adding the three opt-in environment
variables: first configure trusted HTTPS handling and hosting/worker deadlines.
The observed 20-version synchronous trial exceeded the current 30-second Gunicorn
worker timeout. Use the CLI for large runs, and keep the existing App Engine
deployment read-only until bounded execution is configured deliberately.

## Annotation and review readiness — verified 6 October 2026, 00:04 EAT

The repository now implements L0/L1/L2 monitoring, separate L2 weak/model result
views and protected local Human Review. Development weak labels cover all 324
currently eligible versions. The first real L2 development artifact is configured
**locally**, with 324/324 compatible predictions (11 gbv / 307 not_gbv /
6 borderline) and zero pending after verified operational closure.
This does not provision that artifact in App Engine or establish production model
configuration. Local model architecture and measured results are in
[the annotation document](annotations.md#trained-transformer-architecture--l2-afroxlmr-dev-v1).
This progress does not establish a deployed production classifier or completed
validation. See [implementation status](roadmap/IMPLEMENTATION_STATUS.md).

Verify each target database independently. Required migrations include:

| Migration | Purpose | Verified development state |
| --- | --- | --- |
| `20261003_add_automated_annotations.sql` | Automated run/result tables | Installed |
| `20261004_add_human_validations.sql` | Separate append-only review history | Installed |
| `20261005_add_l2_annotations.sql` | L2 labels/prerequisites, identity index and same-version L1-Kenya trigger | Installed and behavior-tested in development; all four readiness checks true |
| `20261005_add_l2_human_validations.sql` | Extend existing review labels to L2 | Installed |

Apply missing migrations to the intended target using the operator guide; do not
blindly rerun installed migrations or infer production readiness from development.
The operational closure applied only the authorized additive development migration;
production resources/schema were unchanged. This subsequent documentation update
made no database or cloud changes. CLI model runs check schema before writes,
verify actual advisory-lock ownership and fail closed on lease loss. macOS CLI
runs also prevent automatic idle sleep; there is no automatic relock or write replay.

Human Review is restricted to direct-local requests. Remote/proxied requests cannot
unlock article bodies or save reviews, including over HTTPS. Keep
`HUMAN_REVIEW_ENABLED=0` on App Engine: adding a shared token is not authenticated
multi-user review. Production review requires separate authenticated accounts,
authorization and trusted deployment handling. Collection pages remain metadata-only;
full text is retrieved only by unlocked local review sessions.

Optional L2 model execution additionally needs `requirements-l2.txt`, an immutable
trained artifact and deliberate model/threshold configuration. No model artifact
is provisioned by App Engine deployment, and `l2-model-unconfigured` does not trigger
an implicit download or weak-label fallback. Use the CLI for annotation/training;
the existing UI trigger remains bounded L0/L1 only. Do not place model weights,
research text, credentials or reviewer information in public deployment artifacts.

The proposed next human-validation milestone is documented in
[the annotation specification](annotations.md#17-next-steps-future-work). Review
batches, initially hidden model output, adjudication and progress reporting are
planned local-workspace additions; they do not authorize remote review or establish
production authentication.
