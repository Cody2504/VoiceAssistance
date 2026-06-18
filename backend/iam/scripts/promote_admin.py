"""Promote a user to admin by email (idempotent first-admin bootstrap).

There is no UI to create the first admin — run this once against the iam
environment (it reads the same DB settings the service uses):

    # inside the iam container / environment (CWD = /app, PYTHONPATH=/app:/shared)
    python scripts/promote_admin.py vodinhhai7@gmail.com

    # or, if iam runs under docker compose:
    docker compose exec iam python scripts/promote_admin.py vodinhhai7@gmail.com

The user must already exist (sign up first). After promotion they must log out
and back in — the role is embedded in the JWT at login time.

Raw-SQL equivalent (no script):
    UPDATE users SET role='admin' WHERE email='vodinhhai7@gmail.com';
"""
import asyncio
import sys

from sqlalchemy import select

from cm_shared.db import get_sessionmaker
from main.models.user import User


async def _promote(email: str) -> int:
    async with get_sessionmaker()() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            print(f"No user with email {email!r}. Sign up first, then re-run.")
            return 1
        if user.role == "admin":
            print(f"{email} is already an admin — nothing to do.")
            return 0
        user.role = "admin"
        await session.commit()
        print(f"Promoted {email} to admin. Log out and back in to refresh the JWT.")
        return 0


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/promote_admin.py <email>")
        raise SystemExit(2)
    raise SystemExit(asyncio.run(_promote(sys.argv[1])))


if __name__ == "__main__":
    main()
