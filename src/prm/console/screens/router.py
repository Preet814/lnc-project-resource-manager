"""Route authenticated users to role-specific menus."""

from prm.console.client import PrmApiClient
from prm.console.screens.admin import menu as admin_menu
from prm.console.screens.engineer import menu as engineer_menu
from prm.console.screens.manager import menu as manager_menu
from prm.console.session import UserSession
from prm.domain.enums import Role


def run_role_menu(client: PrmApiClient, session: UserSession) -> str:
    """Display the menu for the logged-in role. Returns 'logout'."""
    if session.role == Role.ADMIN:
        return admin_menu.run(client, session)
    if session.role == Role.MANAGER:
        return manager_menu.run(client, session)
    if session.role == Role.ENGINEER:
        return engineer_menu.run(session)
    return "logout"
