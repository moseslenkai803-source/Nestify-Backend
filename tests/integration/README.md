# Integration tests

## Database migration tests

The migration tests in `tests/migrations/` are excluded from ordinary pytest collection because they start disposable Docker containers running PostgreSQL with PostGIS. They exercise real Alembic migrations independently of the shared `nestify_pytest` integration database.

Enable the tests explicitly with `RUN_MIGRATION_TESTS=1`.

### Property-location migration

```bash
RUN_MIGRATION_TESTS=1 python -m pytest -q tests/migrations/test_property_location_migration_upgrade.py
```

### Contractor/member assignment consistency migration

```bash
RUN_MIGRATION_TESTS=1 python -m pytest -q tests/migrations/test_assignment_contractor_member_migration.py
```

Both tests construct their migration database URLs exclusively from their own disposable Testcontainers instances. They verify the container endpoint and exact database name `nestify_migration_test` before connecting or invoking Alembic. Both reject `nestify` and `nestify_pytest` as migration targets and never fall back to the application settings URL.

Enabled runs require Docker access and the pinned image `postgis/postgis:16-3.4`, matching Nestify's PostgreSQL 16/PostGIS 3.4 environment. Infrastructure or migration failures fail the tests; they are not skipped.

The GitHub Actions workflow is located at `.github/workflows/database-migration-tests.yml`. It runs both migration tests on pull requests, pushes to `main`, and manual workflow dispatches. It explicitly enables `RUN_MIGRATION_TESTS=1` and provisions disposable databases through Testcontainers.
