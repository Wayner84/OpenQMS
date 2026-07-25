"""Integration tests against real PostgreSQL: Alembic migration + readiness endpoint.

Per docs/Database.md#engines, PostgreSQL-only behaviour (JSONB, the Alembic
migration itself) must be proven here, never against SQLite. Requires a reachable
PostgreSQL instance at `TEST_DATABASE_URL`; this module supplies the fixture and
invokes `alembic upgrade head` before each integration test.
"""

import os
import subprocess
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.integration

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; skipping real-PostgreSQL integration tests")
    return url


def _run_alembic_upgrade_head(database_url: str) -> None:
    env = dict(os.environ, DATABASE_URL=database_url, PYTHONPATH="")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def database_url() -> str:
    url = _database_url()
    _run_alembic_upgrade_head(url)
    return url


async def test_migration_creates_tables_and_seeds_exactly_one_organisation(
    database_url: str,
) -> None:
    """alembic upgrade head creates organisations/configuration and seeds one row."""
    from app.models.organisation import Organisation

    engine = create_async_engine(database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        result = await session.execute(select(Organisation))
        organisations = result.scalars().all()

    await engine.dispose()

    assert len(organisations) == 1
    assert organisations[0].slug == "default"
    assert organisations[0].id == uuid.UUID("00000000-0000-0000-0000-000000000001")


async def test_migration_upgrade_is_idempotent_on_rerun(database_url: str) -> None:
    """Running alembic upgrade head again must not create a second organisation row."""
    from app.models.organisation import Organisation

    _run_alembic_upgrade_head(database_url)

    engine = create_async_engine(database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        result = await session.execute(select(Organisation))
        organisations = result.scalars().all()

    await engine.dispose()

    assert len(organisations) == 1


async def test_configuration_jsonb_round_trips_structured_value(database_url: str) -> None:
    """The configuration.value JSONB column stores and returns nested structured data."""
    from app.models.configuration import Configuration
    from app.models.organisation import Organisation

    engine = create_async_engine(database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        result = await session.execute(select(Organisation).where(Organisation.slug == "default"))
        org = result.scalar_one()

        # Clean up any row left by a previous run of this test against the same
        # (persistent, disposable) database, so the test is repeatable.
        await session.execute(
            delete(Configuration).where(
                Configuration.organisation_id == org.id,
                Configuration.key == "instance.display_name",
            )
        )
        await session.commit()

        config = Configuration(
            organisation_id=org.id,
            key="instance.display_name",
            value={"nested": {"list": [1, 2, 3]}, "flag": True},
        )
        session.add(config)
        await session.commit()

        configuration_result = await session.execute(
            select(Configuration).where(
                Configuration.organisation_id == org.id,
                Configuration.key == "instance.display_name",
            )
        )
        stored = configuration_result.scalar_one()

    await engine.dispose()

    assert stored.value == {"nested": {"list": [1, 2, 3]}, "flag": True}


async def test_health_ready_reports_ready_against_real_postgres(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/v1/health/ready returns 200 ready when DATABASE_URL points at real PostgreSQL."""
    import app.core.config as config_module
    import app.core.db as db_module
    from app.main import create_app

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")
    config_module.get_settings.cache_clear()
    db_module.get_session_factory.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}
