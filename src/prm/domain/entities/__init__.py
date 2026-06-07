"""Domain entities (no ORM or HTTP imports)."""

from prm.domain.entities.allocation import Allocation
from prm.domain.entities.employee import Employee
from prm.domain.entities.milestone import Milestone
from prm.domain.entities.project import Project
from prm.domain.entities.skill import EmployeeSkill, Skill
from prm.domain.entities.system_configuration import SystemConfiguration
from prm.domain.entities.user import User

__all__ = [
    "Allocation",
    "Employee",
    "EmployeeSkill",
    "Milestone",
    "Project",
    "Skill",
    "SystemConfiguration",
    "User",
]
