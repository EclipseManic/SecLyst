from __future__ import annotations
import json
import uuid
from datetime import UTC, datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from ..database.models import AnalysisRun, Artifact, DetectionCandidate
from ..jobs.service import JobCreate, JobInputValue

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])
PLAN = [
    {"id": "phishing", "tool": "phishing", "operation": "analyze"},
    {"id": "attachments", "tool": "malware", "operation": "scan", "depends_on": ["phishing"]},
    {"id": "indicators", "tool": "ioc", "operation": "lookup", "depends_on": ["phishing", "attachments"]},
    {"id": "sightings", "tool": "events", "operation": "search", "depends_on": ["indicators"]},
    {"id": "detection", "tool": "ruleforge", "operation": "evaluate", "depends_on": ["sightings"]},
]


class RunCreate(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    artifact_id: str
    recipe: str = "email-to-detection"


def as_dict(run):
    return {
        "id": run.id,
        "question": run.question,
        "artifact_id": run.artifact_id,
        "recipe": run.recipe,
        "recipe_version": run.recipe_version,
        "status": run.status,
        "plan": json.loads(run.plan_json),
        "initial_job_id": run.initial_job_id,
        "created_at": run.created_at,
    }


@router.post("", status_code=201)
def create_run(body: RunCreate, request: Request):
    db = request.app.state.job_service.database
    with db.session() as session:
        artifact = session.get(Artifact, body.artifact_id)
    if artifact is None:
        raise HTTPException(404, detail={"code": "artifact_not_found", "message": "Artifact not found."})
    if body.recipe != "email-to-detection":
        raise HTTPException(422, detail={"code": "unsupported_recipe", "message": "Recipe is not supported."})
    job = request.app.state.job_service.create(
        JobCreate(
            tool="phishing",
            operation="analyze",
            inputs=[JobInputValue(type="artifact", ref=body.artifact_id, sha256=artifact.sha256)],
            parameters={"recipe": body.recipe},
        )
    ).job
    run = AnalysisRun(
        id=str(uuid.uuid4()),
        question=body.question,
        artifact_id=body.artifact_id,
        recipe=body.recipe,
        recipe_version="1",
        status="queued",
        plan_json=json.dumps(PLAN),
        initial_job_id=job.id,
        created_at=datetime.now(UTC),
    )
    with db.session() as session, session.begin():
        session.add(run)
    return as_dict(run)


@router.get("")
def list_runs(request: Request):
    with request.app.state.job_service.database.session() as session:
        return [as_dict(run) for run in session.scalars(select(AnalysisRun).order_by(AnalysisRun.created_at.desc()))]


@router.get("/{run_id}")
def get_run(run_id: str, request: Request):
    with request.app.state.job_service.database.session() as session:
        run = session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(404, detail={"code": "run_not_found", "message": "Run not found."})
    return as_dict(run)


@router.post("/{run_id}/detections", status_code=201)
def create_detection(run_id: str, request: Request):
    db = request.app.state.job_service.database
    with db.session() as session:
        run = session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(404, detail={"code": "run_not_found", "message": "Run not found."})
    item = DetectionCandidate(
        id=str(uuid.uuid4()),
        run_id=run.id,
        title=f"Detection for {run.question[:120]}",
        status="draft",
        evidence_json=json.dumps({"artifact_id": run.artifact_id, "job_id": run.initial_job_id}),
        rule_source_json="{}",
        validation_json="{}",
        created_at=datetime.now(UTC),
    )
    with db.session() as session, session.begin():
        session.add(item)
    return {"id": item.id, "run_id": item.run_id, "status": item.status, "title": item.title}
