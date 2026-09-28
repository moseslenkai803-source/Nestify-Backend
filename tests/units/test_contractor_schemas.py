import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.contractor import (
    ContractorCreate,
    ContractorMemberCreate,
    ContractorMemberResponse,
    ContractorResponse,
)


def test_contractor_create_accepts_valid_data():
    result = ContractorCreate(
        name="Acme Installations",
        contractor_type="company",
        contact_email="operations@acme.example",
        contact_phone="+254700000001",
    )

    assert result.name == "Acme Installations"
    assert result.contractor_type == "company"
    assert result.contact_email == "operations@acme.example"
    assert result.contact_phone == "+254700000001"


def test_contractor_create_uses_company_as_default_type():
    result = ContractorCreate(
        name="Independent Installer",
    )

    assert result.contractor_type == "company"


def test_contractor_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        ContractorCreate(name="")


def test_contractor_create_rejects_oversized_name():
    with pytest.raises(ValidationError):
        ContractorCreate(name="A" * 256)


def test_contractor_create_rejects_blank_contractor_type():
    with pytest.raises(ValidationError):
        ContractorCreate(
            name="Test Contractor",
            contractor_type="",
        )


def test_contractor_create_rejects_oversized_contractor_type():
    with pytest.raises(ValidationError):
        ContractorCreate(
            name="Test Contractor",
            contractor_type="A" * 51,
        )


def test_contractor_create_allows_optional_contact_fields_to_be_none():
    result = ContractorCreate(
        name="Test Contractor",
        contact_email=None,
        contact_phone=None,
    )

    assert result.contact_email is None
    assert result.contact_phone is None


def test_contractor_member_create_accepts_uuid():
    user_id = uuid.uuid4()

    result = ContractorMemberCreate(
        user_id=user_id,
    )

    assert result.user_id == user_id


def test_contractor_member_create_rejects_invalid_uuid():
    with pytest.raises(ValidationError):
        ContractorMemberCreate(
            user_id="not-a-uuid",
        )


def test_contractor_response_serializes_from_attributes():
    contractor = type(
        "ContractorObject",
        (),
        {
            "id": uuid.uuid4(),
            "name": "Test Contractor",
            "contractor_type": "company",
            "status": "active",
            "contact_email": "test@example.com",
            "contact_phone": "+254700000001",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        },
    )()

    result = ContractorResponse.model_validate(contractor)

    assert result.id == contractor.id
    assert result.name == contractor.name
    assert result.status == contractor.status


def test_contractor_member_response_serializes_from_attributes():
    contractor_id = uuid.uuid4()
    user_id = uuid.uuid4()

    member = type(
        "ContractorMemberObject",
        (),
        {
            "id": uuid.uuid4(),
            "contractor_id": contractor_id,
            "user_id": user_id,
            "is_active": True,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        },
    )()

    result = ContractorMemberResponse.model_validate(member)

    assert result.id == member.id
    assert result.contractor_id == contractor_id
    assert result.user_id == user_id
    assert result.is_active is True
