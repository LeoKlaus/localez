import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/localez_test"


def _make_engine():
    return create_async_engine(TEST_DATABASE_URL, echo=False)


def _make_session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
async def engine():
    e = _make_engine()
    yield e
    await e.dispose()


@pytest_asyncio.fixture(scope="session")
def session_factory(engine):
    return _make_session_factory(engine)


@pytest_asyncio.fixture(scope="session")
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

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, session_factory) -> AsyncClient:
    resp = await client.post("/auth/register", json={"username": "admin_user", "password": "adminpass123"})
    assert resp.status_code == 201

    async with session_factory() as session:
        from sqlalchemy import update
        from app.models.user import GlobalRole, User
        await session.execute(update(User).where(User.username == "admin_user").values(global_role=GlobalRole.admin))
        await session.commit()

    resp2 = await client.post("/auth/token", data={"username": "admin_user", "password": "adminpass123"})
    token = resp2.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
