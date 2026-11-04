from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class EmployeeCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    hire_date: date
    department_id: int = Field(gt=0)
    phone: str | None = Field(default=None, max_length=32)
    job_title: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    hire_date: date | None = None
    department_id: int | None = Field(default=None, gt=0)
    phone: str | None = Field(default=None, max_length=32)
    job_title: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None

    @model_validator(mode="after")
    def required_fields_cannot_be_null(self) -> "EmployeeUpdate":
        required_fields = {
            "first_name",
            "last_name",
            "email",
            "hire_date",
            "department_id",
            "is_active",
        }
        null_fields = required_fields.intersection(self.model_fields_set)
        null_fields = {field for field in null_fields if getattr(self, field) is None}
        if null_fields:
            names = ", ".join(sorted(null_fields))
            raise ValueError(f"{names} cannot be null")
        return self


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None
    job_title: str | None
    hire_date: date
    is_active: bool
    department_id: int
    created_at: datetime
    updated_at: datetime


class EmployeePage(BaseModel):
    items: list[EmployeeRead]
    total: int
    page: int
    page_size: int
