import uuid

from fastapi.testclient import TestClient

from app.api.v1.properties import router
from app.main import app
from app.db.session import get_db
from app.models.address_plate import AddressPlate
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.models.user import User


def test_activate_property_api(db_session):
        user = User(
                email=f"activation-api-{uuid.uuid4()}@example.com",
                password_hash="test-hash",
                role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
                user_id=user.id,
                display_name="Activation API Landlord",
                phone="+254700000000",
                landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
                landlord_id=landlord.id,
                property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
                name="Activation API Property",
                property_type="residential",
                status="draft",
        )
        db_session.add(property)
        db_session.flush()

        address = PropertyAddress(
                property_id=property.id,
                formatted_address="Activation API Address",
                county="Nairobi",
                locality="Nairobi",
        )
        db_session.add(address)
        db_session.flush()

        plate = AddressPlate(
                plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
                status="verified",
        )
        db_session.add(plate)
        db_session.flush()

        def override_get_db():
                yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
                client = TestClient(app)

                response = client.post(
                        f"/api/v1/properties/{property.id}/activate",
                        json={
                                "plate_code": plate.plate_code,
                        },
                )

                assert response.status_code == 200

                data = response.json()

                assert data["property_id"] == str(property.id)
                assert data["plate_code"] == plate.plate_code
                assert data["status"] == "active"
                assert data["activated_at"] is not None

                assert property.status == "active"

        finally:
                app.dependency_overrides.clear()


def test_activate_property_api_requires_address(db_session):
        user = User(
                email=f"activation-no-address-{uuid.uuid4()}@example.com",
                password_hash="test-hash",
                role="landlord",
        )
        db_session.add(user)
        db_session.flush()

        landlord = Landlord(
                user_id=user.id,
                display_name="No Address Landlord",
                phone="+254700000000",
                landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
                landlord_id=landlord.id,
                property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
                name="No Address Property",
                property_type="residential",
                status="draft",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
                plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
                status="verified",
        )
        db_session.add(plate)
        db_session.flush()

        def override_get_db():
                yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
                client = TestClient(app)

                response = client.post(
                        f"/api/v1/properties/{property.id}/activate",
                        json={
                                "plate_code": plate.plate_code,
                        },
                )

                assert response.status_code == 400
                assert response.json()["detail"] == (
                        "Property must have an address before activation"
                )

                assert property.status == "draft"

        finally:
                app.dependency_overrides.clear()
