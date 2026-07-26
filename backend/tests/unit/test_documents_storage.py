"""Unit tests for app/modules/documents/storage.py.

Per the Milestone 2 plan's "Storage and upload/download/preview security" section:
every upload is treated as hostile. These tests prove, in isolation, the three
concrete claims made there: server-generated storage names (no client input ever
becomes a path segment), extension + magic-byte validation (not the client's
declared Content-Type), and size enforcement while streaming (no full buffering,
no orphaned partial files on rejection).
"""

import uuid
from pathlib import Path

import pytest

from app.modules.documents.storage import (
    FileTooLargeError,
    InvalidFileSignatureError,
    UnsupportedFileTypeError,
    build_storage_key,
    extension_for_filename,
    resolve_path,
    sanitise_filename,
    save_validated_upload,
    validate_extension,
    validate_signature,
)


class _FakeUpload:
    """A minimal async-readable stand-in for FastAPI's UploadFile in unit tests."""

    def __init__(self, data: bytes, chunk_size: int = 1024 * 1024) -> None:
        self._data = data
        self._offset = 0
        self._chunk_size = chunk_size

    async def read(self, size: int) -> bytes:
        step = min(size, self._chunk_size)
        chunk = self._data[self._offset : self._offset + step]
        self._offset += len(chunk)
        return chunk


# --- sanitise_filename / extension_for_filename -------------------------------


def test_sanitise_filename_strips_forward_slash_directory_components() -> None:
    assert sanitise_filename("../../etc/passwd") == "passwd"


def test_sanitise_filename_strips_backslash_directory_components() -> None:
    assert sanitise_filename("..\\..\\Windows\\System32\\evil.dll") == "evil.dll"


def test_sanitise_filename_strips_quotes_and_control_characters() -> None:
    assert sanitise_filename('evil".txt\r\n') == "evil.txt"


def test_sanitise_filename_falls_back_when_empty() -> None:
    assert sanitise_filename("") == "upload"
    assert sanitise_filename("../") == "upload"


def test_extension_for_filename_is_lowercased_and_traversal_safe() -> None:
    assert extension_for_filename("Report.PDF") == ".pdf"
    assert extension_for_filename("../../etc/passwd.PDF") == ".pdf"


# --- validate_extension / validate_signature -----------------------------------


def test_validate_extension_rejects_disallowed_extension() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validate_extension(".exe", frozenset({".pdf", ".txt"}))


def test_validate_extension_accepts_allowed_extension() -> None:
    validate_extension(".pdf", frozenset({".pdf", ".txt"}))  # does not raise


def test_validate_signature_accepts_matching_pdf_header() -> None:
    validate_signature(".pdf", b"%PDF-1.7\n...")  # does not raise


def test_validate_signature_rejects_mismatched_header() -> None:
    with pytest.raises(InvalidFileSignatureError):
        validate_signature(".pdf", b"MZ\x90\x00")  # a Windows EXE header, not a PDF


def test_validate_signature_is_a_noop_for_extensions_without_a_reliable_signature() -> None:
    validate_signature(".txt", b"anything at all")  # does not raise
    validate_signature(".csv", b"a,b,c\n1,2,3")  # does not raise


# --- build_storage_key / resolve_path ------------------------------------------


def test_build_storage_key_never_embeds_client_input() -> None:
    organisation_id = uuid.uuid4()
    document_id = uuid.uuid4()
    key = build_storage_key(
        organisation_id=organisation_id, document_id=document_id, extension=".pdf"
    )

    assert key.startswith(f"{organisation_id}/{document_id}/")
    assert key.endswith(".pdf")
    # The only variable component is a server-generated UUID hex, not anything
    # resembling client-suppliable content.
    middle = key.removeprefix(f"{organisation_id}/{document_id}/").removesuffix(".pdf")
    assert len(middle) == 32
    assert all(ch in "0123456789abcdef" for ch in middle)


def test_resolve_path_accepts_a_key_within_the_uploads_directory(tmp_path: Path) -> None:
    key = f"{uuid.uuid4()}/{uuid.uuid4()}/{uuid.uuid4().hex}.pdf"
    resolved = resolve_path(tmp_path, key)
    assert tmp_path.resolve() in resolved.parents


def test_resolve_path_rejects_a_traversal_attempt(tmp_path: Path) -> None:
    """Defense in depth: even though storage_key is always server-generated and can
    never actually contain '..', resolve_path itself must still refuse to resolve
    outside uploads_dir if one were ever passed in."""
    with pytest.raises(ValueError, match="escapes the uploads directory"):
        resolve_path(tmp_path, "../../etc/passwd")


# --- save_validated_upload ------------------------------------------------------


async def test_save_validated_upload_writes_file_and_returns_size_and_checksum(
    tmp_path: Path,
) -> None:
    import hashlib

    data = b"%PDF-1.7\n" + b"filler" * 100
    destination = tmp_path / "org" / "doc" / "version.pdf"

    size, checksum = await save_validated_upload(
        _FakeUpload(data), destination=destination, max_size_bytes=10_000, extension=".pdf"
    )

    assert size == len(data)
    assert checksum == hashlib.sha256(data).hexdigest()
    assert destination.read_bytes() == data


async def test_save_validated_upload_rejects_wrong_signature_without_writing_anything(
    tmp_path: Path,
) -> None:
    data = b"MZ\x90\x00" + b"not a real pdf"
    destination = tmp_path / "org" / "doc" / "version.pdf"

    with pytest.raises(InvalidFileSignatureError):
        await save_validated_upload(
            _FakeUpload(data), destination=destination, max_size_bytes=10_000, extension=".pdf"
        )

    assert not destination.exists()
    assert not destination.parent.exists()


async def test_save_validated_upload_rejects_oversized_file_and_cleans_up_partial_write(
    tmp_path: Path,
) -> None:
    data = b"%PDF-1.7\n" + (b"x" * 5000)
    destination = tmp_path / "org" / "doc" / "version.pdf"

    with pytest.raises(FileTooLargeError):
        await save_validated_upload(
            _FakeUpload(data, chunk_size=64),
            destination=destination,
            max_size_bytes=1000,
            extension=".pdf",
        )

    assert not destination.exists()
