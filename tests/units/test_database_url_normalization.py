import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        (
            "postgres://user:password@localhost:5432/nestify",
            "postgresql+psycopg://user:password@localhost:5432/nestify",
        ),
        (
            "postgresql://user:password@localhost:5432/nestify",
            "postgresql+psycopg://user:password@localhost:5432/nestify",
        ),
        (
            "postgresql+psycopg://user:password@localhost:5432/nestify",
            "postgresql+psycopg://user:password@localhost:5432/nestify",
        ),
    ],
)
def test_database_url_uses_psycopg3(database_url, expected):
    settings = Settings(
        database_url=database_url,
        jwt_secret_key="test-only-secret",
    )

    assert settings.database_url == expected
