"""Domain entities (no ORM or HTTP imports)."""

from prm.domain.entities.allocation import Allocation
from prm.domain.entities.employee import Employee
from prm.domain.entities.skill import EmployeeSkill, Skill
from prm.domain.entities.user import User

__all__ = ["Allocation", "Employee", "EmployeeSkill", "Skill", "User"]
