"""Employee persistence via SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.entities.employee import Employee
from prm.domain.enums import EmployeeWorkStatus
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import EmployeeModel


def _to_domain(model: EmployeeModel) -> Employee:
    return Employee(
        id=model.id,
        user_id=model.user_id,
        full_name=model.full_name,
        email=model.email,
        department=model.department,
        designation=model.designation,
        work_status=model.work_status,
        is_active=model.is_active,
        current_utilisation_percent=model.current_utilisation_percent,
        created_at=model.created_at,
    )


class SqlAlchemyEmployeeRepository:
    """Load and update employees from the employees table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, employee_id: int) -> Employee | None:
        model = self._session.get(EmployeeModel, employee_id)
        return _to_domain(model) if model is not None else None

    def find_by_user_id(self, user_id: int) -> Employee | None:
        model = self._session.scalar(
            select(EmployeeModel).where(EmployeeModel.user_id == user_id)
        )
        return _to_domain(model) if model is not None else None

    def find_by_email(self, email: str) -> Employee | None:
        model = self._session.scalar(
            select(EmployeeModel).where(EmployeeModel.email == email)
        )
        return _to_domain(model) if model is not None else None

    def list_all(
        self,
        *,
        work_status: EmployeeWorkStatus | None = None,
        department: str | None = None,
        active_only: bool = True,
    ) -> list[Employee]:
        stmt = select(EmployeeModel)
        if active_only:
            stmt = stmt.where(EmployeeModel.is_active.is_(True))
        if work_status is not None:
            stmt = stmt.where(EmployeeModel.work_status == work_status)
        if department is not None:
            stmt = stmt.where(EmployeeModel.department == department)
        models = self._session.scalars(stmt.order_by(EmployeeModel.id)).all()
        return [_to_domain(model) for model in models]

    def create(
        self,
        *,
        user_id: int,
        full_name: str,
        email: str,
        department: str,
        designation: str,
    ) -> Employee:
        model = EmployeeModel(
            user_id=user_id,
            full_name=full_name,
            email=email,
            department=department,
            designation=designation,
            work_status=EmployeeWorkStatus.BENCH,
            is_active=True,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def update(
        self,
        employee_id: int,
        *,
        full_name: str | None = None,
        email: str | None = None,
        department: str | None = None,
        designation: str | None = None,
    ) -> Employee:
        model = self._session.get(EmployeeModel, employee_id)
        if model is None:
            raise NotFoundError(f"Employee {employee_id} not found.")

        if full_name is not None:
            model.full_name = full_name
        if email is not None:
            model.email = email
        if department is not None:
            model.department = department
        if designation is not None:
            model.designation = designation

        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def set_active(self, employee_id: int, *, is_active: bool) -> Employee:
        model = self._session.get(EmployeeModel, employee_id)
        if model is None:
            raise NotFoundError(f"Employee {employee_id} not found.")

        model.is_active = is_active
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def update_utilisation_and_status(
        self,
        employee_id: int,
        *,
        current_utilisation_percent: int,
        work_status: EmployeeWorkStatus,
    ) -> Employee:
        model = self._session.get(EmployeeModel, employee_id)
        if model is None:
            raise NotFoundError(f"Employee {employee_id} not found.")

        model.current_utilisation_percent = current_utilisation_percent
        model.work_status = work_status
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)
