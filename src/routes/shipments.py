from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
import uuid

from src.database import get_db
from src.auth_utils import validate_token
from src.models.shipment_request import ShipmentRequest

router = APIRouter(prefix="/shipments", tags=["shipments"])


class ShipmentRequestCreate(BaseModel):
    destination_id: str
    height: float
    width: float
    depth: float
    criteria: str
    max_hops: int
    deliver_not_before: Optional[datetime] = None
    meta_content: Optional[str] = None

    @field_validator("criteria")
    @classmethod
    def criteria_valido(cls, v):
        # valida q criteria sea válido
        if v not in ("price", "distance"):
            raise ValueError("criteria debe ser 'price' o 'distance'")
        return v

    @field_validator("height", "width", "depth")
    @classmethod
    def dimensiones_positivas(cls, v):
        # que las dimensiones sean positivas
        if v <= 0:
            raise ValueError("Las dimensiones deben ser positivas")
        return v
    
    # falta RF01 (dimensiones máx 3000, alcanzabilidad y maxHops)


@router.post("", status_code=201)
def create_shipment(
    body: ShipmentRequestCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(validate_token),
):
    user_id = payload.get("sub")

    shipment = ShipmentRequest(
        id=str(uuid.uuid4()),
        user_id=user_id,
        origin_id=str(__import__("os").getenv("CODIGO_CIUDAD")),
        destination_id=body.destination_id.upper(),
        height=body.height,
        width=body.width,
        depth=body.depth,
        criteria=body.criteria,
        max_hops=body.max_hops,
        deliver_not_before=body.deliver_not_before,
        meta_content=body.meta_content,
        status="pending_quote",
    )

    # guarda en db
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    return {
        "id": shipment.id,
        "status": shipment.status,
        "destination_id": shipment.destination_id,
        "created_at": shipment.created_at,
    }