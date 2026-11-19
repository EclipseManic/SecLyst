from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import or_, select

from ..database.models import Artifact, ArtifactEdge
from ..database.session import Database
from .validation import safe_filename, sniff_media_type


class ArtifactNotFound(LookupError):
    pass


class ArtifactLimitExceeded(ValueError):
    pass


class ArtifactConflict(RuntimeError):
    pass


class ArtifactStore:
    def __init__(self, database: Database, root: Path, *, max_bytes: int = 100 * 1024 * 1024) -> None:
        self.database = database
        self.root = root.resolve()
        self.objects = self.root / "sha256"
        self.temporary = self.root / "tmp"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.temporary.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes

    def ingest(self, stream: BinaryIO, *, original_name: str, declared_type: str | None = None) -> tuple[Artifact, bool]:
        digest = hashlib.sha256()
        size = 0
        prefix = b""
        handle = tempfile.NamedTemporaryFile(dir=self.temporary, delete=False)
        temp_path = Path(handle.name)
        try:
            with handle:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ArtifactLimitExceeded(f"Artifact exceeds {self.max_bytes} bytes.")
                    if len(prefix) < 16:
                        prefix += chunk[: 16 - len(prefix)]
                    digest.update(chunk)
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            sha256 = digest.hexdigest()
            with self.database.session() as session:
                existing = session.scalar(select(Artifact).where(Artifact.sha256 == sha256))
                if existing:
                    temp_path.unlink(missing_ok=True)
                    return existing, True

            destination = self.objects / sha256[:2] / sha256[2:4] / sha256
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                temp_path.unlink(missing_ok=True)
            else:
                temp_path.replace(destination)
            now = datetime.now(UTC)
            artifact = Artifact(
                id=str(uuid.uuid4()),
                sha256=sha256,
                size_bytes=size,
                media_type=sniff_media_type(prefix, declared_type),
                original_name=safe_filename(original_name),
                storage_path=destination.relative_to(self.root).as_posix(),
                quarantined=True,
                created_at=now,
                last_accessed_at=now,
                retention_class="standard",
            )
            with self.database.session() as session, session.begin():
                session.add(artifact)
            return artifact, False
        finally:
            temp_path.unlink(missing_ok=True)

    def get(self, artifact_id: str) -> Artifact:
        with self.database.session() as session, session.begin():
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                raise ArtifactNotFound(artifact_id)
            artifact.last_accessed_at = datetime.now(UTC)
            return artifact

    def path(self, artifact: Artifact) -> Path:
        path = (self.root / artifact.storage_path).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ArtifactNotFound(artifact.id)
        return path

    def relate(
        self,
        parent_id: str,
        child_id: str,
        relationship: str,
        *,
        producing_job_id: str | None = None,
        metadata: dict | None = None,
    ) -> ArtifactEdge:
        if parent_id == child_id:
            raise ArtifactConflict("An artifact cannot be related to itself.")
        with self.database.session() as session, session.begin():
            if session.get(Artifact, parent_id) is None or session.get(Artifact, child_id) is None:
                raise ArtifactNotFound("parent or child")
            edge = ArtifactEdge(
                parent_artifact_id=parent_id,
                child_artifact_id=child_id,
                relationship=relationship,
                producing_job_id=producing_job_id,
                metadata_json=json.dumps(metadata or {}, sort_keys=True, separators=(",", ":")),
                created_at=datetime.now(UTC),
            )
            session.add(edge)
            session.flush()
            return edge

    def relationships(self, artifact_id: str) -> list[ArtifactEdge]:
        with self.database.session() as session:
            if session.get(Artifact, artifact_id) is None:
                raise ArtifactNotFound(artifact_id)
            return list(session.scalars(select(ArtifactEdge).where(or_(
                ArtifactEdge.parent_artifact_id == artifact_id,
                ArtifactEdge.child_artifact_id == artifact_id,
            ))))

    def delete(self, artifact_id: str) -> None:
        with self.database.session() as session, session.begin():
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                raise ArtifactNotFound(artifact_id)
            referenced = session.scalar(select(ArtifactEdge.id).where(or_(
                ArtifactEdge.parent_artifact_id == artifact_id,
                ArtifactEdge.child_artifact_id == artifact_id,
            )))
            if referenced is not None:
                raise ArtifactConflict("Referenced artifacts cannot be deleted.")
            path = self.path(artifact)
            session.delete(artifact)
        path.unlink(missing_ok=True)
