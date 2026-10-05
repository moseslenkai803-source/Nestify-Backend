from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_clearance
from app.db.session import get_db
from app.models.user import User
from app.schemas.address_plate import PlateInventoryResponse
from app.services.plate_inventory_query_service import (
    PlateInventoryQueryService,
)


router = APIRouter(
    prefix="/plate-inventory",
    tags=["Plate Inventory"],
)


@router.get(
    "",
    response_model=list[PlateInventoryResponse],
)
def list_plate_inventory(
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = PlateInventoryQueryService(db)

    return service.list_inventory()
