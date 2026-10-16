"""Local helper: run one job id without Celery (dev / CI)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute SonoPlan job inline")
    parser.add_argument("job_id")
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[4]
    api_src = repo / "services" / "api" / "src"
    adapter = repo / "engine" / "adapter"
    for path in (api_src, adapter):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    from sqlalchemy.orm import sessionmaker

    from sonoplan_api.db import make_engine
    from sonoplan_api.job_execution import execute_job
    import sonoplan_api.models  # noqa: F401

    engine = make_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        job = execute_job(db, args.job_id)
        if job is None:
            print(json.dumps({"ok": False, "errorCode": "JOB_NOT_FOUND"}))
            return 1
        print(
            json.dumps(
                {
                    "ok": job.status == "completed",
                    "jobId": job.id,
                    "status": job.status,
                    "errorCode": job.error_code,
                    "errorMessage": job.error_message,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if job.status == "completed" else 1
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
