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
