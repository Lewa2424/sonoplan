"""Dispatch product SPPS jobs to GitHub Actions and sync results via artifacts.

Free path: public repo → standard runners are $0. Local API polls GitHub
(no public callback URL required). Phase 1 still uses fixture mesh inputs.
"""

from __future__ import annotations

import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from sonoplan_api.models import JobRow

API_VERSION = "2022-11-28"
DEFAULT_WORKFLOW = "run-spps-product-job.yml"
RUN_NAME_PREFIX = "sonoplan-job-"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def jobs_backend() -> str:
    """
    Job execution backend.

    - inline (default): execute in API process (fixture_replay on Windows).
    - github_actions: dispatch workflow; poll artifact on GET.
    - celery: legacy SONOPLAN_JOBS_INLINE=0 path.
    """
    explicit = os.environ.get("SONOPLAN_JOBS_BACKEND", "").strip().lower()
    if explicit in ("inline", "github_actions", "celery"):
        return explicit
    if os.environ.get("SONOPLAN_JOBS_INLINE", "1") == "0":
        return "celery"
    return "inline"


def github_config() -> dict[str, str]:
    token = (
        os.environ.get("SONOPLAN_GITHUB_TOKEN", "").strip()
        or os.environ.get("GITHUB_TOKEN", "").strip()
        or os.environ.get("GH_TOKEN", "").strip()
    )
    repo = (
        os.environ.get("SONOPLAN_GITHUB_REPOSITORY", "").strip()
        or os.environ.get("GITHUB_REPOSITORY", "").strip()
        or "Lewa2424/sonoplan"
    )
    workflow = (
        os.environ.get("SONOPLAN_GH_WORKFLOW", "").strip() or DEFAULT_WORKFLOW
    )
    ref = os.environ.get("SONOPLAN_GH_REF", "").strip() or "main"
    return {
        "token": token,
        "repo": repo,
        "workflow": workflow,
        "ref": ref,
    }


def _api_request(
    method: str,
    path: str,
    *,
    token: str,
    body: dict[str, Any] | None = None,
    accept: str = "application/vnd.github+json",
) -> tuple[int, Any]:
    url = f"https://api.github.com{path}"
    data = None
    headers = {
        "Accept": accept,
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "SonoPlan-API-github-actions-worker",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            code = resp.getcode()
            if not raw:
                return code, None
            if accept.startswith("application/vnd.github+json") or "json" in accept:
                return code, json.loads(raw.decode("utf-8"))
            return code, raw
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(err_body) if err_body else {"message": str(exc)}
        except json.JSONDecodeError:
            parsed = {"message": err_body or str(exc)}
        return exc.code, parsed


def pending_manifest(
    *,
    job_id: str,
    revision_id: str,
    snapshot_hash: str,
    repo: str,
    workflow: str,
    run_id: int | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "jobId": job_id,
        "revisionId": revision_id,
        "snapshotHash": snapshot_hash,
        "mapAvailable": False,
        "mapDeferredReason": "GitHub Actions SPPS run in progress",
        "punctualReceivers": [],
        "executionMode": "github_actions_pending",
        "github": {
            "repository": repo,
            "workflow": workflow,
            "runId": run_id,
            "runName": f"{RUN_NAME_PREFIX}{job_id}",
        },
        "notes": [
            "Job dispatched to GitHub Actions (free Linux worker). "
            "Poll GET /jobs/{id} until completed.",
        ],
    }


def dispatch_product_job(
    *,
    job_id: str,
    revision_id: str,
    snapshot_hash: str,
    export_json: str = "",
) -> dict[str, Any]:
    """Trigger workflow_dispatch. Returns github meta or raises RuntimeError."""
    cfg = github_config()
    if not cfg["token"]:
        raise RuntimeError(
            "SONOPLAN_GITHUB_TOKEN (or GITHUB_TOKEN) is required for "
            "SONOPLAN_JOBS_BACKEND=github_actions"
        )
    owner, _, name = cfg["repo"].partition("/")
    if not owner or not name:
        raise RuntimeError(f"Invalid GITHUB_REPOSITORY: {cfg['repo']}")

    # GitHub workflow_dispatch input size is limited (~100 KiB practical).
    if len(export_json) > 90_000:
        raise RuntimeError(
            f"export_json too large ({len(export_json)} chars) for workflow_dispatch"
        )

    path = (
        f"/repos/{owner}/{name}/actions/workflows/"
        f"{urllib.parse.quote(cfg['workflow'])}/dispatches"
    )
    inputs: dict[str, str] = {
        "job_id": job_id,
        "revision_id": revision_id,
        "snapshot_hash": snapshot_hash,
    }
    if export_json:
        inputs["export_json"] = export_json
    code, payload = _api_request(
        "POST",
        path,
        token=cfg["token"],
        body={
            "ref": cfg["ref"],
            "inputs": inputs,
        },
    )
    if code not in (204, 200):
        msg = payload.get("message") if isinstance(payload, dict) else str(payload)
        raise RuntimeError(f"GitHub workflow_dispatch failed ({code}): {msg}")

    run_id = _find_run_id(
        token=cfg["token"],
        repo=cfg["repo"],
        workflow=cfg["workflow"],
        job_id=job_id,
        attempts=8,
        delay_s=2.0,
    )
    return {
        "repository": cfg["repo"],
        "workflow": cfg["workflow"],
        "ref": cfg["ref"],
        "runId": run_id,
        "runName": f"{RUN_NAME_PREFIX}{job_id}",
    }


def _find_run_id(
    *,
    token: str,
    repo: str,
    workflow: str,
    job_id: str,
    attempts: int,
    delay_s: float,
) -> int | None:
    owner, _, name = repo.partition("/")
    want = f"{RUN_NAME_PREFIX}{job_id}"
    path = (
        f"/repos/{owner}/{name}/actions/workflows/"
        f"{urllib.parse.quote(workflow)}/runs?per_page=20"
    )
    for i in range(attempts):
        code, payload = _api_request("GET", path, token=token)
        if code == 200 and isinstance(payload, dict):
            for run in payload.get("workflow_runs") or []:
                if run.get("name") == want or run.get("display_title") == want:
                    rid = run.get("id")
                    if isinstance(rid, int):
                        return rid
        if i + 1 < attempts:
            time.sleep(delay_s)
    return None


def enqueue_github_actions_job(db: Session, job: JobRow) -> JobRow:
    from sonoplan_api.models import RevisionRow

    job.status = "queued"
    job.updated_at = _utcnow()
    job.result_manifest = pending_manifest(
        job_id=job.id,
        revision_id=job.revision_id,
        snapshot_hash=job.snapshot_hash,
        repo=github_config()["repo"],
        workflow=github_config()["workflow"],
    )
    db.commit()
    db.refresh(job)

    export_json = ""
    try:
        revision = db.get(RevisionRow, job.revision_id)
        if revision is None:
            raise RuntimeError(f"Revision {job.revision_id} not found")
        # Adapter lives under engine/adapter — add to path like job_execution.
        import sys
        from pathlib import Path

        adapter_root = Path(__file__).resolve().parents[4] / "engine" / "adapter"
        if adapter_root.is_dir() and str(adapter_root) not in sys.path:
            sys.path.insert(0, str(adapter_root))
        from sonoplan_adapter.export_revision import compact_export_payload

        payload = compact_export_payload(revision.snapshot)
        export_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        man = dict(job.result_manifest or {})
        notes = list(man.get("notes") or [])
        notes.insert(
            0,
            "Phase 2A export: room AABB box + revision sources/workplaces → Actions SPPS.",
        )
        if not payload.get("box", {}).get("exactRectangle", True):
            notes.insert(
                1,
                "Contour is not an axis-aligned rectangle — AABB used (not full polygon).",
            )
        man["notes"] = notes
        man["exportSummary"] = {
            "box": payload.get("box"),
            "sourceCount": len(payload.get("sources") or []),
            "workplaceCount": len(payload.get("workplaces") or []),
        }
        job.result_manifest = man
        db.commit()
        db.refresh(job)

        meta = dispatch_product_job(
            job_id=job.id,
            revision_id=job.revision_id,
            snapshot_hash=job.snapshot_hash,
            export_json=export_json,
        )
    except Exception as exc:  # noqa: BLE001 — surface config/API errors on job
        job.status = "failed"
        job.error_code = "GITHUB_ACTIONS_DISPATCH_FAILED"
        job.error_message = str(exc)
        job.finished_at = _utcnow()
        job.updated_at = job.finished_at
        job.result_manifest = {
            **(job.result_manifest or {}),
            "executionMode": "github_actions_failed",
            "mapAvailable": False,
            "notes": [str(exc)],
        }
        db.commit()
        db.refresh(job)
        return job

    man = dict(job.result_manifest or {})
    gh = dict(man.get("github") or {})
    gh.update(meta)
    man["github"] = gh
    job.result_manifest = man
    if meta.get("runId"):
        job.status = "running"
        job.started_at = _utcnow()
    job.updated_at = _utcnow()
    db.commit()
    db.refresh(job)
    return job


def sync_github_actions_job(db: Session, job: JobRow) -> JobRow:
    """Poll GitHub run / artifact and apply terminal state when available."""
    if job.status in ("completed", "failed", "cancelled"):
        return job
    if jobs_backend() != "github_actions":
        return job
    if job.cancel_requested and job.status in ("created", "queued"):
        job.status = "cancelled"
        job.error_code = "CANCELLED"
        job.error_message = "Job cancelled before GitHub Actions finished"
        job.finished_at = _utcnow()
        job.updated_at = job.finished_at
        db.commit()
        db.refresh(job)
        return job

    cfg = github_config()
    if not cfg["token"]:
        return job

    man = dict(job.result_manifest or {})
    gh = dict(man.get("github") or {})
    run_id = gh.get("runId")
    if not isinstance(run_id, int):
        run_id = _find_run_id(
            token=cfg["token"],
            repo=cfg["repo"],
            workflow=cfg["workflow"],
            job_id=job.id,
            attempts=1,
            delay_s=0,
        )
        if run_id is not None:
            gh["runId"] = run_id
            man["github"] = gh
            job.result_manifest = man
            if job.status == "queued":
                job.status = "running"
                job.started_at = job.started_at or _utcnow()
            job.updated_at = _utcnow()
            db.commit()
            db.refresh(job)

    if not isinstance(run_id, int):
        return job

    owner, _, name = cfg["repo"].partition("/")
    code, run = _api_request(
        "GET",
        f"/repos/{owner}/{name}/actions/runs/{run_id}",
        token=cfg["token"],
    )
    if code != 200 or not isinstance(run, dict):
        return job

    status = run.get("status")
    conclusion = run.get("conclusion")
    html_url = run.get("html_url")
    gh["htmlUrl"] = html_url
    gh["runStatus"] = status
    gh["conclusion"] = conclusion
    man["github"] = gh
    job.result_manifest = man

    if status != "completed":
        if job.status == "queued":
            job.status = "running"
            job.started_at = job.started_at or _utcnow()
        job.updated_at = _utcnow()
        db.commit()
        db.refresh(job)
        return job

    # Terminal on GitHub — pull artifact (may lag a few seconds after success).
    artifact = _download_job_artifact(
        token=cfg["token"],
        repo=cfg["repo"],
        run_id=run_id,
        job_id=job.id,
    )
    if artifact is None:
        # Keep running so the next GET retries; do not fail on first miss.
        gh["artifactPending"] = True
        man["github"] = gh
        job.result_manifest = man
        if job.status == "queued":
            job.status = "running"
            job.started_at = job.started_at or _utcnow()
        job.updated_at = _utcnow()
        db.commit()
        db.refresh(job)
        return job
    gh.pop("artifactPending", None)

    status_doc = artifact.get("job_status") or {}
    result_man = artifact.get("result_manifest")
    final_status = status_doc.get("status")
    if final_status not in ("completed", "failed"):
        # Infer from GH conclusion + punctual.
        if conclusion == "success" and isinstance(result_man, dict):
            punctual = result_man.get("punctualReceivers") or []
            if any(p.get("lpDbGlobal") is not None for p in punctual):
                final_status = "completed"
            else:
                final_status = "failed"
                status_doc = {
                    "errorCode": "SPPS_ZERO_ENERGY",
                    "errorMessage": "No confirmed Lp in Actions result manifest",
                }
        else:
            final_status = "failed"
            status_doc = {
                "errorCode": "GITHUB_ACTIONS_FAILED",
                "errorMessage": f"Workflow conclusion={conclusion}",
            }

    if isinstance(result_man, dict):
        result_man = dict(result_man)
        result_man["github"] = gh
        if result_man.get("executionMode") in (None, "github_actions_pending"):
            result_man["executionMode"] = "github_actions_spps"
        job.result_manifest = result_man
    else:
        man["executionMode"] = "github_actions_failed"
        job.result_manifest = man

    job.status = final_status
    job.error_code = status_doc.get("errorCode")
    job.error_message = status_doc.get("errorMessage")
    job.finished_at = _utcnow()
    job.updated_at = job.finished_at
    if job.started_at is None:
        job.started_at = job.finished_at
    db.commit()
    db.refresh(job)
    return job


def _download_job_artifact(
    *,
    token: str,
    repo: str,
    run_id: int,
    job_id: str,
) -> dict[str, Any] | None:
    owner, _, name = repo.partition("/")
    code, payload = _api_request(
        "GET",
        f"/repos/{owner}/{name}/actions/runs/{run_id}/artifacts",
        token=token,
    )
    if code != 200 or not isinstance(payload, dict):
        return None
    want = f"sonoplan-job-{job_id}"
    art_id = None
    for art in payload.get("artifacts") or []:
        if art.get("name") == want and not art.get("expired"):
            art_id = art.get("id")
            break
    if not isinstance(art_id, int):
        return None

    # Artifact ZIP: GitHub 302 → blob storage. Do NOT send Authorization on
    # the second hop (Azure rejects the GitHub Bearer and urllib would fail).
    zip_url = (
        f"https://api.github.com/repos/{owner}/{name}/actions/artifacts/"
        f"{art_id}/zip"
    )
    zip_bytes = _download_github_artifact_zip(zip_url, token=token)
    if zip_bytes is None:
        return None

    result: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                base = info.filename.replace("\\", "/").split("/")[-1]
                if base == "result_manifest.json":
                    result["result_manifest"] = json.loads(
                        zf.read(info).decode("utf-8")
                    )
                elif base == "job_status.json":
                    result["job_status"] = json.loads(
                        zf.read(info).decode("utf-8")
                    )
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not result:
        return None
    return result


def _download_github_artifact_zip(api_zip_url: str, *, token: str) -> bytes | None:
    """GET artifact zip; strip Authorization when following off-github redirects."""

    class _StripAuthRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
            new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
            if new_req is None:
                return None
            host = urllib.parse.urlparse(newurl).netloc.lower()
            if "api.github.com" not in host:
                for h in ("Authorization", "authorization"):
                    if h in new_req.headers:
                        del new_req.headers[h]
            return new_req

    opener = urllib.request.build_opener(_StripAuthRedirect)
    req = urllib.request.Request(
        api_zip_url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "SonoPlan-API-github-actions-worker",
        },
        method="GET",
    )
    try:
        with opener.open(req, timeout=120) as resp:
            return resp.read()
    except urllib.error.HTTPError:
        return None
    except urllib.error.URLError:
        return None
