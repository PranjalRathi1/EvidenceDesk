import threading
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.evaluation.runner import run_full_evaluation
from app.models import Collection, EvaluationRun
from app.schemas import EvaluationRunOut

router = APIRouter(prefix="/api", tags=["evaluation"])


def _run_in_background(run_id: str, collection_id: str):
    db = SessionLocal()
    try:
        run = db.get(EvaluationRun, run_id)
        report = run_full_evaluation(db, collection_id, settings.eval_reports_dir)
        run.status = "completed"
        run.report_path = report["_report_path"]
        from datetime import datetime, timezone

        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive
        run = db.get(EvaluationRun, run_id)
        run.status = "failed"
        run.error_message = f"{exc}\n{traceback.format_exc()[-2000:]}"
        db.commit()
    finally:
        db.close()


@router.post("/collections/{collection_id}/evaluate", response_model=EvaluationRunOut, status_code=202)
def start_evaluation(collection_id: str, db: Session = Depends(get_db)):
    if db.get(Collection, collection_id) is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    from app.evaluation.runner import load_dataset

    num_cases = len(load_dataset()["cases"])

    run = EvaluationRun(collection_id=collection_id, report_path="", num_cases=num_cases, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    thread = threading.Thread(target=_run_in_background, args=(run.id, collection_id), daemon=True)
    thread.start()
    return run


@router.get("/evaluations", response_model=list[EvaluationRunOut])
def list_evaluations(db: Session = Depends(get_db)):
    return db.query(EvaluationRun).order_by(EvaluationRun.created_at.desc()).all()


@router.get("/evaluations/{run_id}")
def get_evaluation(run_id: str, db: Session = Depends(get_db)):
    run = db.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    result = {
        "id": run.id,
        "collection_id": run.collection_id,
        "status": run.status,
        "num_cases": run.num_cases,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
        "error_message": run.error_message,
        "report": None,
    }
    if run.status == "completed" and run.report_path:
        import json
        from pathlib import Path

        path = Path(run.report_path)
        if path.exists():
            result["report"] = json.loads(path.read_text(encoding="utf-8"))
    return result
