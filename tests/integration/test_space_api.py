import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.building import Building
from app.models.floor import Floor
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.space import Space
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
        display_name="Space API Landlord",
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
    name: str = "Space API Property",
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


def create_building(
    db_session: Session,
    property_record: Property,
) -> Building:
    building = Building(
        property_id=property_record.id,
        building_number="1",
        name="Building One",
        status="draft",
    )
    db_session.add(building)
    db_session.flush()
    return building


def create_floor(
    db_session: Session,
    building: Building,
) -> Floor:
    floor = Floor(
        building_id=building.id,
        floor_number="1",
        name="Ground Floor",
        status="active",
    )
    db_session.add(floor)
    db_session.flush()
    return floor


def test_create_space_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(db_session, landlord)
        building = create_building(db_session, property_record)
        floor = create_floor(db_session, building)

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{floor.id}/spaces",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "space_number": "A-101",
                "name": "Apartment 101",
                "space_type": "apartment",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["floor_id"] == str(floor.id)
        assert data["space_number"] == "A-101"
        assert data["name"] == "Apartment 101"
        assert data["space_type"] == "apartment"
        assert data["status"] == "draft"

    finally:
        app.dependency_overrides.clear()


def test_list_spaces_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(db_session, landlord)
        building = create_building(db_session, property_record)
        floor = create_floor(db_session, building)

        space_one = Space(
            floor_id=floor.id,
            space_number="A-101",
            name="Apartment 101",
            space_type="apartment",
            status="active",
        )
        space_two = Space(
            floor_id=floor.id,
            space_number="A-102",
            name="Apartment 102",
            space_type="apartment",
            status="active",
        )
        db_session.add_all([space_one, space_two])
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{floor.id}/spaces",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 2
        assert {item["id"] for item in data} == {
            str(space_one.id),
            str(space_two.id),
        }

    finally:
        app.dependency_overrides.clear()


def test_get_space_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(db_session, landlord)
        building = create_building(db_session, property_record)
        floor = create_floor(db_session, building)

        space = Space(
            floor_id=floor.id,
            space_number="A-101",
            name="Apartment 101",
            space_type="apartment",
            status="active",
        )
        db_session.add(space)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{floor.id}/spaces/{space.id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(space.id)
        assert data["floor_id"] == str(floor.id)
        assert data["space_number"] == "A-101"
        assert data["name"] == "Apartment 101"
        assert data["space_type"] == "apartment"
        assert data["status"] == "active"

    finally:
        app.dependency_overrides.clear()


def test_create_space_api_denies_another_landlord(
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
        building = create_building(db_session, property_record)
        floor = create_floor(db_session, building)

        other_user = create_user(db_session)

        access_token = create_access_token(
            subject=str(other_user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{floor.id}/spaces",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "space_number": "A-101",
                "name": "Unauthorized Space",
                "space_type": "apartment",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "User is not authorized for this property"
        )

    finally:
        app.dependency_overrides.clear()


def test_get_space_api_denies_another_landlord(
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
        building = create_building(db_session, property_record)
        floor = create_floor(db_session, building)

        space = Space(
            floor_id=floor.id,
            space_number="A-101",
            name="Private Space",
            space_type="apartment",
            status="active",
        )
        db_session.add(space)
        db_session.flush()

        other_user = create_user(db_session)

        access_token = create_access_token(
            subject=str(other_user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{floor.id}/spaces/{space.id}",
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


def test_get_space_api_returns_404_for_missing_space(
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
        building = create_building(db_session, property_record)
        floor = create_floor(db_session, building)

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{floor.id}/spaces/{uuid.uuid4()}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Space not found"

    finally:
        app.dependency_overrides.clear()


def test_get_space_api_returns_404_for_wrong_parent_floor(
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
        building = create_building(db_session, property_record)

        floor_one = create_floor(db_session, building)
        floor_two = Floor(
            building_id=building.id,
            floor_number="2",
            name="First Floor",
            status="active",
        )
        db_session.add(floor_two)
        db_session.flush()

        space = Space(
            floor_id=floor_two.id,
            space_number="A-201",
            name="Apartment 201",
            space_type="apartment",
            status="active",
        )
        db_session.add(space)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{floor_one.id}/spaces/{space.id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Space not found"

    finally:
        app.dependency_overrides.clear()


def test_get_space_api_returns_404_for_wrong_parent_property(
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

        building = create_building(db_session, property_one)
        floor = create_floor(db_session, building)

        space = Space(
            floor_id=floor.id,
            space_number="A-101",
            name="Property One Space",
            space_type="apartment",
            status="active",
        )
        db_session.add(space)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_two.id}/buildings/{building.id}/floors/{floor.id}/spaces/{space.id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Space not found"

    finally:
        app.dependency_overrides.clear()


def test_list_spaces_api_returns_404_for_wrong_parent_building(
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

        building_one = create_building(db_session, property_one)
        building_two = create_building(db_session, property_two)

        floor = create_floor(db_session, building_two)

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_one.id}/buildings/{building_two.id}/floors/{floor.id}/spaces",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Building not found"

    finally:
        app.dependency_overrides.clear()


def test_create_space_api_returns_404_for_wrong_parent_floor(
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
        building = create_building(db_session, property_record)

        other_building = Building(
            property_id=property_record.id,
            building_number="2",
            name="Building Two",
            status="draft",
        )
        db_session.add(other_building)
        db_session.flush()

        floor = create_floor(db_session, other_building)

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{floor.id}/spaces",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "space_number": "A-101",
                "name": "Wrong Building Space",
                "space_type": "apartment",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Floor not found"

    finally:
        app.dependency_overrides.clear()
