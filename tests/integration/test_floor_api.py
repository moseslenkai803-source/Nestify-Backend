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
        display_name="Floor API Landlord",
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


def test_create_floor_api(db_session: Session):
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
            name="Building One",
            status="draft",
        )
        db_session.add(building)
        db_session.flush()





        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "floor_number": "1",
                "name": "First Floor",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["building_id"] == str(building.id)
        assert data["floor_number"] == "1"
        assert data["name"] == "First Floor"
        assert data["status"] == "draft"

    finally:
        app.dependency_overrides.clear()


def test_list_floors_api(db_session: Session):
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
            name="Building One",
            status="draft",
        )
        db_session.add(building)
        db_session.flush()


        floor_one = Floor(
            building_id=building.id,
            floor_number="1",
            name="Ground Floor",
            status="active",
        )
        floor_two = Floor(
            building_id=building.id,
            floor_number="2",
            name="First Floor",
            status="active",
        )
        db_session.add_all([floor_one, floor_two])
        db_session.flush()



        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 2
        assert {item["id"] for item in data} == {
            str(floor_one.id),
            str(floor_two.id),
        }

    finally:
        app.dependency_overrides.clear()


def test_get_floor_api(db_session: Session):
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
            name="First Floor",
            status="draft",
        )
        db_session.add(building)
        db_session.flush()
        floor = Floor(
            building_id=building.id,
            floor_number="1",
            name="First Floor",
            status="active",
        )
        db_session.add(floor)
        db_session.flush()




        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{floor.id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == str(floor.id)
        assert data["building_id"] == str(building.id)
        assert data["floor_number"] == "1"
        assert data["name"] == "First Floor"
        assert data["status"] == "active"

    finally:
        app.dependency_overrides.clear()


def test_create_floor_api_denies_another_landlord(
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
        building = Building(
            property_id=property_record.id,
            building_number="1",
            name="Private Building",
            status="draft",
        )
        db_session.add(building)
        db_session.flush()




        access_token = create_access_token(
            subject=str(other_user.id),
        )

        response = client.post(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "floor_number": "1",
                "name": "Unauthorized Floor",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "User is not authorized for this property"
        )

    finally:
        app.dependency_overrides.clear()


def test_get_floor_api_denies_another_landlord(
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

        floor = Floor(
            building_id=building.id,
            floor_number="1",
            name="Private Floor",
            status="active",
        )
        db_session.add(floor)
        db_session.flush()

        other_user = create_user(db_session)




        access_token = create_access_token(
            subject=str(other_user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{floor.id}",
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


def test_get_floor_api_returns_404_for_missing_floor(
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
            f"/api/v1/properties/{property_record.id}/buildings/{building.id}/floors/{uuid.uuid4()}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Floor not found"

    finally:
        app.dependency_overrides.clear()


def test_get_floor_api_returns_404_for_wrong_parent_property(
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
        floor = Floor(
            building_id=building.id,
            floor_number="1",
            name="Property One Floor",
            status="active",
        )
        db_session.add(floor)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_two.id}/buildings/{building.id}/floors/{floor.id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Floor not found"

    finally:
        app.dependency_overrides.clear()


def test_list_floors_api_returns_404_for_wrong_parent_building(
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

        building_one = Building(
            property_id=property_one.id,
            building_number="1",
            name="Property One Building",
            status="draft",
        )
        building_two = Building(
            property_id=property_two.id,
            building_number="1",
            name="Property Two Building",
            status="draft",
        )
        db_session.add_all([building_one, building_two])
        db_session.flush()

        floor = Floor(
            building_id=building_two.id,
            floor_number="1",
            name="Property Two Floor",
            status="active",
        )
        db_session.add(floor)
        db_session.flush()

        access_token = create_access_token(
            subject=str(user.id),
        )

        response = client.get(
            f"/api/v1/properties/{property_one.id}/buildings/{building_two.id}/floors",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Building not found"

    finally:
        app.dependency_overrides.clear()
