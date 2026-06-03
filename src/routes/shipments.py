from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
import uuid
import os

from src.database import get_db
from src.auth_utils import validate_token
from src.models.shipment_request import ShipmentRequest
from src.services.shipment_service import get_quotation

router = APIRouter(prefix="/shipments", tags=["shipments"])

FPRICE_DEFAULT = float(os.getenv("FPRICE", "1.0"))


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
        if v not in ("price", "distance"):
            raise ValueError("criteria debe ser 'price' o 'distance'")
        return v

    @field_validator("height", "width", "depth")
    @classmethod
    def dimensiones_positivas(cls, v):
        if v <= 0:
            raise ValueError("Las dimensiones deben ser positivas")
        return v


@router.post("", status_code=201)
def create_shipment(
    body: ShipmentRequestCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(validate_token),
):
    user_id = payload.get("sub")

    # Validar + cotizar
    try:
        quotation = get_quotation(
            destination_id=body.destination_id,
            height=body.height,
            width=body.width,
            depth=body.depth,
            criteria=body.criteria,
            max_hops=body.max_hops,
            fprice=FPRICE_DEFAULT,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Guardar en BD con los datos de la cotización
    shipment = ShipmentRequest(
        id=str(uuid.uuid4()),
        user_id=user_id,
        origin_id=str(os.getenv("CODIGO_CIUDAD")),
        destination_id=body.destination_id.upper(),
        height=body.height,
        width=body.width,
        depth=body.depth,
        criteria=body.criteria,
        max_hops=body.max_hops,
        deliver_not_before=body.deliver_not_before,
        meta_content=body.meta_content,
        fprice=quotation["fprice"],
        route_metric_cost=quotation["route_metric_cost"],
        hops_count=quotation["hops_count"],
        next_hop=quotation["next_hop"],
        full_path=quotation["full_path"],
        final_price=quotation["final_price"],
        status="quoted",
    )

    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    return {
        "id": shipment.id,
        "status": shipment.status,
        "destination_id": shipment.destination_id,
        "criteria": shipment.criteria,
        "route_metric_cost": shipment.route_metric_cost,
        "hops_count": shipment.hops_count,
        "next_hop": shipment.next_hop,
        "full_path": shipment.full_path,
        "fprice": shipment.fprice,
        "final_price": shipment.final_price,
        "created_at": shipment.created_at,
    }