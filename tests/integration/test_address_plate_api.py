import uuid

from fastapi.testclient import TestClient
import pytest

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.user import User


def create_plate_operations_employee(db_session):
    employee = User(
        email=f"plate-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
        clearance="plate_operations",
        is_active=True,
    )

    db_session.add(employee)
    db_session.flush()

    return create_access_token(
        subject=str(employee.id),
    )


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as test_client:
        yield test_client


def test_create_address_plate_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        access_token = create_plate_operations_employee(
            db_session
        )

        response = client.post(
            "/api/v1/address-plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["id"] is not None
        assert data["property_id"] is None
        assert data["plate_code"].startswith("PLATE-")
        assert data["status"] == "unactivated"
        assert data["activated_at"] is None
        assert data["verified_at"] is None

    finally:
        app.dependency_overrides.clear()


def create_user_access_token(
    db_session,
    *,
    role: str,
    clearance: str | None = None,
):
    user = User(
        email=f"auth-test-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        clearance=clearance,
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    return create_access_token(
        subject=str(user.id),
    )


@pytest.mark.parametrize(
    ("role", "clearance", "expected_detail"),
    [
        ("landlord", "plate_operations", "Employee access required"),
        ("employee", None, "Insufficient employee clearance"),
        ("employee", "support", "Insufficient employee clearance"),
    ],
)
def test_create_address_plate_api_requires_employee_clearance(
    db_session,
    role,
    clearance,
    expected_detail,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        access_token = create_user_access_token(
            db_session,
            role=role,
            clearance=clearance,
        )

        response = TestClient(app).post(
            "/api/v1/address-plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == expected_detail

    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("role", "clearance", "expected_detail"),
    [
        ("landlord", "plate_operations", "Employee access required"),
        ("employee", None, "Insufficient employee clearance"),
        ("employee", "support", "Insufficient employee clearance"),
    ],
)
def test_verify_address_plate_api_requires_employee_clearance(
    client,
    db_session,
    role,
    clearance,
    expected_detail,
):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        from app.services.address_plate_service import AddressPlateService

        service = AddressPlateService(db_session)
        plate = service.create_plate()

        restricted_token = create_user_access_token(
            db_session,
            role=role,
            clearance=clearance,
        )

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/verify",
            headers={
                "Authorization": f"Bearer {restricted_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == expected_detail

        db_session.refresh(plate)

        assert plate.status == "unactivated"
        assert plate.verified_at is None

    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("role", "clearance", "expected_detail"),
    [
        ("landlord", "plate_operations", "Employee access required"),
        ("employee", None, "Insufficient employee clearance"),
        ("employee", "support", "Insufficient employee clearance"),
    ],
)
def test_link_address_plate_api_requires_employee_clearance(
    client,
    db_session,
    role,
    clearance,
    expected_detail,
):
    from app.models.landlord import Landlord
    from app.models.property import Property
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        landlord_user = User(
            email=f"auth-link-landlord-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(landlord_user)
        db_session.flush()

        landlord = Landlord(
            user_id=landlord_user.id,
            display_name="Authorization Test Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Authorization Test Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)

        plate = service.create_plate()
        service.verify_plate(plate.plate_code)

        restricted_token = create_user_access_token(
            db_session,
            role=role,
            clearance=clearance,
        )

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            headers={
                "Authorization": f"Bearer {restricted_token}",
            },
            json={
                "property_id": str(property.id),
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == expected_detail

        db_session.refresh(plate)

        assert plate.property_id is None
        assert plate.status == "verified"
        assert plate.activated_at is None

    finally:
        app.dependency_overrides.clear()


def test_get_address_plate_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        access_token = create_plate_operations_employee(
            db_session
        )

        create_response = client.post(
            "/api/v1/address-plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert create_response.status_code == 201

        plate_code = create_response.json()["plate_code"]

        response = client.get(
            f"/api/v1/address-plates/{plate_code}"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["plate_code"] == plate_code
        assert data["status"] == "unactivated"

    finally:
        app.dependency_overrides.clear()


def test_get_address_plate_api_returns_404_for_missing_plate(
    db_session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        response = client.get(
            f"/api/v1/address-plates/PLATE-{uuid.uuid4().hex[:12].upper()}"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Plate not found"

    finally:
        app.dependency_overrides.clear()


def test_verify_address_plate_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        access_token = create_plate_operations_employee(
            db_session
        )

        create_response = client.post(
            "/api/v1/address-plates",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert create_response.status_code == 201

        plate_code = create_response.json()["plate_code"]

        response = client.post(
            f"/api/v1/address-plates/{plate_code}/verify",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["plate_code"] == plate_code
        assert data["status"] == "verified"
        assert data["verified_at"] is not None
        assert data["activated_at"] is None

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        access_token = create_plate_operations_employee(
            db_session
        )

        from app.models.landlord import Landlord
        from app.models.property import Property
        from app.models.user import User
        from app.services.address_plate_service import AddressPlateService

        landlord_user = User(
            email=f"link-landlord-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(landlord_user)
        db_session.flush()

        landlord = Landlord(
            user_id=landlord_user.id,
            display_name="Link API Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Link API Property",
            property_type="residential",
            status="draft",
        )

        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)

        plate = service.create_plate()
        service.verify_plate(plate.plate_code)

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["plate_code"] == plate.plate_code
        assert data["property_id"] == str(property.id)
        assert data["status"] == "active"
        assert data["verified_at"] is not None
        assert data["activated_at"] is not None

    finally:
        app.dependency_overrides.clear()


def test_link_unverified_address_plate_api(
    client,
    db_session,
):
    from app.models.landlord import Landlord
    from app.models.property import Property
    from app.models.user import User
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        access_token = create_plate_operations_employee(
            db_session
        )

        landlord = db_session.query(Landlord).first()

        if landlord is None:
            raise AssertionError("Expected a landlord for the test property")

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Unverified Link Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)
        plate = service.create_plate()

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Only verified plates can be linked to a property"
        )

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api_returns_404_for_missing_property(
    client,
    db_session,
):
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        access_token = create_plate_operations_employee(
            db_session
        )

        service = AddressPlateService(db_session)
        plate = service.create_plate()

        service.verify_plate(plate.plate_code)

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api_rejects_property_with_existing_plate(
    client,
    db_session,
):
    from app.models.landlord import Landlord
    from app.models.property import Property
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        access_token = create_plate_operations_employee(
            db_session
        )

        landlord = db_session.query(Landlord).first()

        if landlord is None:
            raise AssertionError("Expected a landlord for the test property")

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Double Link Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)

        first_plate = service.create_plate()
        service.verify_plate(first_plate.plate_code)

        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        first_response = client.post(
            f"/api/v1/address-plates/{first_plate.plate_code}/link",
            headers=headers,
            json={
                "property_id": str(property.id),
            },
        )

        assert first_response.status_code == 200

        second_plate = service.create_plate()
        service.verify_plate(second_plate.plate_code)

        second_response = client.post(
            f"/api/v1/address-plates/{second_plate.plate_code}/link",
            headers=headers,
            json={
                "property_id": str(property.id),
            },
        )

        assert second_response.status_code == 400
        assert second_response.json()["detail"] == (
            "Property already has a primary address plate"
        )

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api_requires_authentication(db_session):
    from app.models.landlord import Landlord
    from app.models.user import User
    from app.models.property import Property
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        user = User(
            email=f"unauth-link-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Unauthenticated Link Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Unauthenticated Link Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)

        plate = service.create_plate()
        service.verify_plate(plate.plate_code)

        response = TestClient(app).post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            json={
                "property_id": str(property.id),
            },
        )

        assert response.status_code in {401, 403}

        db_session.refresh(plate)

        assert plate.property_id is None
        assert plate.status == "verified"
        assert plate.activated_at is None

    finally:
        app.dependency_overrides.clear()


def test_link_address_plate_api_allows_employee_across_landlord_ownership(
    client,
    db_session,
):
    from app.models.landlord import Landlord
    from app.models.property import Property
    from app.models.user import User
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        access_token = create_plate_operations_employee(
            db_session
        )

        landlord_user = User(
            email=f"cross-landlord-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(landlord_user)
        db_session.flush()

        landlord = Landlord(
            user_id=landlord_user.id,
            display_name="Property Owner",
            phone="+254700000003",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Employee Operational Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)

        plate = service.create_plate()
        service.verify_plate(plate.plate_code)

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/link",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "property_id": str(property.id),
            },
        )

        assert response.status_code == 200
        assert response.json()["property_id"] == str(property.id)
        assert response.json()["status"] == "active"

    finally:
        app.dependency_overrides.clear()


def test_verify_active_address_plate_api_rejects_reverification(
    client,
    db_session,
):
    from app.models.landlord import Landlord
    from app.models.property import Property
    from app.models.user import User
    from app.services.address_plate_service import AddressPlateService

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        access_token = create_plate_operations_employee(
            db_session
        )

        user = User(
            email=f"active-reverify-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
            user_id=user.id,
            display_name="Active Reverify Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Active Reverify Property",
            property_type="residential",
            status="draft",
        )
        db_session.add(property)
        db_session.flush()

        service = AddressPlateService(db_session)

        plate = service.create_plate()
        service.verify_plate(plate.plate_code)
        service.link_plate_to_property(
            plate_code=plate.plate_code,
            property_id=property.id,
        )

        response = client.post(
            f"/api/v1/address-plates/{plate.plate_code}/verify",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Plate cannot be verified in its current status"
        )

        db_session.refresh(plate)

        assert plate.status == "active"
        assert plate.property_id == property.id
        assert plate.verified_at is not None
        assert plate.activated_at is not None

    finally:
        app.dependency_overrides.clear()
