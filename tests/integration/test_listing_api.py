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
        display_name="Listing API Landlord",
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
    status: str = "active",
) -> Property:
    property_record = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Listing API Property",
        property_type="residential",
        status=status,
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
        building_number=f"B-{uuid.uuid4().hex[:6].upper()}",
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
        floor_number=f"F-{uuid.uuid4().hex[:6].upper()}",
        name="Ground Floor",
        status="active",
    )
    db_session.add(floor)
    db_session.flush()
    return floor


def create_space(
    db_session: Session,
    floor: Floor,
) -> Space:
    space = Space(
        floor_id=floor.id,
        space_number=f"S-{uuid.uuid4().hex[:6].upper()}",
        name="Space 101",
        space_type="general",
        status="active",
    )
    db_session.add(space)
    db_session.flush()
    return space


def auth_headers(user: User) -> dict[str, str]:
    access_token = create_access_token(
        subject=str(user.id),
    )

    return {
        "Authorization": f"Bearer {access_token}",
    }


def test_create_property_listing_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(db_session, landlord)

        response = client.post(
            f"/api/v1/properties/{property_record.id}/listings",
            headers=auth_headers(user),
            json={
                "transaction_type": "sale",
                "title": "Entire Property for Sale",
                "description": "A complete residential property.",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["target_type"] == "property"
        assert data["target_id"] == str(property_record.id)
        assert data["transaction_type"] == "sale"
        assert data["title"] == "Entire Property for Sale"
        assert data["description"] == "A complete residential property."
        assert data["status"] == "draft"

    finally:
        app.dependency_overrides.clear()


def test_create_floor_listing_api(db_session: Session):
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

        response = client.post(
            (
                f"/api/v1/properties/{property_record.id}"
                f"/buildings/{building.id}"
                f"/floors/{floor.id}/listings"
            ),
            headers=auth_headers(user),
            json={
                "transaction_type": "rent",
                "title": "First Floor for Rent",
                "description": "Commercial floor space.",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["target_type"] == "floor"
        assert data["target_id"] == str(floor.id)
        assert data["transaction_type"] == "rent"
        assert data["title"] == "First Floor for Rent"
        assert data["status"] == "draft"

    finally:
        app.dependency_overrides.clear()


def test_create_space_listing_api(db_session: Session):
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
        space = create_space(db_session, floor)

        response = client.post(
            (
                f"/api/v1/properties/{property_record.id}"
                f"/buildings/{building.id}"
                f"/floors/{floor.id}"
                f"/spaces/{space.id}/listings"
            ),
            headers=auth_headers(user),
            json={
                "transaction_type": "rent",
                "title": "Space 101 for Rent",
                "description": "Ready for occupancy.",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["target_type"] == "space"
        assert data["target_id"] == str(space.id)
        assert data["transaction_type"] == "rent"
        assert data["title"] == "Space 101 for Rent"
        assert data["description"] == "Ready for occupancy."
        assert data["status"] == "draft"

    finally:
        app.dependency_overrides.clear()


def test_create_property_listing_api_denies_another_landlord(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        owner = create_user(db_session)
        landlord = create_landlord(db_session, owner)
        property_record = create_property(db_session, landlord)

        other_user = create_user(db_session)

        response = client.post(
            f"/api/v1/properties/{property_record.id}/listings",
            headers=auth_headers(other_user),
            json={
                "transaction_type": "sale",
                "title": "Unauthorized Listing",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "User is not authorized for this property"
        )

    finally:
        app.dependency_overrides.clear()


def test_create_property_listing_api_returns_404_for_missing_property(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)

        missing_property_id = uuid.uuid4()

        response = client.post(
            f"/api/v1/properties/{missing_property_id}/listings",
            headers=auth_headers(user),
            json={
                "transaction_type": "sale",
                "title": "Missing Property Listing",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    finally:
        app.dependency_overrides.clear()


def test_publish_listing_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(db_session, landlord)

        create_response = client.post(
            f"/api/v1/properties/{property_record.id}/listings",
            headers=auth_headers(user),
            json={
                "transaction_type": "rent",
                "title": "Property for Rent",
            },
        )

        assert create_response.status_code == 201

        listing_id = create_response.json()["id"]

        publish_response = client.post(
            f"/api/v1/listings/{listing_id}/publish",
            headers=auth_headers(user),
        )

        assert publish_response.status_code == 200

        data = publish_response.json()

        assert data["id"] == listing_id
        assert data["target_type"] == "property"
        assert data["target_id"] == str(property_record.id)
        assert data["status"] == "published"

    finally:
        app.dependency_overrides.clear()


def test_publish_listing_api_rejects_inactive_property(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(
            db_session,
            landlord,
            status="draft",
        )

        create_response = client.post(
            f"/api/v1/properties/{property_record.id}/listings",
            headers=auth_headers(user),
            json={
                "transaction_type": "sale",
                "title": "Draft Property Listing",
            },
        )

        assert create_response.status_code == 201

        listing_id = create_response.json()["id"]

        publish_response = client.post(
            f"/api/v1/listings/{listing_id}/publish",
            headers=auth_headers(user),
        )

        assert publish_response.status_code == 400
        assert publish_response.json()["detail"] == (
            "Property must be active before listing can be published"
        )

    finally:
        app.dependency_overrides.clear()


def test_publish_listing_api_returns_404_for_missing_listing(
    db_session: Session,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)

        response = client.post(
            f"/api/v1/listings/{uuid.uuid4()}/publish",
            headers=auth_headers(user),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Listing not found"

    finally:
        app.dependency_overrides.clear()


def test_unpublish_listing_api(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        user = create_user(db_session)
        landlord = create_landlord(db_session, user)
        property_record = create_property(db_session, landlord)

        create_response = client.post(
            f"/api/v1/properties/{property_record.id}/listings",
            headers=auth_headers(user),
            json={
                "transaction_type": "rent",
                "title": "Rental Property",
            },
        )

        assert create_response.status_code == 201

        listing_id = create_response.json()["id"]

        publish_response = client.post(
            f"/api/v1/listings/{listing_id}/publish",
            headers=auth_headers(user),
        )

        assert publish_response.status_code == 200
        assert publish_response.json()["status"] == "published"

        unpublish_response = client.post(
            f"/api/v1/listings/{listing_id}/unpublish",
            headers=auth_headers(user),
        )

        assert unpublish_response.status_code == 200

        data = unpublish_response.json()

        assert data["id"] == listing_id
        assert data["status"] == "unpublished"

    finally:
        app.dependency_overrides.clear()


def test_unpublish_listing_api_rejects_unpublished_listing(
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

        create_response = client.post(
            f"/api/v1/properties/{property_record.id}/listings",
            headers=auth_headers(user),
            json={
                "transaction_type": "rent",
                "title": "Unpublished Property",
            },
        )

        assert create_response.status_code == 201

        listing_id = create_response.json()["id"]

        response = client.post(
            f"/api/v1/listings/{listing_id}/unpublish",
            headers=auth_headers(user),
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Listing is not published"

    finally:
        app.dependency_overrides.clear()
