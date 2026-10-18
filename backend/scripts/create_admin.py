import argparse
import asyncio
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User


async def create_admin(email: str, password: str, full_name: str, role: str) -> None:
    """
    Safely provisions an administrative user (system_admin or hospital_admin)
    directly into the medismart_db database using Argon2id password hashing.
    """
    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.", file=sys.stderr)
        sys.exit(1)

    if role not in {"system_admin", "hospital_admin"}:
        print("Error: Role must be either 'system_admin' or 'hospital_admin'.", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        # Check if email already exists
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Error: User with email '{email}' already exists.", file=sys.stderr)
            sys.exit(1)

        hashed_password = get_password_hash(password)
        new_admin = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_active=True,
        )

        session.add(new_admin)
        await session.commit()
        await session.refresh(new_admin)

        print(f"Successfully provisioned administrative user '{email}' with role '{role}' (ID: {new_admin.id}).")


def main():
    parser = argparse.ArgumentParser(description="Provision an administrative user for MediSmart")
    parser.add_argument("--email", required=True, help="Administrator email address")
    parser.add_argument("--password", required=True, help="Administrator password (min 8 characters)")
    parser.add_argument("--name", required=True, help="Full name of the administrator")
    parser.add_argument(
        "--role",
        choices=["system_admin", "hospital_admin"],
        default="system_admin",
        help="Administrative role (default: system_admin)",
    )

    args = parser.parse_args()
    asyncio.run(create_admin(args.email, args.password, args.name, args.role))


if __name__ == "__main__":
    main()
