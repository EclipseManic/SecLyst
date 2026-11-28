from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from ..artifacts import ArtifactConflict, ArtifactLimitExceeded, ArtifactNotFound, ArtifactStore


router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


def store(request: Request) -> ArtifactStore:
    return request.app.state.artifact_store


def view(artifact) -> dict:
    return {
        "id": artifact.id,
        "sha256": artifact.sha256,
        "size_bytes": artifact.size_bytes,
        "media_type": artifact.media_type,
        "original_name": artifact.original_name,
        "quarantined": artifact.quarantined,
        "created_at": artifact.created_at,
        "retention_class": artifact.retention_class,
    }


@router.post("", status_code=201)
def upload_artifact(request: Request, file: UploadFile = File(...)) -> dict:
    try:
        artifact, deduplicated = store(request).ingest(
            file.file,
            original_name=file.filename or "artifact.bin",
            declared_type=file.content_type,
        )
        return {**view(artifact), "deduplicated": deduplicated}
    except ArtifactLimitExceeded as exc:
        raise HTTPException(status_code=413, detail={"code": "artifact_limit_exceeded", "message": str(exc)}) from exc


@router.get("/{artifact_id}")
def get_artifact(artifact_id: str, request: Request) -> dict:
    try:
        return view(store(request).get(artifact_id))
    except ArtifactNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "artifact_not_found", "message": "Artifact not found."}) from exc


@router.get("/{artifact_id}/download")
def download_artifact(artifact_id: str, request: Request):
    try:
        artifact = store(request).get(artifact_id)
        return FileResponse(
            store(request).path(artifact),
            filename=artifact.original_name,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{artifact.original_name}"'},
        )
    except ArtifactNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "artifact_not_found", "message": "Artifact not found."}) from exc


@router.get("/{artifact_id}/relationships")
def artifact_relationships(artifact_id: str, request: Request) -> dict:
    try:
        edges = store(request).relationships(artifact_id)
        return {"relationships": [{
            "parent_artifact_id": edge.parent_artifact_id,
            "child_artifact_id": edge.child_artifact_id,
            "relationship": edge.relationship,
            "producing_job_id": edge.producing_job_id,
        } for edge in edges]}
    except ArtifactNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "artifact_not_found", "message": "Artifact not found."}) from exc


@router.delete("/{artifact_id}", status_code=204)
def delete_artifact(artifact_id: str, request: Request) -> None:
    try:
        store(request).delete(artifact_id)
    except ArtifactNotFound as exc:
        raise HTTPException(status_code=404, detail={"code": "artifact_not_found", "message": "Artifact not found."}) from exc
    except ArtifactConflict as exc:
        raise HTTPException(status_code=409, detail={"code": "artifact_referenced", "message": str(exc)}) from exc
