import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.building import Building
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User


def create_user(
    db_session: Session,
    *,
    role: str = "landlord",
    is_active: bool = True,
) -> User:
    user = User(
        email=f"{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_landlord(
    db_session: Session,
    user: User,
) -> Landlord:
    landlord = Landlord(
        user_id=user.id,
        display_name="Building API Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()
    return landlord


def create_property(
    db_session: Session,
    landlord: Landlord,
    *,
    name: str = "Building API Property",
) -> Property:
    property_record = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name=name,
        property_type="residential",
        status="draft",
    )
    db_session.add(property_record)
    db_session.flush()
    return property_record


def test_create_building_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(db_session, landlord)

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/buildings",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "building_number": "1",
                "name": "Main Building",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["property_id"] == str(property_record.id)
        assert data["building_number"] == "1"
        assert data["name"] == "Main Building"
        assert data["status"] == "draft"

    finally:
        app.dependency_overrides.clear()


def test_list_buildings_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(db_session, landlord)

        building_one = Building(
            property_id=property_record.id,
            building_number="1",
            name="Building One",
            status="draft",
        )
        building_two = Building(
            property_id=property_record.id,
            building_number="2",
            name="Building Two",
            status="active",
        )
        db_session.add_all([building_one, building_two])
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 2
        assert {item["id"] for item in data} == {
            str(building_one.id),
            str(building_two.id),
        }

    finally:
        app.dependency_overrides.clear()


def test_get_building_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(db_session, landlord)

        building = Building(
            property_id=property_record.id,
            building_number="1",
            name="Main Building",
            status="draft",
        )
        db_session.add(building)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(building.id)
        assert data["property_id"] == str(property_record.id)
        assert data["building_number"] == "1"
        assert data["name"] == "Main Building"
        assert data["status"] == "draft"

    finally:
        app.dependency_overrides.clear()


def test_create_building_api_denies_another_landlord(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner = create_user(db_session)
        owner_landlord = create_landlord(db_session, owner)
        property_record = create_property(
            db_session,
            owner_landlord,
        )

        other_user = create_user(db_session)

        access_token = create_access_token(
            subject=str(other_user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/buildings",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "building_number": "1",
                "name": "Unauthorized Building",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "User is not authorized for this property"
        )

    finally:
        app.dependency_overrides.clear()


def test_get_building_api_denies_another_landlord(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner = create_user(db_session)
        owner_landlord = create_landlord(db_session, owner)
        property_record = create_property(
            db_session,
            owner_landlord,
        )

        building = Building(
            property_id=property_record.id,
            building_number="1",
            name="Private Building",
            status="draft",
        )
        db_session.add(building)
        db_session.flush()

        other_user = create_user(db_session)

        access_token = create_access_token(
            subject=str(other_user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "User is not authorized for this property"
        )

    finally:
        app.dependency_overrides.clear()


def test_get_building_api_returns_404_for_missing_building(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(db_session, landlord)

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{uuid.uuid4()}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Building not found"

    finally:
        app.dependency_overrides.clear()


def test_get_building_api_returns_404_for_wrong_parent_property(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)

        property_one = create_property(
            db_session,
            landlord,
            name="Property One",
        )
        property_two = create_property(
            db_session,
            landlord,
            name="Property Two",
        )

        building = Building(
            property_id=property_one.id,
            building_number="1",
            name="Property One Building",
            status="draft",
        )
        db_session.add(building)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_two.id}/buildings/{building.id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Building not found"

    finally:
        app.dependency_overrides.clear()
