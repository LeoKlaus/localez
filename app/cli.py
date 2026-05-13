"""
Management CLI for localez.

Usage:
    python -m app.cli create-admin --username <name> --password <pass>
    python -m app.cli promote-admin --username <name>
    python -m app.cli list-admins
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.recovery import generate_recovery_words, hash_recovery_words
from app.core.security import hash_password
from app.database import Base
from app.models.user import GlobalRole, User


def _build_engine():
    url = (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )
    return create_async_engine(url, echo=False)


async def _create_admin(username: str, password: str) -> None:
    engine = _build_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        existing = await session.scalar(select(User).where(User.username == username))
        if existing is not None:
            if existing.global_role == GlobalRole.admin:
                print(f"User '{username}' already exists and is already an admin.")
            else:
                existing.global_role = GlobalRole.admin
                await session.commit()
                print(f"User '{username}' already exists — promoted to admin.")
            await engine.dispose()
            return

        recovery_words = generate_recovery_words()
        user = User(
            username=username,
            hashed_password=hash_password(password),
            global_role=GlobalRole.admin,
            recovery_word_hash=hash_recovery_words(recovery_words),
        )
        session.add(user)
        await session.commit()

    await engine.dispose()

    print(f"Admin user '{username}' created successfully.")
    print()
    print("Recovery words (store these somewhere safe — shown only once):")
    print("  " + " ".join(recovery_words))


async def _promote_admin(username: str) -> None:
    engine = _build_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        user = await session.scalar(select(User).where(User.username == username))
        if user is None:
            print(f"Error: user '{username}' not found.", file=sys.stderr)
            await engine.dispose()
            sys.exit(1)

        if user.global_role == GlobalRole.admin:
            print(f"User '{username}' is already an admin.")
            await engine.dispose()
            return

        user.global_role = GlobalRole.admin
        await session.commit()

    await engine.dispose()
    print(f"User '{username}' promoted to admin.")


async def _list_admins() -> None:
    engine = _build_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        result = await session.execute(select(User).where(User.global_role == GlobalRole.admin))
        admins = result.scalars().all()

    await engine.dispose()

    if not admins:
        print("No admin users found.")
        return

    print(f"{'Username':<30} {'Active':<8} {'Created'}")
    print("-" * 60)
    for u in admins:
        created = u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "—"
        print(f"{u.username:<30} {'yes' if u.is_active else 'no':<8} {created}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="localez management CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create-admin
    p_create = sub.add_parser("create-admin", help="Create a new admin user (or promote existing)")
    p_create.add_argument("--username", required=True, help="Username for the admin account")
    p_create.add_argument(
        "--password",
        help="Password (omit to be prompted securely)",
    )

    # promote-admin
    p_promote = sub.add_parser("promote-admin", help="Promote an existing user to admin")
    p_promote.add_argument("--username", required=True, help="Username to promote")

    # list-admins
    sub.add_parser("list-admins", help="List all admin users")

    args = parser.parse_args()

    if args.command == "create-admin":
        password = args.password
        if not password:
            password = getpass.getpass("Password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Error: passwords do not match.", file=sys.stderr)
                sys.exit(1)
        if len(password) < 8:
            print("Error: password must be at least 8 characters.", file=sys.stderr)
            sys.exit(1)
        asyncio.run(_create_admin(args.username.lower(), password))

    elif args.command == "promote-admin":
        asyncio.run(_promote_admin(args.username.lower()))

    elif args.command == "list-admins":
        asyncio.run(_list_admins())


if __name__ == "__main__":
    main()
