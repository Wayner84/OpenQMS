"""Unit tests for the People module's Pydantic schemas.

Per docs/modules/People.md and the Milestone 1 plan: the `is_employee`/`company_id`
invariant is rejected with a validation error before it ever reaches the service
layer.
"""

import uuid

import pytest
from pydantic import ValidationError

from app.modules.people.schemas import PersonWriteRequest


def test_employee_with_a_company_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PersonWriteRequest(
            company_id=uuid.uuid4(),
            first_name="Jane",
            last_name="Doe",
            is_employee=True,
        )


def test_contact_without_a_company_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PersonWriteRequest(
            company_id=None,
            first_name="Jane",
            last_name="Doe",
            is_employee=False,
        )


def test_employee_without_a_company_id_is_accepted() -> None:
    request = PersonWriteRequest(
        company_id=None, first_name="Jane", last_name="Doe", is_employee=True
    )
    assert request.company_id is None


def test_contact_with_a_company_id_is_accepted() -> None:
    company_id = uuid.uuid4()
    request = PersonWriteRequest(
        company_id=company_id, first_name="Jane", last_name="Doe", is_employee=False
    )
    assert request.company_id == company_id
