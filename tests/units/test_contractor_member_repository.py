import uuid

from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.user import User
from app.repositories.contractor_member_repository import (
    ContractorMemberRepository,
)


def create_user(db_session, role="landlord", is_active=True):
    user = User(
        email=f"contractor-member-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_contractor(db_session):
    contractor = Contractor(
        name=f"Contractor {uuid.uuid4().hex[:8]}",
        contractor_type="company",
        status="active",
    )
    db_session.add(contractor)
    db_session.flush()
    return contractor


def create_member(db_session, contractor, user, is_active=True):
    member = ContractorMember(
        contractor_id=contractor.id,
        user_id=user.id,
        is_active=is_active,
    )
    db_session.add(member)
    db_session.flush()
    return member


def test_add_contractor_member(db_session):
    contractor = create_contractor(db_session)
    user = create_user(db_session)

    repository = ContractorMemberRepository(db_session)

    member = ContractorMember(
        contractor_id=contractor.id,
        user_id=user.id,
        is_active=True,
    )

    result = repository.add(member)

    assert result.id is not None
    assert result.contractor_id == contractor.id
    assert result.user_id == user.id
    assert result.is_active is True


def test_get_by_contractor_and_user_for_update_returns_member(
    db_session,
):
    contractor = create_contractor(db_session)
    user = create_user(db_session)
    member = create_member(db_session, contractor, user)

    repository = ContractorMemberRepository(db_session)

    result = repository.get_by_contractor_and_user_for_update(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    assert result is not None
    assert result.id == member.id


def test_get_by_contractor_and_user_for_update_returns_none_when_missing(
    db_session,
):
    contractor = create_contractor(db_session)
    user = create_user(db_session)

    repository = ContractorMemberRepository(db_session)

    result = repository.get_by_contractor_and_user_for_update(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    assert result is None


def test_get_active_by_contractor_and_user_returns_active_member(
    db_session,
):
    contractor = create_contractor(db_session)
    user = create_user(db_session)
    member = create_member(db_session, contractor, user)

    repository = ContractorMemberRepository(db_session)

    result = repository.get_active_by_contractor_and_user(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    assert result is not None
    assert result.id == member.id


def test_get_active_by_contractor_and_user_ignores_inactive_member(
    db_session,
):
    contractor = create_contractor(db_session)
    user = create_user(db_session)
    create_member(
        db_session,
        contractor,
        user,
        is_active=False,
    )

    repository = ContractorMemberRepository(db_session)

    result = repository.get_active_by_contractor_and_user(
        contractor_id=contractor.id,
        user_id=user.id,
    )

    assert result is None


def test_get_by_contractor_id_returns_all_members(db_session):
    contractor = create_contractor(db_session)
    user_one = create_user(db_session)
    user_two = create_user(db_session)

    member_one = create_member(
        db_session,
        contractor,
        user_one,
    )
    member_two = create_member(
        db_session,
        contractor,
        user_two,
    )

    repository = ContractorMemberRepository(db_session)

    result = repository.get_by_contractor_id(contractor.id)

    assert len(result) == 2
    assert {member.id for member in result} == {
        member_one.id,
        member_two.id,
    }


def test_get_by_user_id_returns_user_memberships(db_session):
    contractor_one = create_contractor(db_session)
    contractor_two = create_contractor(db_session)
    user = create_user(db_session)

    member_one = create_member(
        db_session,
        contractor_one,
        user,
    )
    member_two = create_member(
        db_session,
        contractor_two,
        user,
    )

    repository = ContractorMemberRepository(db_session)

    result = repository.get_by_user_id(user.id)

    assert len(result) == 2
    assert {member.id for member in result} == {
        member_one.id,
        member_two.id,
    }


def test_deactivate_marks_member_inactive(db_session):
    contractor = create_contractor(db_session)
    user = create_user(db_session)
    member = create_member(db_session, contractor, user)

    repository = ContractorMemberRepository(db_session)

    result = repository.deactivate(member)

    assert result.id == member.id
    assert result.is_active is False
