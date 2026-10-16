from __future__ import annotations

from fastapi import APIRouter

from sonoplan_api.schemas import CapabilitiesResponse, HealthResponse

router = APIRouter(tags=["system"])

SCHEMA_VERSION = "1.0"


@router.get("/api/v1/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok", schemaVersion=SCHEMA_VERSION)


@router.get(
    "/api/v1/capabilities",
    response_model=CapabilitiesResponse,
    summary="Engine capabilities (STUB)",
)
def get_capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        stub=True,
        engineProfileId=None,
        bandsHz=[],
        notes=[
            "STUB: registry is empty until engine/adapter publishes verified capabilities",
            "Do not present unsupported SPPS features as available in UI",
        ],
    )
