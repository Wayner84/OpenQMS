"""Unit tests for app/modules/documents/service.py's approval workflow functions
(SQLite for the DB side, a real tmp_path for the file side).

Per the Milestone 2 plan's "Workflow (state machine)" section: draft -> in_review ->
approved (or rejected, terminal for that version) -> obsolete (on supersession);
documents.status becomes and stays "approved" once any version has ever been
approved, even across a later version's separate in_review/rejected cycle.
"""

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation

SessionMaker = async_sessionmaker[AsyncSession]


class _FakeUpload:
    def __init__(self, filename: str, data: bytes) -> None:
        self.filename: str | None = filename
        self._data = data
        self._offset = 0

    async def read(self, size: int) -> bytes:
        chunk = self._data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
    import app.modules.documents.models  # noqa: F401
    import app.modules.people.models  # noqa: F401
    from app.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def organisation_id(session_maker: SessionMaker) -> uuid.UUID:
    async with session_maker() as session:
        org = Organisation(name="Default Organisation", slug="default")
        session.add(org)
        await session.commit()
        return org.id


@pytest.fixture
async def admin_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.models.user import User, UserRole

    async with session_maker() as session:
        user = User(
            organisation_id=organisation_id,
            email="admin@example.com",
            hashed_password="irrelevant",
            full_name="Admin",
            role=UserRole.ADMIN,
        )
        session.add(user)
        await session.commit()
        return user.id


async def _create_draft_version(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path, *, title: str = "SOP 1"
) -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (document_id, version_id) for a freshly created draft version."""
    from app.modules.documents.service import create_document, create_document_version

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title=title,
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
    async with session_maker() as session:
        version = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("report.pdf", b"%PDF-1.7\nhello"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    return document.id, version.id


# --- submit-for-approval -------------------------------------------------------


async def test_submit_for_approval_moves_draft_to_in_review(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.models import DocumentStatus, DocumentVersionStatus
    from app.modules.documents.service import get_document, submit_document_version_for_approval

    document_id, version_id = await _create_draft_version(session_maker, organisation_id, tmp_path)

    async with session_maker() as session:
        version = await submit_document_version_for_approval(
            session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
        )

    assert version.status == DocumentVersionStatus.IN_REVIEW

    async with session_maker() as session:
        document = await get_document(
            session, organisation_id=organisation_id, document_id=document_id
        )
    assert document.status == DocumentStatus.IN_REVIEW


async def test_submit_for_approval_rejects_a_non_draft_version(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import (
        InvalidVersionStateError,
        submit_document_version_for_approval,
    )

    document_id, version_id = await _create_draft_version(session_maker, organisation_id, tmp_path)

    async with session_maker() as session:
        await submit_document_version_for_approval(
            session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
        )

    async with session_maker() as session:
        with pytest.raises(InvalidVersionStateError):
            await submit_document_version_for_approval(
                session,
                organisation_id=organisation_id,
                document_id=document_id,
                version_id=version_id,
            )


# --- approve ---------------------------------------------------------------


async def test_approve_sets_current_version_and_document_status(
    session_maker: SessionMaker, organisation_id: uuid.UUID, admin_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.models import DocumentStatus, DocumentVersionStatus
    from app.modules.documents.service import (
        approve_document_version,
        get_document,
        submit_document_version_for_approval,
    )

    document_id, version_id = await _create_draft_version(session_maker, organisation_id, tmp_path)
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
        )

    async with session_maker() as session:
        version = await approve_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=version_id,
            approver_id=admin_id,
            comments="Looks good",
        )

    assert version.status == DocumentVersionStatus.APPROVED

    async with session_maker() as session:
        document = await get_document(
            session, organisation_id=organisation_id, document_id=document_id
        )
    assert document.status == DocumentStatus.APPROVED
    assert document.current_version_id == version_id


async def test_approve_rejects_a_version_that_is_not_in_review(
    session_maker: SessionMaker, organisation_id: uuid.UUID, admin_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import InvalidVersionStateError, approve_document_version

    document_id, version_id = await _create_draft_version(session_maker, organisation_id, tmp_path)

    async with session_maker() as session:
        with pytest.raises(InvalidVersionStateError):
            await approve_document_version(
                session,
                organisation_id=organisation_id,
                document_id=document_id,
                version_id=version_id,
                approver_id=admin_id,
                comments=None,
            )


async def test_approve_records_an_immutable_approval_row(
    session_maker: SessionMaker, organisation_id: uuid.UUID, admin_id: uuid.UUID, tmp_path: Path
) -> None:
    from sqlalchemy import select

    from app.modules.documents.models import ApprovalDecision, DocumentApproval
    from app.modules.documents.service import (
        approve_document_version,
        submit_document_version_for_approval,
    )

    document_id, version_id = await _create_draft_version(session_maker, organisation_id, tmp_path)
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
        )
    async with session_maker() as session:
        await approve_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=version_id,
            approver_id=admin_id,
            comments="Looks good",
        )

    async with session_maker() as session:
        approvals = (
            (
                await session.execute(
                    select(DocumentApproval).where(
                        DocumentApproval.document_version_id == version_id
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(approvals) == 1
    assert approvals[0].decision == ApprovalDecision.APPROVED
    assert approvals[0].approver_id == admin_id
    assert approvals[0].comments == "Looks good"


async def test_approving_a_new_version_supersedes_the_previous_current_version(
    session_maker: SessionMaker, organisation_id: uuid.UUID, admin_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.models import DocumentVersionStatus
    from app.modules.documents.service import (
        approve_document_version,
        create_document_version,
        get_document,
        get_document_version,
        submit_document_version_for_approval,
    )

    document_id, first_version_id = await _create_draft_version(
        session_maker, organisation_id, tmp_path
    )
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=first_version_id,
        )
    async with session_maker() as session:
        await approve_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=first_version_id,
            approver_id=admin_id,
            comments=None,
        )

    async with session_maker() as session:
        second_version = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            upload=_FakeUpload("report-v2.pdf", b"%PDF-1.7\nversion two"),
            change_summary="Revised",
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=second_version.id,
        )
    async with session_maker() as session:
        await approve_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=second_version.id,
            approver_id=admin_id,
            comments=None,
        )

    async with session_maker() as session:
        document = await get_document(
            session, organisation_id=organisation_id, document_id=document_id
        )
        first_version = await get_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=first_version_id,
        )

    assert document.current_version_id == second_version.id
    assert first_version.status == DocumentVersionStatus.OBSOLETE


# --- reject ------------------------------------------------------------------


async def test_reject_requires_a_comment(
    session_maker: SessionMaker, organisation_id: uuid.UUID, admin_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import (
        RejectionCommentRequiredError,
        reject_document_version,
        submit_document_version_for_approval,
    )

    document_id, version_id = await _create_draft_version(session_maker, organisation_id, tmp_path)
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
        )

    async with session_maker() as session:
        with pytest.raises(RejectionCommentRequiredError):
            await reject_document_version(
                session,
                organisation_id=organisation_id,
                document_id=document_id,
                version_id=version_id,
                approver_id=admin_id,
                comments="   ",
            )


async def test_reject_reverts_document_to_draft_when_never_approved(
    session_maker: SessionMaker, organisation_id: uuid.UUID, admin_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.models import DocumentStatus, DocumentVersionStatus
    from app.modules.documents.service import (
        get_document,
        reject_document_version,
        submit_document_version_for_approval,
    )

    document_id, version_id = await _create_draft_version(session_maker, organisation_id, tmp_path)
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
        )

    async with session_maker() as session:
        version = await reject_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=version_id,
            approver_id=admin_id,
            comments="Needs rework",
        )

    assert version.status == DocumentVersionStatus.REJECTED

    async with session_maker() as session:
        document = await get_document(
            session, organisation_id=organisation_id, document_id=document_id
        )
    assert document.status == DocumentStatus.DRAFT


async def test_reject_leaves_document_approved_when_a_current_version_already_exists(
    session_maker: SessionMaker, organisation_id: uuid.UUID, admin_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.models import DocumentStatus
    from app.modules.documents.service import (
        approve_document_version,
        create_document_version,
        get_document,
        reject_document_version,
        submit_document_version_for_approval,
    )

    document_id, first_version_id = await _create_draft_version(
        session_maker, organisation_id, tmp_path
    )
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=first_version_id,
        )
    async with session_maker() as session:
        await approve_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=first_version_id,
            approver_id=admin_id,
            comments=None,
        )

    async with session_maker() as session:
        second_version = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            upload=_FakeUpload("report-v2.pdf", b"%PDF-1.7\nversion two"),
            change_summary="Revised",
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=second_version.id,
        )
    async with session_maker() as session:
        await reject_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=second_version.id,
            approver_id=admin_id,
            comments="Not ready",
        )

    async with session_maker() as session:
        document = await get_document(
            session, organisation_id=organisation_id, document_id=document_id
        )
    assert document.status == DocumentStatus.APPROVED
    assert document.current_version_id == first_version_id


# --- retire ------------------------------------------------------------------


async def test_retire_document_sets_obsolete_regardless_of_version_state(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.models import DocumentStatus
    from app.modules.documents.service import retire_document

    document_id, _version_id = await _create_draft_version(session_maker, organisation_id, tmp_path)

    async with session_maker() as session:
        document = await retire_document(
            session, organisation_id=organisation_id, document_id=document_id
        )

    assert document.status == DocumentStatus.OBSOLETE


async def test_submitting_a_new_version_does_not_undo_a_retire(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    """Regression test: retire is admin-only, but before this fix any active user
    could silently revive a retired document by uploading and submitting a new
    draft, since submit-for-approval unconditionally set documents.status to
    in_review whenever current_version_id was still null."""
    from app.modules.documents.models import DocumentStatus
    from app.modules.documents.service import (
        create_document_version,
        get_document,
        retire_document,
        submit_document_version_for_approval,
    )

    document_id, first_version_id = await _create_draft_version(
        session_maker, organisation_id, tmp_path
    )
    async with session_maker() as session:
        await retire_document(session, organisation_id=organisation_id, document_id=document_id)

    async with session_maker() as session:
        new_version = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            upload=_FakeUpload("report-v2.pdf", b"%PDF-1.7\nversion two"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=new_version.id,
        )

    async with session_maker() as session:
        document = await get_document(
            session, organisation_id=organisation_id, document_id=document_id
        )
    assert document.status == DocumentStatus.OBSOLETE
    assert first_version_id  # keep the fixture's first version referenced


async def test_rejecting_a_version_does_not_undo_a_retire(
    session_maker: SessionMaker, organisation_id: uuid.UUID, admin_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.models import DocumentStatus
    from app.modules.documents.service import (
        create_document_version,
        get_document,
        reject_document_version,
        retire_document,
        submit_document_version_for_approval,
    )

    document_id, _first_version_id = await _create_draft_version(
        session_maker, organisation_id, tmp_path
    )
    async with session_maker() as session:
        await retire_document(session, organisation_id=organisation_id, document_id=document_id)

    async with session_maker() as session:
        new_version = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            upload=_FakeUpload("report-v2.pdf", b"%PDF-1.7\nversion two"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=new_version.id,
        )
    async with session_maker() as session:
        await reject_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=new_version.id,
            approver_id=admin_id,
            comments="Not ready",
        )

    async with session_maker() as session:
        document = await get_document(
            session, organisation_id=organisation_id, document_id=document_id
        )
    assert document.status == DocumentStatus.OBSOLETE


async def test_approving_a_version_can_deliberately_revive_a_retired_document(
    session_maker: SessionMaker, organisation_id: uuid.UUID, admin_id: uuid.UUID, tmp_path: Path
) -> None:
    """Unlike submit/reject, approve is itself an admin-only action, so an admin
    approving a new version of a retired document is a deliberate decision to bring
    it back into force -- intentionally different from the submit/reject cases
    above."""
    from app.modules.documents.models import DocumentStatus
    from app.modules.documents.service import (
        approve_document_version,
        create_document_version,
        get_document,
        retire_document,
        submit_document_version_for_approval,
    )

    document_id, _first_version_id = await _create_draft_version(
        session_maker, organisation_id, tmp_path
    )
    async with session_maker() as session:
        await retire_document(session, organisation_id=organisation_id, document_id=document_id)

    async with session_maker() as session:
        new_version = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            upload=_FakeUpload("report-v2.pdf", b"%PDF-1.7\nversion two"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        await submit_document_version_for_approval(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=new_version.id,
        )
    async with session_maker() as session:
        await approve_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=new_version.id,
            approver_id=admin_id,
            comments=None,
        )

    async with session_maker() as session:
        document = await get_document(
            session, organisation_id=organisation_id, document_id=document_id
        )
    assert document.status == DocumentStatus.APPROVED
