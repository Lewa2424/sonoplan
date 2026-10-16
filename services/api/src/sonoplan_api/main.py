"""SonoPlan FastAPI application: health, capabilities stub, projects/draft/revisions."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sonoplan_api.routers import projects, revisions, system

app = FastAPI(
    title="SonoPlan API",
    version="0.0.0-stg02",
    description=(
        "STG-02: projects, draft ETag, revisions, validate. "
        "Acoustic calculation endpoints are not implemented yet. "
        "Capabilities remain stub:true until STG-01 verifies SPPS."
    ),
)

# Dev CORS for apps/web (Vite). Expose ETag for draft If-Match sync (STG-03).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag"],
)

app.include_router(system.router)
app.include_router(projects.router)
app.include_router(revisions.router)
