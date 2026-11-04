from fastapi import APIRouter

from app.api.v1.endpoints import departments, employees, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(departments.router, tags=["departments"])
api_router.include_router(employees.router, tags=["employees"])
