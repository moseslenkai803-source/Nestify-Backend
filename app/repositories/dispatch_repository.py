from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dispatch import Dispatch


class DispatchRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        dispatch: Dispatch,
    ) -> Dispatch:
        self.db.add(dispatch)
        self.db.flush()

        return dispatch

    def get_by_id(
        self,
        dispatch_id: UUID,
    ) -> Dispatch | None:
        return self.db.get(
            Dispatch,
            dispatch_id,
        )

    def get_by_dispatch_code(
        self,
        dispatch_code: str,
    ) -> Dispatch | None:
        return (
            self.db.query(Dispatch)
            .filter(
                Dispatch.dispatch_code == dispatch_code,
            )
            .first()
        )

    def get_by_dispatch_code_for_update(
        self,
        dispatch_code: str,
    ) -> Dispatch | None:
        statement = (
            select(Dispatch)
            .where(Dispatch.dispatch_code == dispatch_code)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_by_status(
        self,
        status: str,
    ) -> list[Dispatch]:
        return (
            self.db.query(Dispatch)
            .filter(
                Dispatch.status == status,
            )
            .order_by(
                Dispatch.created_at.desc(),
            )
            .all()
        )
