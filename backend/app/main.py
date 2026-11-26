from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app import models  # noqa: F401
from backend.app.database import Base, engine
from backend.app.routers.ai import router as ai_router
from backend.app.routers.analytics import router as analytics_router
from backend.app.routers.mood_sleep import router as mood_sleep_router
from backend.app.routers.rag import router as rag_router
from backend.app.routers.symptoms import router as symptoms_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize database tables on application startup."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="HealthTrack AI", version="0.1.0", lifespan=lifespan)
app.include_router(symptoms_router)
app.include_router(analytics_router)
app.include_router(mood_sleep_router)
app.include_router(ai_router)
app.include_router(rag_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "HealthTrack AI API"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
