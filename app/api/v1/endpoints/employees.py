from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.employee import (
    EmployeeCreate,
    EmployeePage,
    EmployeeRead,
    EmployeeUpdate,
)
from app.services import employees as employee_service

router = APIRouter(prefix="/api/v1/employees")
DbSession = Annotated[Session, Depends(get_db)]


def _raise_http_error(error: Exception) -> NoReturn:
    if isinstance(error, employee_service.EmployeeNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        ) from error
    if isinstance(error, employee_service.EmployeeDepartmentNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        ) from error
    if isinstance(error, employee_service.EmployeeEmailConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An employee with this email already exists",
        ) from error
    if isinstance(error, employee_service.EmployeeAccountConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee cannot be deleted while a user account is linked",
        ) from error
    raise error


@router.post(
    "",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    employee_in: EmployeeCreate,
    db: DbSession,
) -> EmployeeRead:
    try:
        return employee_service.create_employee(db, employee_in)
    except (
        employee_service.EmployeeDepartmentNotFoundError,
        employee_service.EmployeeEmailConflictError,
    ) as error:
        _raise_http_error(error)


@router.get("", response_model=EmployeePage)
def list_employees(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    department_id: Annotated[int | None, Query(gt=0)] = None,
) -> EmployeePage:
    employees, total = employee_service.list_employees(
        db,
        page=page,
        page_size=page_size,
        department_id=department_id,
    )
    return EmployeePage(
        items=employees,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee(
    employee_id: int,
    db: DbSession,
) -> EmployeeRead:
    try:
        return employee_service.get_employee(db, employee_id)
    except employee_service.EmployeeNotFoundError as error:
        _raise_http_error(error)


@router.patch("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: int,
    employee_in: EmployeeUpdate,
    db: DbSession,
) -> EmployeeRead:
    try:
        return employee_service.update_employee(db, employee_id, employee_in)
    except (
        employee_service.EmployeeDepartmentNotFoundError,
        employee_service.EmployeeEmailConflictError,
        employee_service.EmployeeNotFoundError,
    ) as error:
        _raise_http_error(error)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: int, db: DbSession) -> Response:
    try:
        employee_service.delete_employee(db, employee_id)
    except (
        employee_service.EmployeeAccountConflictError,
        employee_service.EmployeeNotFoundError,
    ) as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
