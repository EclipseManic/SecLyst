import io

import pytest

from seclyst.artifacts import ArtifactConflict, ArtifactLimitExceeded, ArtifactStore
from seclyst.database.session import Database


def test_artifacts_are_content_addressed_and_deduplicated(tmp_path) -> None:
    database = Database(tmp_path / "artifacts.db", create_schema=True)
    store = ArtifactStore(database, tmp_path / "objects")
    try:
        first, duplicate = store.ingest(io.BytesIO(b"same bytes"), original_name="../unsafe.exe")
        second, deduplicated = store.ingest(io.BytesIO(b"same bytes"), original_name="other.exe")
        assert duplicate is False and deduplicated is True
        assert first.id == second.id
        assert first.original_name == "unsafe.exe"
        assert store.path(first).read_bytes() == b"same bytes"
    finally:
        database.dispose()


def test_artifact_limit_removes_temporary_file(tmp_path) -> None:
    database = Database(tmp_path / "limits.db", create_schema=True)
    root = tmp_path / "objects"
    store = ArtifactStore(database, root, max_bytes=4)
    try:
        with pytest.raises(ArtifactLimitExceeded):
            store.ingest(io.BytesIO(b"too large"), original_name="large.bin")
        assert not list((root / "tmp").iterdir())
    finally:
        database.dispose()


def test_referenced_artifact_cannot_be_deleted(tmp_path) -> None:
    database = Database(tmp_path / "edges.db", create_schema=True)
    store = ArtifactStore(database, tmp_path / "objects")
    try:
        parent, _ = store.ingest(io.BytesIO(b"parent"), original_name="parent.eml")
        child, _ = store.ingest(io.BytesIO(b"child"), original_name="child.bin")
        store.relate(parent.id, child.id, "contains")
        with pytest.raises(ArtifactConflict):
            store.delete(parent.id)
        with pytest.raises(ArtifactConflict):
            store.delete(child.id)
    finally:
        database.dispose()
