# Reset production data without a provider shell

TaskFlow provides a manually triggered GitHub Actions workflow for clearing
production data while preserving the PostgreSQL database and its schema. The
workflow does not call Render's deploy hook and does not run database
migrations.

## What the reset does

The reset removes all application rows, including users, tasks, categories,
account profiles, sessions, and rate-limit buckets. It then creates one fresh
superuser from the configured reset-admin secrets and marks that admin's email
as verified so they can sign in to TaskFlow. Users, tasks, and other
records cannot be recovered by the workflow; take a provider export or backup
first if one is available. The workflow does not save a database dump in
GitHub Actions.

The database resource, tables, and migration history remain in place. No reset
is performed unless the command confirms production settings, `DEBUG=False`,
PostgreSQL, the required admin credentials, and the exact confirmation phrase.
The flush and replacement superuser creation run in one database transaction.

## One-time GitHub setup

1. In the repository, create a GitHub Environment named
   `production-data-reset` when your GitHub plan/repository visibility allows
   environment configuration.
2. Add these secrets, preferably to that environment:

   - `PRODUCTION_SECRET_KEY`
   - `PRODUCTION_DATABASE_URL` — Render's **external** PostgreSQL URL, with
     TLS required (`sslmode=require`). Do not use the internal URL from a
     GitHub-hosted runner.
   - `PRODUCTION_DB_NAME` — the exact database name in that URL. The reset
     command compares it with Django's configured database name before
     flushing.
   - `PRODUCTION_ALLOWED_HOSTS`
   - `PRODUCTION_DEFAULT_FROM_EMAIL`
   - `PRODUCTION_RESET_ADMIN_USERNAME`
   - `PRODUCTION_RESET_ADMIN_EMAIL`
   - `PRODUCTION_RESET_ADMIN_PASSWORD` — must pass TaskFlow's configured
     Django password validators.

3. If available, restrict the `production-data-reset` environment to the
   `todo-list` branch and require a reviewer. Repository-level secrets also
   work with this workflow, but any repository workflow can access them; limit
   who can edit workflow files and prefer environment-level secrets for these
   production credentials. When a same-named environment secret exists, it
   takes precedence over the repository secret.
4. Ensure Render allows external PostgreSQL connections from GitHub Actions.
   If external database access is disabled or restricted, the workflow will
   fail before changing data. Do not add a public reset endpoint as a bypass.

## Run a reset

1. Open the repository's **Actions** tab and select **Reset production data**.
2. Select the `todo-list` branch.
3. Enter `CLEAR_TASKFLOW_PRODUCTION_DATA` in the confirmation field.
4. Start the workflow and wait for it to finish. If environment approval is
   configured, approve the run before it connects to PostgreSQL.
5. Sign in to `/admin/` with the reset-admin username and password stored in
   the GitHub Environment secrets.

The workflow is manual-only, is restricted to the `todo-list` branch, uses a
separate concurrency group, and performs a second confirmation check in the
Django management command. Do not test this workflow against production data.
