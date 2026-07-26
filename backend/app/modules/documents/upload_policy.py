"""Configuration-driven upload policy (allowed extensions, max size), per
docs/Database.md#configuration-table and the Milestone 2 plan's "Upload policy"
section (.hermes/plans/2026-07-26-milestone-2-document-management.md). Unlike
numbering, this is read-only -- no sequence to mutate -- so a missing row simply
falls back to the conservative built-in default rather than being seeded on read.
"""

import logging
import uuid
from typing import NamedTuple, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration
from app.modules.documents.storage import CONTENT_TYPE_BY_EXTENSION

logger = logging.getLogger(__name__)

UPLOAD_POLICY_KEY = "document_upload_policy"

DEFAULT_ALLOWED_EXTENSIONS = frozenset(
    {".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg", ".txt", ".csv"}
)
DEFAULT_MAX_SIZE_MB = 50


class UploadPolicy(NamedTuple):
    allowed_extensions: frozenset[str]
    max_size_bytes: int


async def get_upload_policy(session: AsyncSession, *, organisation_id: uuid.UUID) -> UploadPolicy:
    """Return the effective upload policy for `organisation_id`, falling back to a
    conservative built-in default if the `configuration` row is missing."""
    config_row = (
        await session.execute(
            select(Configuration).where(
                Configuration.organisation_id == organisation_id,
                Configuration.key == UPLOAD_POLICY_KEY,
            )
        )
    ).scalar_one_or_none()

    if config_row is None:
        return UploadPolicy(
            allowed_extensions=DEFAULT_ALLOWED_EXTENSIONS,
            max_size_bytes=DEFAULT_MAX_SIZE_MB * 1024 * 1024,
        )

    value = config_row.value
    extensions = cast(
        list[object], value.get("allowed_extensions", list(DEFAULT_ALLOWED_EXTENSIONS))
    )
    max_size_mb = cast(int, value.get("max_size_mb", DEFAULT_MAX_SIZE_MB))

    # Never trust a configured extension the backend doesn't actually know how to
    # serve a Content-Type for -- storage.save_validated_upload/create_document_version
    # look up CONTENT_TYPE_BY_EXTENSION unconditionally for any extension that
    # passes this allow-list, so an unknown one would otherwise be accepted here
    # only to crash with a KeyError deeper in the upload path. Silently dropped,
    # not a hard error, so an operator's overly-broad configuration row degrades
    # gracefully instead of taking every upload down.
    requested = frozenset(str(ext).lower() for ext in extensions)
    unknown = requested - CONTENT_TYPE_BY_EXTENSION.keys()
    if unknown:
        logger.warning(
            "document_upload_policy for organisation %s names unsupported extensions"
            " %s; ignoring them",
            organisation_id,
            sorted(unknown),
        )
    allowed_extensions = requested & CONTENT_TYPE_BY_EXTENSION.keys()

    return UploadPolicy(
        allowed_extensions=frozenset(allowed_extensions),
        max_size_bytes=int(max_size_mb) * 1024 * 1024,
    )
