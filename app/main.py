from fastapi import FastAPI

from app.api.v1.router import api_router

app = FastAPI(
    title="Employee Management API",
    version="0.1.0",
    description="API foundation for employee and department management.",
)
app.include_router(api_router)
