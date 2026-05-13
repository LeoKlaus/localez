import itertools
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.database import Base, get_db
from app.main import app

_counter = itertools.count(1)


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine(pg_container):
    url = pg_container.get_connection_url().replace("psycopg2", "asyncpg")
    e = create_async_engine(url, echo=False)
    yield e
    await e.dispose()


@pytest.fixture(scope="session")
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_database(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db(session_factory) -> AsyncSession:
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncClient:
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_client(session_factory) -> AsyncClient:
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/auth/register", json={"username": "admin_user", "password": "adminpass123"})
        assert resp.status_code == 201

        async with session_factory() as session:
            from sqlalchemy import update
            from app.models.user import GlobalRole, User
            await session.execute(update(User).where(User.username == "admin_user").values(global_role=GlobalRole.admin))
            await session.commit()

        resp2 = await c.post("/auth/token", data={"username": "admin_user", "password": "adminpass123"})
        token = resp2.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


# ---------------------------------------------------------------------------
# Convenience fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def unique_username():
    """Return a factory that generates unique usernames for each call."""
    def _make(prefix: str = "user") -> str:
        return f"{prefix}_{next(_counter)}"
    return _make


@pytest.fixture
def member_client(client: AsyncClient):
    """
    Factory: create additional authenticated AsyncClients using the test DB.
    Depends on `client` to keep the DB override active.
    Usage: async with member_client("alice") as c: ...
    """
    @asynccontextmanager
    async def _make(username: str, password: str = "securepass1"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            reg = await c.post("/auth/register", json={"username": username, "password": password})
            assert reg.status_code in (201, 409), f"Registration failed: {reg.status_code} {reg.json()}"
            token_resp = await c.post("/auth/token", data={"username": username, "password": password})
            assert token_resp.status_code == 200
            c.headers["Authorization"] = f"Bearer {token_resp.json()['access_token']}"
            yield c
    return _make


@pytest_asyncio.fixture
async def project(admin_client: AsyncClient) -> dict:
    """Create a bare project and return its JSON body."""
    resp = await admin_client.post("/projects", json={"name": "Test Project", "source_language": "en"})
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def xcstrings_project(admin_client: AsyncClient) -> dict:
    """Create a project and import Example.xcstrings into it."""
    resp = await admin_client.post("/projects", json={"name": "XCStrings Project", "source_language": "en"})
    assert resp.status_code == 201
    proj = resp.json()
    example = Path(__file__).parent.parent / "Example.xcstrings"
    imp = await admin_client.post(
        f"/projects/{proj['id']}/import",
        files={"file": (example.name, example.read_bytes(), "application/json")},
    )
    assert imp.status_code == 200
    return proj
