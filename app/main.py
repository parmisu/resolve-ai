from fastapi import FastAPI
from pydantic import BaseModel

from app.api.tickets import router as tickets_router

app = FastAPI(
    title="ResolveAI API",
    description="Customer support ticket management for TaskFlow.",
    version="0.1.0",
)


class HealthResponse(BaseModel):
    status: str


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Check whether the API is running",
)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


app.include_router(tickets_router)
