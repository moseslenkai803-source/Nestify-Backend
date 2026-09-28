import uuid

import pytest

from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.user import User
from app.services.contractor_service import ContractorService


def create_user(
    db_session,
    role="contractor",
    is_active=True,
):
    user = User(
        email=f"contractor-service-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_contractor(
    db_session,
    status="active",
):
    contractor = Contractor(
        name=f"Contractor {uuid.uuid4().hex[:8]}",
        contractor_type="company",
        status=status,
        contact_email="contractor@example.com",
        contact_phone="+254700000001",
    )
    db_session.add(contractor)
    db_session.flush()
    return contractor


def test_create_contractor_creates_active_contractor(db_session):
    service = ContractorService(db_session)

    result = service.create_contractor(
        name="Acme Installations",
        contractor_type="company",
        contact_email="acme@example.com",
        contact_phone="+254700000002",
    )

    assert result.id is not None
    assert result.name == "Acme Installations"
    assert result.contractor_type == "company"
    assert result.status == "active"
    assert result.contact_email == "acme@example.com"
    assert result.contact_phone == "+254700000002"


def test_create_contractor_rejects_blank_name(db_session):
    service = ContractorService(db_session)

    with pytest.raises(
        ValueError,
        match="Contractor name is required",
    ):
        service.create_contractor(name="   ")


def test_create_contractor_rejects_blank_type(db_session):
    service = ContractorService(db_session)

    with pytest.raises(
        ValueError,
        match="Contractor type is required",
    ):
        service.create_contractor(
            name="Acme Installations",
            contractor_type="   ",
        )


def test_add_member_creates_active_membership(db_session):
    contractor = create_contractor(db_session)
    user = create_user(db_session)

    service = ContractorService(db_session)

    result = service.add_member(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    assert result.id is not None
    assert result.contractor_id == contractor.id
    assert result.user_id == user.id
    assert result.is_active is True


def test_add_member_rejects_missing_contractor(db_session):
    user = create_user(db_session)

    service = ContractorService(db_session)

    with pytest.raises(
        ValueError,
        match="Contractor not found",
    ):
        service.add_member(
            contractor_id=uuid.uuid4(),
            user_id=user.id,
        )


def test_add_member_rejects_inactive_contractor(db_session):
    contractor = create_contractor(
        db_session,
        status="inactive",
    )
    user = create_user(db_session)

    service = ContractorService(db_session)

    with pytest.raises(
        ValueError,
        match="Contractor is inactive",
    ):
        service.add_member(
            contractor_id=contractor.id,
            user_id=user.id,
        )


def test_add_member_rejects_missing_user(db_session):
    contractor = create_contractor(db_session)

    service = ContractorService(db_session)

    with pytest.raises(
        ValueError,
        match="User not found",
    ):
        service.add_member(
            contractor_id=contractor.id,
            user_id=uuid.uuid4(),
        )


def test_add_member_rejects_inactive_user(db_session):
    contractor = create_contractor(db_session)
    user = create_user(
        db_session,
        is_active=False,
    )

    service = ContractorService(db_session)

    with pytest.raises(
        ValueError,
        match="User is inactive",
    ):
        service.add_member(
            contractor_id=contractor.id,
            user_id=user.id,
        )


def test_add_member_rejects_non_contractor_user(db_session):
    contractor = create_contractor(db_session)
    landlord = create_user(
        db_session,
        role="landlord",
    )

    service = ContractorService(db_session)

    with pytest.raises(
        ValueError,
        match="Only contractor users can be contractor members",
    ):
        service.add_member(
            contractor_id=contractor.id,
            user_id=landlord.id,
        )


def test_add_member_rejects_duplicate_active_membership(db_session):
    contractor = create_contractor(db_session)
    user = create_user(db_session)

    service = ContractorService(db_session)

    service.add_member(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    with pytest.raises(
        ValueError,
        match="User is already an active member of this contractor",
    ):
        service.add_member(
            contractor_id=contractor.id,
            user_id=user.id,
        )


def test_add_member_reactivates_inactive_membership(db_session):
    contractor = create_contractor(db_session)
    user = create_user(db_session)

    service = ContractorService(db_session)

    member = service.add_member(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    service.deactivate_member(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    reactivated_member = service.add_member(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    assert reactivated_member.id == member.id
    assert reactivated_member.is_active is True


def test_get_contractor_returns_contractor(db_session):
    contractor = create_contractor(db_session)

    service = ContractorService(db_session)

    result = service.get_contractor(contractor.id)

    assert result.id == contractor.id


def test_get_contractor_rejects_missing_contractor(db_session):
    service = ContractorService(db_session)

    with pytest.raises(
        ValueError,
        match="Contractor not found",
    ):
        service.get_contractor(uuid.uuid4())


def test_list_members_returns_contractor_members(db_session):
    contractor = create_contractor(db_session)
    user_one = create_user(db_session)
    user_two = create_user(db_session)

    service = ContractorService(db_session)

    member_one = service.add_member(
        contractor_id=contractor.id,
        user_id=user_one.id,
    )
    member_two = service.add_member(
        contractor_id=contractor.id,
        user_id=user_two.id,
    )

    result = service.list_members(contractor.id)

    assert len(result) == 2
    assert {member.id for member in result} == {
        member_one.id,
        member_two.id,
    }


def test_list_members_rejects_missing_contractor(db_session):
    service = ContractorService(db_session)

    with pytest.raises(
        ValueError,
        match="Contractor not found",
    ):
        service.list_members(uuid.uuid4())


def test_deactivate_member_deactivates_membership(db_session):
    contractor = create_contractor(db_session)
    user = create_user(db_session)

    service = ContractorService(db_session)

    service.add_member(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    result = service.deactivate_member(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    assert result.is_active is False


def test_deactivate_member_rejects_missing_membership(db_session):
    contractor = create_contractor(db_session)
    user = create_user(db_session)

    service = ContractorService(db_session)

    with pytest.raises(
        ValueError,
        match="Active contractor membership not found",
    ):
        service.deactivate_member(
            contractor_id=contractor.id,
            user_id=user.id,
        )


def test_deactivate_member_rejects_already_inactive_membership(db_session):
    contractor = create_contractor(db_session)
    user = create_user(db_session)

    service = ContractorService(db_session)

    service.add_member(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    service.deactivate_member(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    with pytest.raises(
        ValueError,
        match="Active contractor membership not found",
    ):
        service.deactivate_member(
            contractor_id=contractor.id,
            user_id=user.id,
        )
