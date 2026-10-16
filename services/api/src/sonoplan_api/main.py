"""SonoPlan FastAPI application: health, projects/draft/revisions, jobs."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sonoplan_api.routers import jobs, projects, revisions, system

app = FastAPI(
    title="SonoPlan API",
    version="0.0.0-stg04",
    description=(
        "STG-04: projects, draft ETag, revisions, validate, calculation jobs. "
        "Jobs bind to revisionId+snapshotHash; worker→adapter→SPPS. "
        "No invented heatmaps. Capabilities remain stub:true until verified profile."
    ),
)

# Dev CORS for apps/web (Vite). Expose ETag for draft If-Match sync (STG-03).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://[::1]:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag"],
)

app.include_router(system.router)
app.include_router(projects.router)
app.include_router(revisions.router)
app.include_router(jobs.router)
