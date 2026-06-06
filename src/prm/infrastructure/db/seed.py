"""Bootstrap data seeding for first-run setup."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.api.settings import Settings, get_settings
from prm.domain.enums import Role, UserAccountStatus
from prm.infrastructure.db.models import UserModel
from prm.infrastructure.db.session import get_session_factory
from prm.infrastructure.security.password import BcryptPasswordHasher


def seed_bootstrap_admin(
    session: Session,
    *,
    username: str,
    password: str,
    full_name: str,
    email: str,
    password_hasher: BcryptPasswordHasher | None = None,
) -> bool:
    """Insert the first Admin account if it does not exist.

    Returns True when a new row is created, False when admin already exists.
    """
    hasher = password_hasher or BcryptPasswordHasher()
    existing = session.scalar(select(UserModel).where(UserModel.username == username))
    if existing is not None:
        return False

    admin = UserModel(
        full_name=full_name,
        username=username,
        email=email,
        password_hash=hasher.hash(password),
        role=Role.ADMIN,
        account_status=UserAccountStatus.ACTIVE,
        force_password_change=True,
    )
    session.add(admin)
    session.commit()
    return True


def seed_bootstrap_admin_from_settings(
    session: Session,
    settings: Settings | None = None,
    *,
    password_hasher: BcryptPasswordHasher | None = None,
) -> bool:
    """Seed bootstrap admin using values from environment / .env."""
    config = settings or get_settings()
    return seed_bootstrap_admin(
        session,
        username=config.bootstrap_admin_username,
        password=config.bootstrap_admin_password,
        full_name=config.bootstrap_admin_full_name,
        email=config.bootstrap_admin_email,
        password_hasher=password_hasher,
    )


def main() -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    with session_factory() as session:
        created = seed_bootstrap_admin_from_settings(session, settings)
        if created:
            print(f"Created bootstrap admin user '{settings.bootstrap_admin_username}'.")
        else:
            print(
                f"Bootstrap admin '{settings.bootstrap_admin_username}' already exists; skipped."
            )


if __name__ == "__main__":
    main()
