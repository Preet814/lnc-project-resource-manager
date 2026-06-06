"""Bootstrap data seeding for first-run setup."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.enums import Role, UserAccountStatus
from prm.infrastructure.db.models import UserModel
from prm.infrastructure.db.session import get_session_factory
from prm.infrastructure.security.password import BcryptPasswordHasher

BOOTSTRAP_ADMIN_USERNAME = "admin"
BOOTSTRAP_ADMIN_PASSWORD = "Admin@1234"
BOOTSTRAP_ADMIN_FULL_NAME = "System Administrator"
BOOTSTRAP_ADMIN_EMAIL = "admin@local"


def seed_bootstrap_admin(
    session: Session,
    *,
    password_hasher: BcryptPasswordHasher | None = None,
) -> bool:
    """Insert the first Admin account if it does not exist.

    Returns True when a new row is created, False when admin already exists.
    """
    hasher = password_hasher or BcryptPasswordHasher()
    existing = session.scalar(
        select(UserModel).where(UserModel.username == BOOTSTRAP_ADMIN_USERNAME)
    )
    if existing is not None:
        return False

    admin = UserModel(
        full_name=BOOTSTRAP_ADMIN_FULL_NAME,
        username=BOOTSTRAP_ADMIN_USERNAME,
        email=BOOTSTRAP_ADMIN_EMAIL,
        password_hash=hasher.hash(BOOTSTRAP_ADMIN_PASSWORD),
        role=Role.ADMIN,
        account_status=UserAccountStatus.ACTIVE,
        force_password_change=True,
    )
    session.add(admin)
    session.commit()
    return True


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        created = seed_bootstrap_admin(session)
        if created:
            print(f"Created bootstrap admin user '{BOOTSTRAP_ADMIN_USERNAME}'.")
        else:
            print(f"Bootstrap admin '{BOOTSTRAP_ADMIN_USERNAME}' already exists; skipped.")


if __name__ == "__main__":
    main()
