import uuid

from app.models.contractor import Contractor
from app.repositories.contractor_repository import ContractorRepository


def create_contractor(db_session, status="active"):
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


def test_add_contractor(db_session):
    repository = ContractorRepository(db_session)

    contractor = Contractor(
        name="Test Contractor",
        contractor_type="company",
        status="active",
    )

    result = repository.add(contractor)

    assert result.id is not None
    assert result.name == "Test Contractor"
    assert result.contractor_type == "company"
    assert result.status == "active"


def test_get_by_id_returns_contractor(db_session):
    contractor = create_contractor(db_session)

    repository = ContractorRepository(db_session)

    result = repository.get_by_id(contractor.id)

    assert result is not None
    assert result.id == contractor.id


def test_get_by_id_returns_none_for_missing_contractor(db_session):
    repository = ContractorRepository(db_session)

    result = repository.get_by_id(uuid.uuid4())

    assert result is None


def test_get_by_id_for_update_returns_contractor(db_session):
    contractor = create_contractor(db_session)

    repository = ContractorRepository(db_session)

    result = repository.get_by_id_for_update(contractor.id)

    assert result is not None
    assert result.id == contractor.id


def test_get_by_id_for_update_returns_none_for_missing_contractor(
    db_session,
):
    repository = ContractorRepository(db_session)

    result = repository.get_by_id_for_update(uuid.uuid4())

    assert result is None


def test_get_all_returns_contractors_newest_first(db_session):
    first = create_contractor(db_session)
    second = create_contractor(db_session)

    repository = ContractorRepository(db_session)

    result = repository.get_all()

    result_ids = [contractor.id for contractor in result]

    assert result_ids[:2] == [second.id, first.id]


def test_get_active_returns_only_active_contractors_newest_first(
    db_session,
):
    first_active = create_contractor(
        db_session,
        status="active",
    )
    inactive = create_contractor(
        db_session,
        status="inactive",
    )
    second_active = create_contractor(
        db_session,
        status="active",
    )

    repository = ContractorRepository(db_session)

    result = repository.get_active()

    result_ids = [contractor.id for contractor in result]

    assert result_ids[:2] == [
        second_active.id,
        first_active.id,
    ]
    assert inactive.id not in result_ids
