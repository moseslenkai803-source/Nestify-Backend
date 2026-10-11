import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_invitation import EmployeeInvitation
from app.models.user import User
from app.repositories.employee_invitation_repository import (
    EmployeeInvitationRepository,
)
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.user_repository import UserRepository
from app.core.employee_clearances import validate_employee_clearance
from app.services.employee_service import EmployeeService
from app.services.user_service import UserService


class EmployeeInvitationService:
    INVITATION_LIFETIME = timedelta(hours=24)

    def __init__(self, db: Session):
        self.db = db
        self.invitation_repository = EmployeeInvitationRepository(db)
        self.employee_repository = EmployeeRepository(db)
        self.user_repository = UserRepository(db)
        self.user_service = UserService(db)
        self.employee_service = EmployeeService(db)

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _lock_invitation_identifiers(
        self,
        *,
        email: str,
        employee_number: str,
    ) -> None:
        identifiers = sorted(
            (f"employee-invitation:email:{email}",
             f"employee-invitation:number:{employee_number}")
        )
        for identifier in identifiers:
            lock_key = int.from_bytes(
                hashlib.sha256(identifier.encode("utf-8")).digest()[:8],
                byteorder="big",
                signed=True,
            )
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": lock_key},
            )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def create_invitation(
        self,
        *,
        email: str,
        employee_number: str,
        department: str,
        position: str,
        clearances: list[str],
        invited_by_user_id,
    ) -> tuple[EmployeeInvitation, str]:
        normalized_email = self._normalize_email(email)
        employee_number = employee_number.strip()
        department = department.strip()
        position = position.strip()

        if not normalized_email:
            raise ValueError("Email is required")
        if not employee_number:
            raise ValueError("Employee number is required")
        if not department:
            raise ValueError("Department is required")
        if not position:
            raise ValueError("Position is required")

        self._lock_invitation_identifiers(
            email=normalized_email,
            employee_number=employee_number,
        )

        if self.user_repository.get_by_email(normalized_email):
            raise ValueError("A user with this email already exists")

        if self.employee_repository.get_by_employee_number(employee_number):
            raise ValueError("Employee number already exists")

        now = self._utc_now()
        active_email_invitation = self.db.scalar(
            select(EmployeeInvitation.id).where(
                EmployeeInvitation.email == normalized_email,
                EmployeeInvitation.redeemed_at.is_(None),
                EmployeeInvitation.expires_at > now,
            )
        )
        if active_email_invitation is not None:
            raise ValueError("An active invitation already exists for this email")

        active_number_invitation = self.db.scalar(
            select(EmployeeInvitation.id).where(
                EmployeeInvitation.employee_number == employee_number,
                EmployeeInvitation.redeemed_at.is_(None),
                EmployeeInvitation.expires_at > now,
            )
        )
        if active_number_invitation is not None:
            raise ValueError(
                "An active invitation already exists for this employee number"
            )

        normalized_clearances = []
        for clearance in clearances:
            value = clearance.strip()
            if not value:
                raise ValueError("Clearance cannot be empty")
            value = validate_employee_clearance(value)
            if value not in normalized_clearances:
                normalized_clearances.append(value)

        token = secrets.token_urlsafe(32)
        invitation = EmployeeInvitation(
            email=normalized_email,
            token_hash=self._hash_token(token),
            employee_number=employee_number,
            department=department,
            position=position,
            clearances=normalized_clearances,
            invited_by_user_id=invited_by_user_id,
            expires_at=now + self.INVITATION_LIFETIME,
        )
        self.invitation_repository.add(invitation)
        return invitation, token

    def accept_invitation(
        self,
        *,
        token: str,
        password: str,
    ) -> tuple[User, Employee]:
        token_hash = self._hash_token(token)
        invitation = self.invitation_repository.get_by_token_hash_for_update(
            token_hash
        )

        if invitation is None:
            raise ValueError("Invitation is invalid or has expired")

        if invitation.redeemed_at is not None:
            raise ValueError("Invitation has already been used")

        now = self._utc_now()
        if self._as_utc(invitation.expires_at) <= now:
            raise ValueError("Invitation is invalid or has expired")

        email = self._normalize_email(invitation.email)
        if self.user_repository.get_by_email(email):
            raise ValueError("A user with this email already exists")

        user = self.user_service.create_user(
            email=email,
            password=password,
            role="employee",
        )
        employee = self.employee_service.create_employee(
            user_id=user.id,
            employee_number=invitation.employee_number,
            department=invitation.department,
            position=invitation.position,
            clearances=invitation.clearances,
        )

        invitation.redeemed_at = now
        self.db.flush()
        return user, employee
