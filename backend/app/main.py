from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.query import router as query_router
from app.api.upload import router as upload_router
from app.core.config import CORS_ALLOW_ORIGINS
from app.api.conversations import router as conversations_router
from app.api.voice import router as voice_router

# Create the FastAPI application.
app = FastAPI()

# Configure CORS for frontend access.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all API routes.
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(upload_router)
app.include_router(query_router)
app.include_router(conversations_router)
app.include_router(voice_router)