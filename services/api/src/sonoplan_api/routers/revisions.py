from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from sonoplan_api.db import get_db
from sonoplan_api.models import RevisionRow
from sonoplan_api.schemas import ValidateResponse, ValidationIssue
from sonoplan_api.validate_model import validate_model

router = APIRouter(tags=["revisions"])


@router.post("/api/v1/revisions/{revision_id}/validate", response_model=ValidateResponse)
def validate_revision(revision_id: str, db: Session = Depends(get_db)) -> ValidateResponse:
    revision = db.get(RevisionRow, revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Revision not found")

    result = validate_model(revision.snapshot)
    errors = [ValidationIssue(**e) for e in result["errors"]]
    warnings = [ValidationIssue(**w) for w in result["warnings"]]
    return ValidateResponse(
        revisionId=revision.id,
        snapshotHash=revision.snapshot_hash,
        ok=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
