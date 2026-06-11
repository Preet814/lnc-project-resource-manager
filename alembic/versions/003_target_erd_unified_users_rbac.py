"""target ERD: unified users, RBAC, resource_status

Revision ID: 003_target_erd
Revises: 002_manager_id_story_pts
Create Date: 2026-06-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_target_erd"
down_revision: str | None = "002_manager_id_story_pts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- lookup tables ---
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("hierarchy_rank", sa.Integer(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("hierarchy_level", sa.Integer(), nullable=False),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "designations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("track", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # seed roles
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("hierarchy_rank", sa.Integer),
        sa.column("is_system", sa.Boolean),
    )
    op.bulk_insert(
        roles,
        [
            {"id": 1, "code": "ENGINEER", "name": "Engineer", "hierarchy_rank": 1, "is_system": True},
            {"id": 2, "code": "MANAGER", "name": "Manager", "hierarchy_rank": 2, "is_system": True},
            {"id": 3, "code": "ADMIN", "name": "Admin", "hierarchy_rank": 3, "is_system": True},
        ],
    )

    dept = sa.table("departments", sa.column("id", sa.Integer), sa.column("name", sa.String))
    op.bulk_insert(
        dept,
        [{"name": n} for n in ("IT", "Engineering", "Backend", "Frontend", "DevOps", "QA", "Delivery")],
    )
    desig = sa.table(
        "designations",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("track", sa.String),
    )
    op.bulk_insert(
        desig,
        [
            {"name": "System Administrator", "track": "ADMIN"},
            {"name": "Program Manager", "track": "MANAGEMENT"},
            {"name": "Project Manager", "track": "MANAGEMENT"},
            {"name": "SSE", "track": "IC"},
            {"name": "SE", "track": "IC"},
            {"name": "JSE", "track": "IC"},
        ],
    )

    perms = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("hierarchy_level", sa.Integer),
        sa.column("module", sa.String),
    )
    permission_rows = [
        ("timesheet:submit", "Submit timesheet", 1, "TIMESHEET"),
        ("timesheet:view_own", "View own timesheets", 1, "TIMESHEET"),
        ("allocation:view_own", "View own allocations", 1, "ALLOCATION"),
        ("resource:search_ai", "AI resource search", 2, "RESOURCE"),
        ("allocation:create", "Create allocation", 2, "ALLOCATION"),
        ("allocation:end", "End allocation", 2, "ALLOCATION"),
        ("project:health_view", "View project health", 2, "PROJECT"),
        ("timesheet:view_team", "View team timesheets", 2, "TIMESHEET"),
        ("llm:skill_match", "LLM skill match", 2, "LLM"),
        ("llm:risk_summary", "LLM risk summary", 2, "LLM"),
        ("resource:view_dashboard", "Resource dashboard", 2, "RESOURCE"),
        ("user:create", "Create user", 3, "USER"),
        ("user:deactivate", "Deactivate user", 3, "USER"),
        ("user:reset_password", "Reset password", 3, "USER"),
        ("engineer:manage", "Manage engineers", 3, "ENGINEER"),
        ("engineer:assign_manager", "Assign manager", 3, "ENGINEER"),
        ("skill:manage_any", "Manage any user skills", 3, "SKILL"),
        ("project:create", "Create project", 3, "PROJECT"),
        ("milestone:manage", "Manage milestones", 3, "PROJECT"),
        ("allocation:view_all", "View all allocations", 3, "ALLOCATION"),
        ("config:manage", "Manage system config", 3, "CONFIG"),
        ("role:manage", "Manage roles and permissions", 3, "RBAC"),
    ]
    op.bulk_insert(
        perms,
        [
            {"code": c, "name": n, "hierarchy_level": lvl, "module": m}
            for c, n, lvl, m in permission_rows
        ],
    )

    # role_permissions via SQL
    role_perm_map = {
        1: [c for c, _, lvl, _ in permission_rows if lvl == 1],
        2: [c for c, _, lvl, _ in permission_rows if lvl == 2],
        3: [c for c, _, lvl, _ in permission_rows if lvl == 3],
    }
    conn = op.get_bind()
    for role_id, codes in role_perm_map.items():
        for code in codes:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT :role_id, p.id FROM permissions p WHERE p.code = :code
                    """
                ),
                {"role_id": role_id, "code": code},
            )

    # --- extend users ---
    op.add_column("users", sa.Column("role_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("department_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("designation_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("manager_id", sa.Integer(), nullable=True))

    # map legacy role enum to role_id
    conn.execute(sa.text("UPDATE users SET role_id = 1 WHERE role = 'EMPLOYEE'"))
    conn.execute(sa.text("UPDATE users SET role_id = 2 WHERE role = 'MANAGER'"))
    conn.execute(sa.text("UPDATE users SET role_id = 3 WHERE role = 'ADMIN'"))

    # default dept/designation for users without employee row
    conn.execute(
        sa.text(
            """
            UPDATE users SET department_id = (SELECT id FROM departments WHERE name = 'IT' LIMIT 1)
            WHERE department_id IS NULL
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE users SET designation_id = (
                SELECT id FROM designations WHERE name = 'System Administrator' LIMIT 1
            )
            WHERE designation_id IS NULL AND role_id = 3
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE users SET designation_id = (
                SELECT id FROM designations WHERE name = 'Project Manager' LIMIT 1
            )
            WHERE designation_id IS NULL AND role_id = 2
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE users SET designation_id = (
                SELECT id FROM designations WHERE name = 'SE' LIMIT 1
            )
            WHERE designation_id IS NULL AND role_id = 1
            """
        )
    )

    # merge employee profile into users
    conn.execute(
        sa.text(
            """
            UPDATE users u SET
                department_id = COALESCE(
                    (SELECT d.id FROM departments d
                     JOIN employees e ON e.user_id = u.id
                     WHERE d.name = e.department LIMIT 1),
                    u.department_id
                ),
                designation_id = COALESCE(
                    (SELECT g.id FROM designations g
                     JOIN employees e ON e.user_id = u.id
                     WHERE g.name = e.designation LIMIT 1),
                    u.designation_id
                ),
                manager_id = (SELECT e.manager_id FROM employees e WHERE e.user_id = u.id LIMIT 1)
            WHERE EXISTS (SELECT 1 FROM employees e WHERE e.user_id = u.id)
            """
        )
    )

    # insert department/designation rows from employee strings not in lookup
    conn.execute(
        sa.text(
            """
            INSERT INTO departments (name)
            SELECT DISTINCT e.department FROM employees e
            WHERE e.department IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM departments d WHERE d.name = e.department)
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO designations (name, track)
            SELECT DISTINCT e.designation, 'IC' FROM employees e
            WHERE e.designation IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM designations g WHERE g.name = e.designation)
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE users u SET
                department_id = (SELECT d.id FROM departments d
                                 JOIN employees e ON e.user_id = u.id AND d.name = e.department),
                designation_id = (SELECT g.id FROM designations g
                                  JOIN employees e ON e.user_id = u.id AND g.name = e.designation)
            WHERE EXISTS (SELECT 1 FROM employees e WHERE e.user_id = u.id)
            """
        )
    )

    op.alter_column("users", "role_id", nullable=False)
    op.alter_column("users", "department_id", nullable=False)
    op.alter_column("users", "designation_id", nullable=False)

    op.create_foreign_key("fk_users_role_id", "users", "roles", ["role_id"], ["id"])
    op.create_foreign_key(
        "fk_users_department_id", "users", "departments", ["department_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_users_designation_id", "users", "designations", ["designation_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_users_manager_id", "users", "users", ["manager_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index(op.f("ix_users_role_id"), "users", ["role_id"], unique=False)
    op.create_index(op.f("ix_users_department_id"), "users", ["department_id"], unique=False)
    op.create_index(op.f("ix_users_designation_id"), "users", ["designation_id"], unique=False)
    op.create_index(op.f("ix_users_manager_id"), "users", ["manager_id"], unique=False)

    op.drop_column("users", "role")

    # resource_status from employees (engineers only)
    op.create_table(
        "resource_status",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "work_status",
            sa.Enum("BENCH", "ALLOCATED", name="resource_work_status", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("utilisation_percent", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO resource_status (user_id, work_status, utilisation_percent)
            SELECT e.user_id, e.work_status, e.current_utilisation_percent
            FROM employees e
            JOIN users u ON u.id = e.user_id
            WHERE e.user_id IS NOT NULL AND u.role_id = 1 AND e.is_active = true
            """
        )
    )

    # allocations: employee_id -> user_id
    op.add_column("allocations", sa.Column("user_id", sa.Integer(), nullable=True))
    conn.execute(
        sa.text(
            """
            UPDATE allocations a SET user_id = (
                SELECT e.user_id FROM employees e WHERE e.id = a.employee_id
            )
            """
        )
    )
    op.drop_constraint("allocations_employee_id_fkey", "allocations", type_="foreignkey")
    op.drop_index(op.f("ix_allocations_employee_id"), table_name="allocations")
    op.drop_column("allocations", "employee_id")
    op.alter_column("allocations", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_allocations_user_id", "allocations", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(op.f("ix_allocations_user_id"), "allocations", ["user_id"], unique=False)

    # timesheet_weeks: employee_id -> user_id
    op.add_column("timesheet_weeks", sa.Column("user_id", sa.Integer(), nullable=True))
    conn.execute(
        sa.text(
            """
            UPDATE timesheet_weeks t SET user_id = (
                SELECT e.user_id FROM employees e WHERE e.id = t.employee_id
            )
            """
        )
    )
    op.drop_constraint("timesheet_weeks_employee_id_fkey", "timesheet_weeks", type_="foreignkey")
    op.drop_index(op.f("ix_timesheet_weeks_employee_id"), table_name="timesheet_weeks")
    op.drop_column("timesheet_weeks", "employee_id")
    op.alter_column("timesheet_weeks", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_timesheet_weeks_user_id",
        "timesheet_weeks",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_timesheet_weeks_user_id"), "timesheet_weeks", ["user_id"], unique=False)

    # employee_skills -> user_skills
    op.add_column("employee_skills", sa.Column("user_id", sa.Integer(), nullable=True))
    conn.execute(
        sa.text(
            """
            UPDATE employee_skills es SET user_id = (
                SELECT e.user_id FROM employees e WHERE e.id = es.employee_id
            )
            """
        )
    )
    op.drop_constraint("employee_skills_employee_id_fkey", "employee_skills", type_="foreignkey")
    op.drop_index(op.f("ix_employee_skills_employee_id"), table_name="employee_skills")
    op.drop_column("employee_skills", "employee_id")
    op.alter_column("employee_skills", "user_id", nullable=False)
    op.rename_table("employee_skills", "user_skills")
    op.create_foreign_key(
        "fk_user_skills_user_id", "user_skills", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(op.f("ix_user_skills_user_id"), "user_skills", ["user_id"], unique=False)

    # drop employees
    op.drop_constraint("fk_employees_manager_id_users", "employees", type_="foreignkey")
    op.drop_index(op.f("ix_employees_manager_id"), table_name="employees")
    op.drop_table("employees")


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for 003_target_erd")
