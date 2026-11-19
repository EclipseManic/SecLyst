from __future__ import annotations

from pathlib import Path


def safe_filename(value: str) -> str:
    name = Path(value or "artifact.bin").name.replace("\x00", "").strip()
    cleaned = "".join(character if character.isalnum() or character in "._- " else "_" for character in name)
    return (cleaned[:255] or "artifact.bin").strip(". ") or "artifact.bin"


def sniff_media_type(prefix: bytes, declared: str | None) -> str:
    if prefix.startswith(b"MZ"):
        return "application/vnd.microsoft.portable-executable"
    if prefix.startswith(b"PK\x03\x04"):
        return "application/zip"
    if prefix.startswith(b"ElfFile\x00"):
        return "application/x-evtx"
    if prefix.startswith(b"%PDF"):
        return "application/pdf"
    return (declared or "application/octet-stream").split(";", 1)[0].strip()[:255]
