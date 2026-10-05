import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.address_plate import AddressPlate
from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.installation_assignment import InstallationAssignment
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User


def test_create_installation_assignment_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"assignment-api-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Assignment API Owner",
            phone="+254700000010",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Assignment API Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"assignment-api-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Assignment API Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        due_at = datetime(
            2026,
            10,
            5,
            12,
            0,
            tzinfo=UTC,
        )

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(plate.id),
                "contractor_id": str(contractor.id),
                "contractor_member_id": str(contractor_member.id),
                "due_at": due_at.isoformat(),
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["id"] is not None
        assert data["property_id"] == str(property.id)
        assert data["plate_id"] == str(plate.id)
        assert data["contractor_id"] == str(contractor.id)
        assert data["contractor_member_id"] == str(contractor_member.id)
        assert data["assigned_by"] == str(employee.id)
        assert data["due_at"] == due_at.isoformat().replace("+00:00", "Z")
        assert data["status"] == "assigned"

        assignment = db_session.get(
            InstallationAssignment,
            uuid.UUID(data["id"]),
        )

        assert assignment is not None
        assert assignment.property_id == property.id
        assert assignment.plate_id == plate.id
        assert assignment.contractor_id == contractor.id
        assert assignment.contractor_member_id == contractor_member.id
        assert assignment.assigned_by == employee.id
        assert assignment.status == "assigned"

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_requires_plate_operations_clearance(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-restricted-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="contractor_management",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(uuid.uuid4()),
                "plate_id": str(uuid.uuid4()),
                "contractor_id": str(uuid.uuid4()),
                "contractor_member_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Insufficient employee clearance"
        )

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_rejects_non_employee(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        contractor_user = User(
            email=f"assignment-api-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        access_token = create_access_token(
            subject=str(contractor_user.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(uuid.uuid4()),
                "plate_id": str(uuid.uuid4()),
                "contractor_id": str(uuid.uuid4()),
                "contractor_member_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Employee access required"
        )

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_returns_404_for_missing_property(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-missing-property-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(uuid.uuid4()),
                "plate_id": str(uuid.uuid4()),
                "contractor_id": str(uuid.uuid4()),
                "contractor_member_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_returns_404_for_missing_plate(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-missing-plate-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-missing-plate-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Missing Plate Owner",
            phone="+254700000011",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Missing Plate Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        contractor = Contractor(
            name="Missing Plate Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-missing-plate-member-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(uuid.uuid4()),
                "contractor_id": str(contractor.id),
                "contractor_member_id": str(contractor_member.id),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Address plate not found"

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_rejects_plate_from_different_property(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"assignment-api-mismatch-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Mismatch Owner",
            phone="+254700000012",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        other_property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Other Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(other_property)
        db_session.flush()

        employee = User(
            email=f"assignment-api-mismatch-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Mismatch Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-mismatch-member-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=other_property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(plate.id),
                "contractor_id": str(contractor.id),
                "contractor_member_id": str(contractor_member.id),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Address plate is not linked to this property"
        )

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_returns_404_for_missing_contractor(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-missing-contractor-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-missing-contractor-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Missing Contractor Owner",
            phone="+254700000013",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Missing Contractor Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        contractor_member_id = uuid.uuid4()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(plate.id),
                "contractor_id": str(uuid.uuid4()),
                "contractor_member_id": str(contractor_member_id),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Contractor not found"

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_returns_404_for_missing_contractor_member(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-missing-member-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-missing-member-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Missing Member Owner",
            phone="+254700000014",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Missing Member Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        contractor = Contractor(
            name="Missing Member Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(plate.id),
                "contractor_id": str(contractor.id),
                "contractor_member_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Contractor member not found"

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_rejects_member_from_different_contractor(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-member-mismatch-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-member-mismatch-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Member Mismatch Owner",
            phone="+254700000015",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Member Mismatch Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        contractor = Contractor(
            name="Target Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        other_contractor = Contractor(
            name="Other Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(other_contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-member-mismatch-member-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=other_contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(plate.id),
                "contractor_id": str(contractor.id),
                "contractor_member_id": str(contractor_member.id),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Contractor member does not belong to this contractor"
        )

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_rejects_inactive_contractor(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-inactive-contractor-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-inactive-contractor-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Inactive Contractor Owner",
            phone="+254700000016",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Inactive Contractor Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        contractor = Contractor(
            name="Inactive Contractor",
            contractor_type="company",
            status="inactive",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-inactive-contractor-member-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(plate.id),
                "contractor_id": str(contractor.id),
                "contractor_member_id": str(contractor_member.id),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Contractor is inactive"

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_rejects_inactive_contractor_member(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-inactive-member-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-inactive-member-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Inactive Member Owner",
            phone="+254700000017",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Inactive Member Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        contractor = Contractor(
            name="Inactive Member Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-inactive-member-user-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=False,
        )
        db_session.add(contractor_member)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(plate.id),
                "contractor_id": str(contractor.id),
                "contractor_member_id": str(contractor_member.id),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Contractor member is inactive"

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_rejects_inactive_contractor_member_user(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-inactive-member-user-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-inactive-member-user-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Inactive Member User Owner",
            phone="+254700000018",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Inactive Member User Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        contractor = Contractor(
            name="Inactive Member User Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-inactive-member-user-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=False,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(plate.id),
                "contractor_id": str(contractor.id),
                "contractor_member_id": str(contractor_member.id),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Contractor member user is inactive"
        )

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_rejects_inactive_assigning_employee(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-inactive-assigner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=False,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-inactive-assigner-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Inactive Assigner Owner",
            phone="+254700000019",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Inactive Assigner Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        contractor = Contractor(
            name="Inactive Assigner Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-inactive-assigner-member-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(plate.id),
                "contractor_id": str(contractor.id),
                "contractor_member_id": str(contractor_member.id),
            },
        )

        assert response.status_code == 401

    finally:
        app.dependency_overrides.clear()


def test_create_installation_assignment_api_rejects_duplicate_active_property_assignment(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-duplicate-property-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-duplicate-property-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Duplicate Property Owner",
            phone="+254700000020",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Duplicate Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        contractor = Contractor(
            name="Duplicate Property Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-duplicate-property-member-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        first_assignment = InstallationAssignment(
            property_id=property.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="assigned",
        )
        db_session.add(first_assignment)
        db_session.flush()

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            "/api/v1/installation-assignments",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
                "plate_id": str(plate.id),
                "contractor_id": str(contractor.id),
                "contractor_member_id": str(contractor_member.id),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Property already has an active installation assignment"
        )

    finally:
        app.dependency_overrides.clear()



def test_start_installation_assignment_api(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"assignment-api-start-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Start Assignment Owner",
            phone="+254700000020",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Start Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"assignment-api-start-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Start Assignment Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-start-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="assigned",
        )
        db_session.add(assignment)
        db_session.flush()

        access_token = create_access_token(
            subject=str(contractor_user.id),
        )

        response = client.post(
            f"/api/v1/installation-assignments/{assignment.id}/start",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(assignment.id)
        assert data["property_id"] == str(property.id)
        assert data["plate_id"] == str(plate.id)
        assert data["contractor_id"] == str(contractor.id)
        assert data["contractor_member_id"] == str(contractor_member.id)
        assert data["status"] == "in_progress"

        db_session.refresh(assignment)
        assert assignment.status == "in_progress"

    finally:
        app.dependency_overrides.clear()


def test_start_installation_assignment_api_rejects_wrong_contractor_user(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"assignment-api-start-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Start Assignment Owner",
            phone="+254700000020",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Start Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"assignment-api-start-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Start Assignment Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-wrong-assigned-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        wrong_user = User(
            email=f"assignment-api-wrong-user-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add_all([contractor_user, wrong_user])
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="assigned",
        )
        db_session.add(assignment)
        db_session.flush()

        access_token = create_access_token(
            subject=str(wrong_user.id),
        )

        response = client.post(
            f"/api/v1/installation-assignments/{assignment.id}/start",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Contractor user is not assigned to this installation"

        db_session.refresh(assignment)
        assert assignment.status == "assigned"

    finally:
        app.dependency_overrides.clear()


def test_start_installation_assignment_api_rejects_user_whose_role_is_no_longer_contractor(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"assignment-api-role-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Role Change Owner",
            phone="+254700000021",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Role Change Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"assignment-api-role-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Role Change Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-role-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="assigned",
        )
        db_session.add(assignment)
        db_session.flush()

        contractor_user.role = "landlord"
        db_session.flush()

        access_token = create_access_token(
            subject=str(contractor_user.id),
        )

        response = client.post(
            f"/api/v1/installation-assignments/{assignment.id}/start",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Contractor member user must be a contractor"

        db_session.refresh(assignment)
        assert assignment.status == "assigned"

    finally:
        app.dependency_overrides.clear()


def test_submit_installation_assignment_api_rejects_user_whose_role_is_no_longer_contractor(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"assignment-api-submit-role-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Submit Role Change Owner",
            phone="+254700000031",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Submit Role Change Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"assignment-api-submit-role-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Submit Role Change Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-submit-role-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="in_progress",
        )
        db_session.add(assignment)
        db_session.flush()

        contractor_user.role = "landlord"
        db_session.flush()

        access_token = create_access_token(
            subject=str(contractor_user.id),
        )

        captured_at = datetime(2026, 9, 28, 18, 0, tzinfo=UTC)

        response = client.post(
            f"/api/v1/installation-assignments/{assignment.id}/submit",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "latitude": -1.2921,
                "longitude": 36.8219,
                "accuracy_meters": 4.5,
                "captured_at": captured_at.isoformat(),
                "notes": "Plate installed and GPS evidence captured.",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Contractor member user must be a contractor"

        db_session.refresh(assignment)
        assert assignment.status == "in_progress"

    finally:
        app.dependency_overrides.clear()


def test_submit_installation_assignment_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"assignment-api-submit-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Submit Assignment Owner",
            phone="+254700000030",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Submit Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"assignment-api-submit-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Submit Assignment Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-submit-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="in_progress",
        )
        db_session.add(assignment)
        db_session.flush()

        access_token = create_access_token(
            subject=str(contractor_user.id),
        )

        captured_at = datetime(2026, 9, 28, 18, 0, tzinfo=UTC)

        response = client.post(
            f"/api/v1/installation-assignments/{assignment.id}/submit",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "latitude": -1.2921,
                "longitude": 36.8219,
                "accuracy_meters": 4.5,
                "captured_at": captured_at.isoformat(),
                "notes": "Plate installed and GPS evidence captured.",
            },
        )

        assert response.status_code == 200

        data = response.json()
        assert data["id"] is not None
        assert data["property_id"] == str(property.id)
        assert data["plate_id"] == str(plate.id)
        assert data["assignment_id"] == str(assignment.id)
        assert data["installer_id"] == str(contractor_user.id)
        assert data["latitude"] == -1.2921
        assert data["longitude"] == 36.8219
        assert data["accuracy_meters"] == 4.5
        assert data["captured_at"] == captured_at.isoformat().replace("+00:00", "Z")
        assert data["status"] == "submitted"

        db_session.refresh(assignment)
        assert assignment.status == "submitted"

    finally:
        app.dependency_overrides.clear()

def test_submit_installation_assignment_api_rejects_wrong_contractor_user(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"assignment-api-submit-wrong-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Wrong Contractor Owner",
            phone="+254700000031",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Wrong Contractor Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"assignment-api-submit-wrong-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Assigned Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        assigned_user = User(
            email=f"assignment-api-submit-assigned-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        wrong_user = User(
            email=f"assignment-api-submit-wrong-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add_all([assigned_user, wrong_user])
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=assigned_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="in_progress",
        )
        db_session.add(assignment)
        db_session.flush()

        access_token = create_access_token(
            subject=str(wrong_user.id),
        )

        response = client.post(
            f"/api/v1/installation-assignments/{assignment.id}/submit",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "latitude": -1.2921,
                "longitude": 36.8219,
                "accuracy_meters": 4.5,
                "captured_at": datetime(2026, 9, 28, 18, 0, tzinfo=UTC).isoformat(),
                "notes": "Unauthorized submission attempt.",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Contractor user is not assigned to this installation"

        db_session.refresh(assignment)
        assert assignment.status == "in_progress"

    finally:
        app.dependency_overrides.clear()

def test_submit_installation_assignment_api_rejects_assignment_not_in_progress(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"assignment-api-submit-state-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Submit State Owner",
            phone="+254700000032",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Submit State Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"assignment-api-submit-state-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Submit State Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-submit-state-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="assigned",
        )
        db_session.add(assignment)
        db_session.flush()

        access_token = create_access_token(
            subject=str(contractor_user.id),
        )

        response = client.post(
            f"/api/v1/installation-assignments/{assignment.id}/submit",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "latitude": -1.2921,
                "longitude": 36.8219,
                "accuracy_meters": 4.5,
                "captured_at": datetime(2026, 9, 28, 18, 0, tzinfo=UTC).isoformat(),
                "notes": "Invalid state submission attempt.",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Installation assignment is not in progress"

        db_session.refresh(assignment)
        assert assignment.status == "assigned"

    finally:
        app.dependency_overrides.clear()


def test_cancel_installation_assignment_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner_user = User(
            email=f"assignment-api-cancel-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Cancel API Owner",
            phone="+254700000040",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Cancel API Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        employee = User(
            email=f"assignment-api-cancel-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Cancel API Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-cancel-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="assigned",
        )
        db_session.add(assignment)
        db_session.flush()

        access_token = create_access_token(subject=str(employee.id))

        response = client.post(
            f"/api/v1/installation-assignments/{assignment.id}/cancel",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"reason": "Contractor scheduling changed."},
        )

        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(assignment.id)
        assert data["status"] == "cancelled"
        assert data["cancelled_by"] == str(employee.id)
        assert data["cancelled_at"] is not None
        assert data["cancellation_reason"] == "Contractor scheduling changed."

        db_session.refresh(assignment)
        assert assignment.status == "cancelled"
        assert assignment.cancelled_by == employee.id
        assert assignment.cancelled_at is not None
        assert assignment.cancellation_reason == "Contractor scheduling changed."

    finally:
        app.dependency_overrides.clear()


def test_cancel_installation_assignment_api_requires_plate_operations_clearance(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-cancel-restricted-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="contractor_management",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        access_token = create_access_token(subject=str(employee.id))

        response = client.post(
            f"/api/v1/installation-assignments/{uuid.uuid4()}/cancel",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"reason": "Cancellation attempt."},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient employee clearance"

    finally:
        app.dependency_overrides.clear()


def test_cancel_installation_assignment_api_rejects_contractor(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        contractor_user = User(
            email=f"assignment-api-cancel-contractor-rejected-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        access_token = create_access_token(subject=str(contractor_user.id))

        response = client.post(
            f"/api/v1/installation-assignments/{uuid.uuid4()}/cancel",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"reason": "Contractor cancellation attempt."},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Employee access required"

    finally:
        app.dependency_overrides.clear()


def test_cancel_installation_assignment_api_rejects_completed_assignment(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-cancel-completed-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        contractor = Contractor(
            name="Completed Assignment Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-cancel-completed-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-cancel-completed-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Completed Assignment Owner",
            phone="+254700000041",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Completed Assignment Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            property_id=property.id,
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="completed",
        )
        db_session.add(assignment)
        db_session.flush()

        access_token = create_access_token(subject=str(employee.id))

        response = client.post(
            f"/api/v1/installation-assignments/{assignment.id}/cancel",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"reason": "Completed cancellation attempt."},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Installation assignment cannot be cancelled"

        db_session.refresh(assignment)
        assert assignment.status == "completed"

    finally:
        app.dependency_overrides.clear()

def test_list_installation_assignments_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-list-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-list-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Assignment List Owner",
            phone="+254700000050",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_record = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-LIST-{uuid.uuid4().hex[:12].upper()}",
            name="Assignment List Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property_record)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-LIST-{uuid.uuid4().hex[:12].upper()}",
            status="unactivated",
            property_id=property_record.id,
        )
        db_session.add(plate)
        db_session.flush()

        contractor = Contractor(
            name="Assignment List Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-list-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property_record.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="assigned",
        )
        db_session.add(assignment)
        db_session.flush()

        access_token = create_access_token(subject=str(employee.id))

        response = client.get(
            "/api/v1/installation-assignments",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200

        data = response.json()

        assert any(
            item["id"] == str(assignment.id)
            for item in data
        )

    finally:
        app.dependency_overrides.clear()


def test_list_installation_assignments_api_filters_by_status(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-filter-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        owner_user = User(
            email=f"assignment-api-filter-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        db_session.add(owner_user)
        db_session.flush()

        landlord = Landlord(
            user_id=owner_user.id,
            display_name="Assignment Filter Owner",
            phone="+254700000051",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property_record = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-FILTER-{uuid.uuid4().hex[:12].upper()}",
            name="Assignment Filter Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property_record)
        db_session.flush()

        plate = AddressPlate(
            plate_code=f"PLATE-FILTER-{uuid.uuid4().hex[:12].upper()}",
            status="unactivated",
            property_id=property_record.id,
        )
        db_session.add(plate)
        db_session.flush()

        contractor = Contractor(
            name="Assignment Filter Contractor",
            contractor_type="company",
            status="active",
        )
        db_session.add(contractor)
        db_session.flush()

        contractor_user = User(
            email=f"assignment-api-filter-contractor-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="contractor",
            is_active=True,
        )
        db_session.add(contractor_user)
        db_session.flush()

        contractor_member = ContractorMember(
            contractor_id=contractor.id,
            user_id=contractor_user.id,
            is_active=True,
        )
        db_session.add(contractor_member)
        db_session.flush()

        assignment = InstallationAssignment(
            property_id=property_record.id,
            plate_id=plate.id,
            contractor_id=contractor.id,
            contractor_member_id=contractor_member.id,
            assigned_by=employee.id,
            status="cancelled",
        )
        db_session.add(assignment)
        db_session.flush()

        access_token = create_access_token(subject=str(employee.id))

        response = client.get(
            "/api/v1/installation-assignments?status=cancelled",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200

        data = response.json()

        assert data
        assert all(item["status"] == "cancelled" for item in data)
        assert any(item["id"] == str(assignment.id) for item in data)

    finally:
        app.dependency_overrides.clear()


def test_list_installation_assignments_api_unknown_status_returns_empty(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-unknown-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="plate_operations",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        access_token = create_access_token(subject=str(employee.id))

        response = client.get(
            "/api/v1/installation-assignments?status=not-a-real-status",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        assert response.json() == []

    finally:
        app.dependency_overrides.clear()


def test_list_installation_assignments_api_requires_plate_operations_clearance(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        employee = User(
            email=f"assignment-api-list-no-clearance-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            clearance="property_verification",
            is_active=True,
        )
        db_session.add(employee)
        db_session.flush()

        access_token = create_access_token(subject=str(employee.id))

        response = client.get(
            "/api/v1/installation-assignments",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient employee clearance"

    finally:
        app.dependency_overrides.clear()
