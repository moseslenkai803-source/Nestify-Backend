# Integration tests

## Property-location migration upgrade test
`test_property_location_migration_upgrade.py` is excluded from ordinary pytest collection because it starts a fresh Docker container running PostgreSQL with PostGIS. This test exercises the real Alembic ancestry and is intentionally separate from the shared `nestify_pytest` integration database.

Enable it explicitly:

```
RUN_MIGRATION_TESTS=1 \
DATABASE_URL=postgresql+psycopg://unused:unused@127.0.0.1:1/nestify_pytest \
JWT_SECRET_KEY=ci-only-test-secret \
pytest -q tests/integration/test_property_location_migration_upgrade.py
```
The `DATABASE_URL` above only satisfies the ordinary test-suite database-name guard; this migration test does not connect to it. Its migration target URL is constructed exclusively from the fresh Testcontainers instance and is checked against that container's endpoint and the exact database name `nestify_migration_test` before connecting or invoking Alembic.

The test rejects `nestify` and `nestify_pytest` as migration targets and never falls back to the application settings URL.

An enabled run requires Docker access and the pinned PostGIS image `postgis/postgis:16-3.4`, matching Nestify's PostgreSQL 16/PostGIS 3.4 environment. Infrastructure or migration failures fail the test; they are not skipped.

The dedicated GitHub Actions workflow is located at `.github/workflows/property-location-migration.yml`. It runs the migration test on pull requests, pushes to `main`, and manual workflow dispatches. It explicitly enables `RUN_MIGRATION_TESTS=1` and provisions its disposable database through Testcontainers.
