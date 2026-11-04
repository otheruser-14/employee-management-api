from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Department, Employee
from app.schemas.department import DepartmentCreate, DepartmentUpdate

DEPARTMENT_NAME_CONSTRAINT = "uq_departments_name"
EMPLOYEE_DEPARTMENT_CONSTRAINT = "fk_employees_department_id_departments"


class DepartmentNotFoundError(Exception):
    pass


class DepartmentNameConflictError(Exception):
    pass


class DepartmentHasEmployeesError(Exception):
    pass


def _constraint_name(error: IntegrityError) -> str | None:
    return getattr(getattr(error.orig, "diag", None), "constraint_name", None)


def _commit_department_change(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        constraint_name = _constraint_name(error)
        if constraint_name == DEPARTMENT_NAME_CONSTRAINT:
            raise DepartmentNameConflictError from error
        if constraint_name == EMPLOYEE_DEPARTMENT_CONSTRAINT:
            raise DepartmentHasEmployeesError from error
        raise


def create_department(db: Session, department_in: DepartmentCreate) -> Department:
    duplicate = db.scalar(
        select(Department.id).where(Department.name == department_in.name)
    )
    if duplicate is not None:
        raise DepartmentNameConflictError

    department = Department(**department_in.model_dump())
    db.add(department)
    _commit_department_change(db)
    db.refresh(department)
    return department


def list_departments(
    db: Session,
    *,
    page: int,
    page_size: int,
) -> tuple[list[Department], int]:
    total = db.scalar(select(func.count()).select_from(Department)) or 0
    departments = list(
        db.scalars(
            select(Department)
            .order_by(Department.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return departments, total


def get_department(db: Session, department_id: int) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise DepartmentNotFoundError
    return department


def update_department(
    db: Session,
    department_id: int,
    department_in: DepartmentUpdate,
) -> Department:
    department = get_department(db, department_id)
    updates = department_in.model_dump(exclude_unset=True)

    if "name" in updates:
        duplicate = db.scalar(
            select(Department.id).where(
                Department.name == updates["name"],
                Department.id != department_id,
            )
        )
        if duplicate is not None:
            raise DepartmentNameConflictError

    for field, value in updates.items():
        setattr(department, field, value)

    if updates:
        _commit_department_change(db)
        db.refresh(department)
    return department


def delete_department(db: Session, department_id: int) -> None:
    department = get_department(db, department_id)
    has_employees = db.scalar(
        select(Employee.id).where(Employee.department_id == department_id).limit(1)
    )
    if has_employees is not None:
        raise DepartmentHasEmployeesError

    db.delete(department)
    _commit_department_change(db)
