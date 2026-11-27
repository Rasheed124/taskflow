# Production security rollout

The production settings redirect HTTP to HTTPS, use secure session and CSRF
cookies, and send a one-year HSTS policy. HSTS is limited to the configured
host; subdomains and preload are disabled unless deliberately enabled through
environment settings.

The Content Security Policy is initially sent as
`Content-Security-Policy-Report-Only`. Browser reports are accepted at
`/csp-report/` and summarized in the `core.security` log without recording
full URLs or submitted form values. Review those logs after deployment. When
the report stream contains no unexpected legitimate resources, set
`CSP_REPORT_ONLY=false` to enforce the same policy.

Run the production configuration check before release:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
python manage.py check --deploy
```

Provide the production environment variables (`SECRET_KEY`, `DATABASE_URL`,
`ALLOWED_HOSTS`, and `DEFAULT_FROM_EMAIL`) when running this command. Keep
tests and local checks pointed at a non-production database. As part of the
deployment release process, apply pending migrations to the production
database with `python manage.py migrate --noinput`; take a database backup
first when the deployment changes production data or schema.

Build static assets with `python manage.py collectstatic --noinput` as part of
the deployment build unless the hosting platform already runs this command.
