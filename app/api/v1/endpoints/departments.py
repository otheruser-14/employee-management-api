from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.department import (
    DepartmentCreate,
    DepartmentPage,
    DepartmentRead,
    DepartmentUpdate,
)
from app.services import departments as department_service

router = APIRouter(prefix="/api/v1/departments")
DbSession = Annotated[Session, Depends(get_db)]


def _raise_http_error(error: Exception) -> NoReturn:
    if isinstance(error, department_service.DepartmentNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        ) from error
    if isinstance(error, department_service.DepartmentNameConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A department with this name already exists",
        ) from error
    if isinstance(error, department_service.DepartmentHasEmployeesError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department cannot be deleted while employees are assigned",
        ) from error
    raise error


@router.post(
    "",
    response_model=DepartmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    department_in: DepartmentCreate,
    db: DbSession,
) -> DepartmentRead:
    try:
        return department_service.create_department(db, department_in)
    except department_service.DepartmentNameConflictError as error:
        _raise_http_error(error)


@router.get("", response_model=DepartmentPage)
def list_departments(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DepartmentPage:
    departments, total = department_service.list_departments(
        db,
        page=page,
        page_size=page_size,
    )
    return DepartmentPage(
        items=departments,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{department_id}", response_model=DepartmentRead)
def get_department(
    department_id: int,
    db: DbSession,
) -> DepartmentRead:
    try:
        return department_service.get_department(db, department_id)
    except department_service.DepartmentNotFoundError as error:
        _raise_http_error(error)


@router.patch("/{department_id}", response_model=DepartmentRead)
def update_department(
    department_id: int,
    department_in: DepartmentUpdate,
    db: DbSession,
) -> DepartmentRead:
    try:
        return department_service.update_department(db, department_id, department_in)
    except (
        department_service.DepartmentNameConflictError,
        department_service.DepartmentNotFoundError,
    ) as error:
        _raise_http_error(error)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(department_id: int, db: DbSession) -> Response:
    try:
        department_service.delete_department(db, department_id)
    except (
        department_service.DepartmentHasEmployeesError,
        department_service.DepartmentNotFoundError,
    ) as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
