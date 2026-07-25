"""Pydantic schemas for the People module, per docs/modules/People.md and docs/API.md."""

import uuid
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, model_validator

from app.modules.people.models import CompanyType


class CompanyWriteRequest(BaseModel):
    """Shared shape for POST and PATCH /api/v1/companies (create and full update)."""

    name: str
    type: CompanyType = CompanyType.OTHER
    address: str | None = None
    phone: str | None = None
    general_email: EmailStr | None = None
    notes: str | None = None


class CompanyRead(BaseModel):
    """A company's public shape."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    name: str
    type: CompanyType
    address: str | None
    phone: str | None
    general_email: str | None
    notes: str | None
    created_by_id: uuid.UUID | None
    updated_by_id: uuid.UUID | None


class CompanyListResponse(BaseModel):
    """GET /api/v1/companies response body, per docs/API.md#pagination."""

    items: list[CompanyRead]
    total: int
    limit: int
    offset: int


class PersonWriteRequest(BaseModel):
    """Shared shape for POST and PATCH /api/v1/people (create and full update).

    Enforces the People module's core invariant (docs/modules/People.md): a null
    `company_id` means an internal employee (`is_employee=true`); a populated one
    means a contact at that company (`is_employee=false`).
    """

    company_id: uuid.UUID | None = None
    first_name: str
    last_name: str
    email: EmailStr | None = None
    phone: str | None = None
    role: str | None = None
    department: str | None = None
    notes: str | None = None
    is_employee: bool = False

    @model_validator(mode="after")
    def _check_employee_company_invariant(self) -> Self:
        if self.is_employee and self.company_id is not None:
            raise ValueError("An employee (is_employee=true) cannot have a company_id")
        if not self.is_employee and self.company_id is None:
            raise ValueError("A contact (is_employee=false) must have a company_id")
        return self


class PersonRead(BaseModel):
    """A person's public shape."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    company_id: uuid.UUID | None
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    role: str | None
    department: str | None
    notes: str | None
    is_employee: bool
    created_by_id: uuid.UUID | None
    updated_by_id: uuid.UUID | None


class PersonListResponse(BaseModel):
    """GET /api/v1/people (and .../companies/{id}/people) response body."""

    items: list[PersonRead]
    total: int
    limit: int
    offset: int
