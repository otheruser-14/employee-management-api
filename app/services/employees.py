from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Department, Employee
from app.schemas.employee import EmployeeCreate, EmployeeUpdate

EMPLOYEE_EMAIL_CONSTRAINT = "uq_employees_email"
EMPLOYEE_DEPARTMENT_CONSTRAINT = "fk_employees_department_id_departments"
USER_EMPLOYEE_CONSTRAINT = "fk_users_employee_id_employees"


class EmployeeNotFoundError(Exception):
    pass


class EmployeeEmailConflictError(Exception):
    pass


class EmployeeDepartmentNotFoundError(Exception):
    pass


class EmployeeAccountConflictError(Exception):
    pass


def _constraint_name(error: IntegrityError) -> str | None:
    return getattr(getattr(error.orig, "diag", None), "constraint_name", None)


def _commit_employee_change(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        constraint_name = _constraint_name(error)
        if constraint_name == EMPLOYEE_EMAIL_CONSTRAINT:
            raise EmployeeEmailConflictError from error
        if constraint_name == EMPLOYEE_DEPARTMENT_CONSTRAINT:
            raise EmployeeDepartmentNotFoundError from error
        if constraint_name == USER_EMPLOYEE_CONSTRAINT:
            raise EmployeeAccountConflictError from error
        raise


def _require_department(db: Session, department_id: int) -> None:
    if db.get(Department, department_id) is None:
        raise EmployeeDepartmentNotFoundError


def create_employee(db: Session, employee_in: EmployeeCreate) -> Employee:
    _require_department(db, employee_in.department_id)
    duplicate = db.scalar(
        select(Employee.id).where(Employee.email == employee_in.email)
    )
    if duplicate is not None:
        raise EmployeeEmailConflictError

    employee = Employee(**employee_in.model_dump())
    db.add(employee)
    _commit_employee_change(db)
    db.refresh(employee)
    return employee


def list_employees(
    db: Session,
    *,
    page: int,
    page_size: int,
    department_id: int | None,
) -> tuple[list[Employee], int]:
    statement = select(Employee)
    count_statement = select(func.count()).select_from(Employee)
    if department_id is not None:
        statement = statement.where(Employee.department_id == department_id)
        count_statement = count_statement.where(Employee.department_id == department_id)

    total = db.scalar(count_statement) or 0
    employees = list(
        db.scalars(
            statement.order_by(Employee.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return employees, total


def get_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise EmployeeNotFoundError
    return employee


def update_employee(
    db: Session,
    employee_id: int,
    employee_in: EmployeeUpdate,
) -> Employee:
    employee = get_employee(db, employee_id)
    updates = employee_in.model_dump(exclude_unset=True)

    if "department_id" in updates:
        _require_department(db, updates["department_id"])
    if "email" in updates:
        duplicate = db.scalar(
            select(Employee.id).where(
                Employee.email == updates["email"],
                Employee.id != employee_id,
            )
        )
        if duplicate is not None:
            raise EmployeeEmailConflictError

    for field, value in updates.items():
        setattr(employee, field, value)

    if updates:
        _commit_employee_change(db)
        db.refresh(employee)
    return employee


def delete_employee(db: Session, employee_id: int) -> None:
    employee = get_employee(db, employee_id)
    db.delete(employee)
    _commit_employee_change(db)
