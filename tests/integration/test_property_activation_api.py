import pytest
import uuid

from datetime import UTC, datetime, timedelta
from app.models.property_installation import PropertyInstallation
from app.models.property_installation_verification import PropertyInstallationVerification

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.core.security import create_access_token
from app.main import app
from app.db.session import get_db
from app.models.address_plate import AddressPlate
from app.models.address_plate_lifecycle_event import AddressPlateLifecycleEvent
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_address import PropertyAddress
from app.models.property_location import PropertyLocation
from app.models.property_location_verification import (
    PropertyLocationVerification,
)
from app.models.user import User
from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.services.property_access_service import PropertyAccessService
from tests.conftest import cleanup_installation_test_context


def _add_approved_property_location(db_session, property_id, verified_by):
    now = datetime.now(UTC)
    location = PropertyLocation(
        property_id=property_id,
        version_number=1,
        is_current=True,
        latitude=-1.2921,
        longitude=36.8219,
        location="SRID=4326;POINT(36.8219 -1.2921)",
        source="test_fixture",
        capture_method="manual_entry",
        captured_at=now,
        submitted_by_id=verified_by,
        submitted_at=now,
        status="approved",
    )
    db_session.add(location)
    db_session.flush()

    db_session.add(
        PropertyLocationVerification(
            location_id=location.id,
            verified_by=verified_by,
            decision="approved",
            verification_method="test_fixture",
            verified_at=now,
        )
    )
    db_session.flush()
    return location


def _add_verified_activation_evidence(
    db_session,
    property,
    plate,
    installer_id,
    verified_by,
):
    from datetime import UTC, datetime

    from app.models.property_installation import PropertyInstallation
    from app.models.property_installation_verification import (
        PropertyInstallationVerification,
    )

    now = datetime.now(UTC)
    installation = PropertyInstallation(
        property_id=property.id,
        plate_id=plate.id,
        installer_id=installer_id,
        latitude=-1.286389,
        longitude=36.817223,
        captured_at=now,
        status="verified",
    )
    db_session.add(installation)
    db_session.flush()

    verification = PropertyInstallationVerification(
        installation_id=installation.id,
        verified_by=verified_by,
        status="verified",
        verified_at=now,
        notes="Verified installation evidence for activation API test",
    )
    db_session.add(verification)
    db_session.flush()


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
                status="verified",
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
                property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
                status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        for event_type in (
                "manufactured",
                "allocated",
                "dispatched",
                "installed",
                "verified",
        ):
                db_session.add(
                        AddressPlateLifecycleEvent(
                                plate_id=plate.id,
                                event_type=event_type,
                                performed_by=user.id,
                        )
                )
        db_session.flush()

        _add_verified_activation_evidence(
            db_session,
            property,
            plate,
            installer_id=user.id,
            verified_by=user.id,
        )
        _add_approved_property_location(
            db_session,
            property.id,
            verified_by=user.id,
        )

        try:
                client = TestClient(app)

                employee = User(
                    email=f"activation-employee-{uuid.uuid4()}@example.com",
                    password_hash="test-hash",
                    role="employee",
                )
                db_session.add(employee)
                db_session.flush()

                employee_record = Employee(
                    user_id=employee.id,
                    employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
                    department="Operations",
                    position="Test Employee",
                )
                db_session.add(employee_record)
                db_session.flush()

                db_session.add(
                    EmployeeClearance(
                        employee_id=employee_record.id,
                        clearance="plate_operations",
                        is_active=True,
                    )
                )
                db_session.flush()


                PropertyAccessService(db_session).grant_access(
                    user_id=employee.id,
                    property_id=property.id,
                    access_type="plate_operations",
                )

                access_token = create_access_token(
                    subject=str(employee.id),
                )

                response = client.post(
                        f"/api/v1/properties/{property.id}/activate",
                        headers={
                                "Authorization": f"Bearer {access_token}",
                        },
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

                db_session.refresh(property)
                assert property.status == "active"

        finally:
                pass


def test_activate_property_api_allows_employee_across_landlord_ownership(
    db_session,
):
    owner_user = User(
        email=f"activation-owner-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(owner_user)
    db_session.flush()

    owner_landlord = Landlord(
        user_id=owner_user.id,
        display_name="Activation Owner",
        phone="+254700000001",
        landlord_type="individual",
    )
    db_session.add(owner_landlord)
    db_session.flush()

    property = Property(
        landlord_id=owner_landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Employee Activation Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Employee Activation Address",
        county="Nairobi",
        locality="Nairobi",
    )
    db_session.add(address)
    db_session.flush()

    plate = AddressPlate(
        property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )
    db_session.add(plate)
    db_session.flush()

    employee = User(
        email=f"activation-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
    )
    db_session.add(employee)
    db_session.flush()

    employee_record = Employee(
        user_id=employee.id,
        employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
        department="Operations",
        position="Test Employee",
    )
    db_session.add(employee_record)
    db_session.flush()

    db_session.add(
        EmployeeClearance(
            employee_id=employee_record.id,
            clearance="plate_operations",
            is_active=True,
        )
    )
    db_session.flush()

    for event_type in ("manufactured", "allocated", "dispatched", "installed", "verified"):
        db_session.add(
            AddressPlateLifecycleEvent(
                plate_id=plate.id,
                event_type=event_type,
                performed_by=employee.id,
            )
        )
    db_session.flush()

    _add_verified_activation_evidence(
        db_session,
        property,
        plate,
        installer_id=employee.id,
        verified_by=employee.id,
    )
    _add_approved_property_location(
        db_session,
        property.id,
        verified_by=employee.id,
    )
    PropertyAccessService(db_session).grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )


    try:
        client = TestClient(app)

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": plate.plate_code,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "active"

        db_session.refresh(property)
        db_session.refresh(plate)

        assert property.status == "active"
        assert plate.property_id == property.id
        assert plate.status == "active"

    finally:
        pass


def test_activate_property_api_requires_property_access(db_session):
    owner_user = User(
        email=f"activation-access-owner-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(owner_user)
    db_session.flush()

    landlord = Landlord(
        user_id=owner_user.id,
        display_name="Activation Access Owner",
        phone="+254700000002",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Unauthorized Activation Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Unauthorized Activation Address",
        county="Nairobi",
        locality="Nairobi",
    )
    db_session.add(address)
    db_session.flush()

    plate = AddressPlate(
        property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )
    db_session.add(plate)
    db_session.flush()

    employee = User(
        email=f"activation-unauthorized-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
    )
    db_session.add(employee)
    db_session.flush()

    employee_record = Employee(
        user_id=employee.id,
        employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
        department="Operations",
        position="Test Employee",
    )
    db_session.add(employee_record)
    db_session.flush()

    db_session.add(
        EmployeeClearance(
            employee_id=employee_record.id,
            clearance="plate_operations",
            is_active=True,
        )
    )
    db_session.flush()


    try:
        client = TestClient(app)

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": plate.plate_code,
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "User is not authorized for this property"
        )

        db_session.refresh(property)
        db_session.refresh(plate)

        assert property.status == "verified"
        assert plate.property_id == property.id
        assert plate.status == "unactivated"
        assert plate.activated_at is None

    finally:
        pass


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
                status="verified",
        )
        db_session.add(property)
        db_session.flush()

        plate = AddressPlate(
                property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
                status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()


        try:
                client = TestClient(app)

                employee = User(
                    email=f"activation-employee-{uuid.uuid4()}@example.com",
                    password_hash="test-hash",
                    role="employee",
                )
                db_session.add(employee)
                db_session.flush()

                employee_record = Employee(
                    user_id=employee.id,
                    employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
                    department="Operations",
                    position="Test Employee",
                )
                db_session.add(employee_record)
                db_session.flush()

                db_session.add(
                    EmployeeClearance(
                        employee_id=employee_record.id,
                        clearance="plate_operations",
                        is_active=True,
                    )
                )
                db_session.flush()


                PropertyAccessService(db_session).grant_access(
                    user_id=employee.id,
                    property_id=property.id,
                    access_type="plate_operations",
                )

                access_token = create_access_token(
                    subject=str(employee.id),
                )

                response = client.post(
                        f"/api/v1/properties/{property.id}/activate",
                        headers={
                                "Authorization": f"Bearer {access_token}",
                        },
                        json={
                                "plate_code": plate.plate_code,
                        },
                )

                assert response.status_code == 400
                assert response.json()["detail"] == (
                        "Property must have an address before activation"
                )

                assert property.status == "verified"

        finally:
                pass


def test_activate_property_api_requires_approved_location(db_session):
    user = User(
        email=f"activation-no-location-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="No Location Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="No Approved Location Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    db_session.add(
        PropertyAddress(
            property_id=property.id,
            formatted_address="Westlands, Nairobi",
            county="Nairobi",
            sub_county="Westlands",
            locality="Westlands",
        )
    )
    db_session.flush()

    plate = AddressPlate(
        property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )
    db_session.add(plate)
    db_session.flush()

    employee = User(
        email=f"activation-location-employee-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="employee",
    )
    db_session.add(employee)
    db_session.flush()

    employee_record = Employee(
        user_id=employee.id,
        employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
        department="Operations",
        position="Test Employee",
    )
    db_session.add(employee_record)
    db_session.flush()

    db_session.add(
        EmployeeClearance(
            employee_id=employee_record.id,
            clearance="plate_operations",
            is_active=True,
        )
    )
    db_session.flush()

    PropertyAccessService(db_session).grant_access(
        user_id=employee.id,
        property_id=property.id,
        access_type="plate_operations",
    )

    access_token = create_access_token(subject=str(employee.id))

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"plate_code": plate.plate_code},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Property must have a current approved location before activation"
        )

        db_session.refresh(property)
        assert property.status == "verified"

        assert db_session.scalar(
            select(func.count(AddressPlateLifecycleEvent.id)).where(
                AddressPlateLifecycleEvent.plate_id == plate.id
            )
        ) == 0
    finally:
        pass


def test_activate_property_api_returns_404_for_missing_plate(
    db_session,
):
    user = User(
        email=f"activation-missing-plate-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Missing Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Missing Plate Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Missing Plate Address",
        county="Nairobi",
        locality="Nairobi",
    )
    db_session.add(address)
    db_session.flush()


    try:
        client = TestClient(app)

        employee = User(
            email=f"activation-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
        )
        db_session.add(employee)
        db_session.flush()

        employee_record = Employee(
            user_id=employee.id,
            employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
            department="Operations",
            position="Test Employee",
        )
        db_session.add(employee_record)
        db_session.flush()

        db_session.add(
            EmployeeClearance(
                employee_id=employee_record.id,
                clearance="plate_operations",
                is_active=True,
            )
        )
        db_session.flush()


        PropertyAccessService(db_session).grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )

        _add_approved_property_location(
            db_session,
            property.id,
            verified_by=employee.id,
        )

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": "PLATE-DOES-NOT-EXIST",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Plate not found"

        db_session.refresh(property)

        assert property.status == "verified"

    finally:
        pass


def test_activate_property_api_rejects_unverified_plate(
    db_session,
):
    user = User(
        email=f"activation-unverified-plate-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Unverified Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Unverified Plate Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Unverified Plate Address",
        county="Nairobi",
        locality="Nairobi",
    )
    db_session.add(address)
    db_session.flush()

    plate = AddressPlate(
        property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )
    db_session.add(plate)
    db_session.flush()


    try:
        client = TestClient(app)

        employee = User(
            email=f"activation-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
        )
        db_session.add(employee)
        db_session.flush()

        employee_record = Employee(
            user_id=employee.id,
            employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
            department="Operations",
            position="Test Employee",
        )
        db_session.add(employee_record)
        db_session.flush()

        db_session.add(
            EmployeeClearance(
                employee_id=employee_record.id,
                clearance="plate_operations",
                is_active=True,
            )
        )
        db_session.flush()
        for event_type in ("manufactured", "allocated", "dispatched", "installed"):
            db_session.add(
                AddressPlateLifecycleEvent(
                    plate_id=plate.id,
                    event_type=event_type,
                    performed_by=employee.id,
                )
            )
        db_session.flush()

        _add_approved_property_location(
            db_session,
            property.id,
            verified_by=employee.id,
        )

        PropertyAccessService(db_session).grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )

        access_token = create_access_token(
            subject=str(employee.id),
        )

        response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": plate.plate_code,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "A verified installation with a successful verification record is required before activation"
        )

        db_session.refresh(property)
        db_session.refresh(plate)

        assert property.status == "verified"
        assert plate.property_id == property.id
        assert plate.status == "unactivated"
        assert plate.activated_at is None

    finally:
        pass


def test_activate_property_api_rejects_already_active_plate(
    db_session,
):
    user = User(
        email=f"activation-active-plate-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Active Plate Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Already Active Property",
        property_type="residential",
        status="verified",
    )
    db_session.add(property)
    db_session.flush()

    address = PropertyAddress(
        property_id=property.id,
        formatted_address="Already Active Address",
        county="Nairobi",
        locality="Nairobi",
    )
    db_session.add(address)
    db_session.flush()

    plate = AddressPlate(
        property_id=property.id,
        plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
        status="unactivated",
    )
    db_session.add(plate)
    db_session.flush()


    try:
        client = TestClient(app)

        employee = User(
            email=f"activation-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
        )
        db_session.add(employee)
        db_session.flush()

        employee_record = Employee(
            user_id=employee.id,
            employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
            department="Operations",
            position="Test Employee",
        )
        db_session.add(employee_record)
        db_session.flush()

        db_session.add(
            EmployeeClearance(
                employee_id=employee_record.id,
                clearance="plate_operations",
                is_active=True,
            )
        )
        db_session.flush()

        for event_type in ("manufactured", "allocated", "dispatched", "installed", "verified"):
            db_session.add(
                AddressPlateLifecycleEvent(
                    plate_id=plate.id,
                    event_type=event_type,
                    performed_by=employee.id,
                )
            )
        db_session.flush()

        _add_verified_activation_evidence(
            db_session,
            property,
            plate,
            installer_id=employee.id,
            verified_by=employee.id,
        )
        _add_approved_property_location(
            db_session,
            property.id,
            verified_by=employee.id,
        )
        PropertyAccessService(db_session).grant_access(
            user_id=employee.id,
            property_id=property.id,
            access_type="plate_operations",
        )

        access_token = create_access_token(
            subject=str(employee.id),
        )

        first_response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": plate.plate_code,
            },
        )

        assert first_response.status_code == 200

        second_response = client.post(
            f"/api/v1/properties/{property.id}/activate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "plate_code": plate.plate_code,
            },
        )

        assert second_response.status_code == 400
        assert second_response.json()["detail"] == (
            "Property is already active"
        )

        db_session.refresh(property)
        db_session.refresh(plate)

        assert property.status == "active"
        assert plate.property_id == property.id
        assert plate.status == "active"
        assert plate.activated_at is not None

    finally:
        pass


@pytest.mark.independent_db_transactions
def test_production_activation_rolls_back_when_commit_fails(
    db_session,
    monkeypatch,
):
    import app.db.session as db_session_module

    class ActivationCommitFailure(RuntimeError):
        pass

    property_id = uuid.uuid4()
    landlord_user_id = uuid.uuid4()
    employee_user_id = uuid.uuid4()
    test_user_ids = [landlord_user_id, employee_user_id]
    request_sessions = []

    def snapshot_activation_state(session, plate_id):
        property_status = session.scalar(
            select(Property.status).where(Property.id == property_id)
        )
        plate_status, activated_at = session.execute(
            select(AddressPlate.status, AddressPlate.activated_at).where(
                AddressPlate.id == plate_id,
                AddressPlate.property_id == property_id,
            )
        ).one()
        lifecycle_history = tuple(
            tuple(row)
            for row in session.execute(
                select(
                    AddressPlateLifecycleEvent.id,
                    AddressPlateLifecycleEvent.event_type,
                    AddressPlateLifecycleEvent.performed_by,
                    AddressPlateLifecycleEvent.occurred_at,
                    AddressPlateLifecycleEvent.notes,
                    AddressPlateLifecycleEvent.created_at,
                )
                .where(AddressPlateLifecycleEvent.plate_id == plate_id)
                .order_by(
                    AddressPlateLifecycleEvent.occurred_at.asc(),
                    AddressPlateLifecycleEvent.id.asc(),
                )
            ).all()
        )
        return (
            property_status,
            plate_status,
            activated_at,
            lifecycle_history,
        )

    try:
        landlord_user = User(
            id=landlord_user_id,
            email=f"activation-rollback-owner-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="landlord",
            is_active=True,
        )
        employee_user = User(
            id=employee_user_id,
            email=f"activation-rollback-employee-{uuid.uuid4()}@example.com",
            password_hash="test-hash",
            role="employee",
            is_active=True,
        )
        db_session.add_all([landlord_user, employee_user])
        db_session.flush()

        landlord = Landlord(
            user_id=landlord_user.id,
            display_name="Activation Rollback Landlord",
            phone="+254700000000",
            landlord_type="individual",
        )
        db_session.add(landlord)
        db_session.flush()

        property = Property(
            id=property_id,
            landlord_id=landlord.id,
            property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
            name="Activation Rollback Property",
            property_type="residential",
            status="verified",
        )
        db_session.add(property)
        db_session.flush()

        db_session.add(
            PropertyAddress(
                property_id=property.id,
                formatted_address="Activation Rollback Address",
                county="Nairobi",
                locality="Nairobi",
            )
        )
        plate = AddressPlate(
            property_id=property.id,
            plate_code=f"PLATE-{uuid.uuid4().hex[:12].upper()}",
            status="unactivated",
        )
        db_session.add(plate)
        db_session.flush()

        employee_record = Employee(
            user_id=employee_user.id,
            employee_number=f"NEST-TEST-{uuid.uuid4().hex[:12].upper()}",
            department="Operations",
            position="Test Employee",
        )
        db_session.add(employee_record)
        db_session.flush()
        db_session.add(
            EmployeeClearance(
                employee_id=employee_record.id,
                clearance="plate_operations",
                is_active=True,
            )
        )

        now = datetime.now(UTC)
        for offset, event_type in enumerate(
            ("manufactured", "allocated", "dispatched", "installed", "verified")
        ):
            db_session.add(
                AddressPlateLifecycleEvent(
                    plate_id=plate.id,
                    event_type=event_type,
                    performed_by=employee_user.id,
                    occurred_at=now + timedelta(seconds=offset),
                )
            )

        _add_verified_activation_evidence(
            db_session,
            property,
            plate,
            installer_id=employee_user.id,
            verified_by=employee_user.id,
        )
        _add_approved_property_location(
            db_session,
            property.id,
            verified_by=employee_user.id,
        )
        PropertyAccessService(db_session).grant_access(
            user_id=employee_user.id,
            property_id=property.id,
            access_type="plate_operations",
        )
        db_session.commit()

        plate_id = plate.id
        token = create_access_token(subject=str(employee_user.id))

        baseline_session = db_session_module.SessionLocal()
        try:
            baseline = snapshot_activation_state(baseline_session, plate_id)
        finally:
            baseline_session.rollback()
            baseline_session.close()

        assert baseline[0] == "verified"
        assert baseline[1] == "unactivated"
        assert baseline[2] is None
        assert all(row[1] != "activated" for row in baseline[3])

        assert get_db not in app.dependency_overrides

        listener_observations = []
        injected_failures = []
        original_session_factory = db_session_module.SessionLocal

        def instrumented_session_factory():
            request_db = original_session_factory()

            def fail_before_commit(session):
                property_status = session.scalar(
                    select(Property.status).where(
                        Property.id == property_id
                    )
                )
                plate_status, activated_at = session.execute(
                    select(AddressPlate.status, AddressPlate.activated_at).where(
                        AddressPlate.id == plate_id,
                        AddressPlate.property_id == property_id,
                    )
                ).one()
                activation_event_count = session.scalar(
                    select(func.count())
                    .select_from(AddressPlateLifecycleEvent)
                    .join(
                        AddressPlate,
                        AddressPlate.id
                        == AddressPlateLifecycleEvent.plate_id,
                    )
                    .where(
                        AddressPlateLifecycleEvent.plate_id == plate_id,
                        AddressPlate.id == plate_id,
                        AddressPlate.property_id == property_id,
                        AddressPlateLifecycleEvent.event_type == "activated",
                    )
                )
                observed = (
                    property_status,
                    plate_status,
                    activated_at is not None,
                    activation_event_count,
                )
                listener_observations.append(observed)

                if observed == ("active", "active", True, 1):
                    injected_failures.append(observed)
                    raise ActivationCommitFailure(
                        "simulated activation request commit failure"
                    )

            event.listen(request_db, "before_commit", fail_before_commit)
            request_sessions.append((request_db, fail_before_commit))
            return request_db

        try:
            with monkeypatch.context() as request_patch:
                request_patch.setattr(
                    db_session_module,
                    "SessionLocal",
                    instrumented_session_factory,
                )
                response = TestClient(
                    app,
                    raise_server_exceptions=False,
                ).post(
                    f"/api/v1/properties/{property_id}/activate",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"plate_code": plate.plate_code},
                )
        finally:
            for request_db, listener in request_sessions:
                if event.contains(request_db, "before_commit", listener):
                    event.remove(request_db, "before_commit", listener)

        verification_session = db_session_module.SessionLocal()
        try:
            after_request = snapshot_activation_state(
                verification_session,
                plate_id,
            )
        finally:
            verification_session.rollback()
            verification_session.close()

        assert response.status_code == 500, response.text
        assert listener_observations == [("active", "active", True, 1)]
        assert injected_failures == [("active", "active", True, 1)]
        assert after_request == baseline
        assert all(row[1] != "activated" for row in after_request[3])
    finally:
        db_session.rollback()
        cleanup_session = db_session_module.SessionLocal()
        try:
            cleanup_installation_test_context(
                cleanup_session,
                property_id,
                test_user_ids,
            )
        except Exception:
            cleanup_session.rollback()
            raise
        finally:
            cleanup_session.close()
