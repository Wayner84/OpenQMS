"""File storage for document versions: server-generated storage names, extension +
magic-byte + size validation, and strictly organisation-scoped path resolution. Per
the Milestone 2 plan's "Storage and upload/download/preview security" section
(.hermes/plans/2026-07-26-milestone-2-document-management.md) -- every upload is
treated as hostile:

- The client's filename is *never* used to build a filesystem path; `storage_key` is
  built entirely from server-side identifiers (organisation id, document id, a
  random UUID), so path traversal is structurally impossible, not just filtered.
- File type is checked by extension allow-list *and*, where a reliable signature
  exists, the file's own first bytes -- not the client's declared `Content-Type`.
- Size is enforced while streaming, never after buffering the whole file in memory.
- `content_type` served back to clients is always derived from the validated
  extension, never trusted from the client.
"""

import hashlib
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol

CHUNK_SIZE = 1024 * 1024  # 1 MiB


class UnsupportedFileTypeError(Exception):
    """Raised when a file's extension isn't in the organisation's allow-list."""


class InvalidFileSignatureError(Exception):
    """Raised when a file's content doesn't match its extension's expected
    signature (best-effort magic-byte check; see MAGIC_BYTES below)."""


class FileTooLargeError(Exception):
    """Raised when a file exceeds the organisation's configured size limit."""


# Signature bytes for the extensions that have a reliable one. Office Open XML
# formats (.docx/.xlsx/.pptx) are all zip containers and share the same signature --
# distinguishing their *internal* structure would require unzipping, which is out of
# scope for this best-effort check (see the Milestone 2 plan's deferrals: no
# antivirus/deep content scanning). Plain text formats (.txt/.csv) have no reliable
# signature and are validated by extension + size only.
MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",),
    ".docx": (b"PK\x03\x04",),
    ".xlsx": (b"PK\x03\x04",),
    ".pptx": (b"PK\x03\x04",),
    ".png": (b"\x89PNG",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}

CONTENT_TYPE_BY_EXTENSION: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".txt": "text/plain",
    ".csv": "text/csv",
}

PREVIEWABLE_CONTENT_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg"})


def sanitise_filename(filename: str) -> str:
    """Best-effort display-only cleanup: strip any directory components (checked
    against both `/` and `\\`, regardless of host OS, since this is attacker-
    controlled input) and non-printable/quote characters. Never used to build a
    filesystem path -- only for `original_filename` display and the download
    `Content-Disposition` header."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable() and ch != '"')
    return name.strip() or "upload"


def extension_for_filename(filename: str) -> str:
    sanitised = sanitise_filename(filename)
    return Path(sanitised).suffix.lower()


def validate_extension(extension: str, allowed_extensions: frozenset[str]) -> None:
    if extension not in allowed_extensions:
        raise UnsupportedFileTypeError(f"File type {extension!r} is not allowed")


def validate_signature(extension: str, header: bytes) -> None:
    """No-op for extensions with no reliable signature (.txt/.csv)."""
    expected = MAGIC_BYTES.get(extension)
    if expected is None:
        return
    if not any(header.startswith(signature) for signature in expected):
        raise InvalidFileSignatureError(
            f"File content does not match the expected signature for {extension!r}"
        )


def build_storage_key(*, organisation_id: uuid.UUID, document_id: uuid.UUID, extension: str) -> str:
    """Entirely server-generated -- no client input ever becomes a path segment."""
    return f"{organisation_id}/{document_id}/{uuid.uuid4().hex}{extension}"


def resolve_path(uploads_dir: Path, storage_key: str) -> Path:
    """Resolve `storage_key` to an absolute path under `uploads_dir`, defensively
    verifying the result never escapes it -- defense in depth, even though
    `storage_key` is always server-generated and therefore can't contain `..`."""
    root = uploads_dir.resolve()
    resolved = (uploads_dir / storage_key).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"storage_key {storage_key!r} escapes the uploads directory")
    return resolved


class _AsyncReadable(Protocol):
    async def read(self, size: int) -> bytes: ...


async def save_validated_upload(
    upload: _AsyncReadable,
    *,
    destination: Path,
    max_size_bytes: int,
    extension: str,
) -> tuple[int, str]:
    """Read `upload` in bounded chunks, validate its signature from the first chunk
    before writing anything to disk, then stream the rest to `destination` while
    enforcing `max_size_bytes` and computing a SHA-256 checksum. Returns
    `(size_bytes, checksum_sha256)`. Deletes any partially-written file and re-raises
    if the size limit is exceeded.
    """
    first_chunk = await upload.read(CHUNK_SIZE)
    validate_signature(extension, first_chunk[:16])

    destination.parent.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    total = 0
    try:
        with destination.open("wb") as handle:
            handle_typed: BinaryIO = handle
            chunk = first_chunk
            while chunk:
                total += len(chunk)
                if total > max_size_bytes:
                    raise FileTooLargeError(
                        f"File exceeds the maximum allowed size of {max_size_bytes} bytes"
                    )
                hasher.update(chunk)
                handle_typed.write(chunk)
                chunk = await upload.read(CHUNK_SIZE)
    except FileTooLargeError:
        destination.unlink(missing_ok=True)
        raise

    return total, hasher.hexdigest()
