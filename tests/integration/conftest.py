"""Integration tests run against a real Postgres with pgvector (`docker compose up -d`)."""

import os
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.integrations.db.repository import PostgresCorpusRepository, create_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://immicite:immicite@localhost:5432/immicite_test"
)
ROOT = Path(__file__).parents[2]


def _dsn(database: str) -> str:
    url = make_url(TEST_DATABASE_URL).set(drivername="postgresql", database=database)
    return url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def test_database() -> str:
    name = make_url(TEST_DATABASE_URL).database
    try:
        with psycopg.connect(_dsn("postgres"), autocommit=True, connect_timeout=3) as conn:
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
                conn.execute(f'CREATE DATABASE "{name}"')
    except psycopg.OperationalError:
        if os.environ.get("CI"):
            raise
        pytest.skip("Postgres is not reachable; start it with `docker compose up -d`")
    return name


@pytest.fixture
def database_url(test_database: str) -> str:
    """A freshly migrated, empty database for each test."""
    with psycopg.connect(_dsn(test_database), autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")
    return TEST_DATABASE_URL


@pytest.fixture
async def engine(database_url: str):
    engine = create_engine(database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
def repository(engine) -> PostgresCorpusRepository:
    return PostgresCorpusRepository(engine)
