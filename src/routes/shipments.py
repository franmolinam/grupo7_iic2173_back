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
from src.models.payment import Payment
from src.models.package import Package
from src.services.shipment_service import get_quotation
from src.services.jobs_master_service import check_heartbeat
from src.routes.config import get_fprice

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
    insured: bool = False
    priority_class: str = "medium"

    @field_validator("priority_class")
    @classmethod
    def priority_class_valido(cls, v):
        if v not in ("low", "medium", "high"):
            raise ValueError("priority_class debe ser 'low', 'medium' o 'high'")
        return v

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
    #payload = {"sub": "test-user"}  # para probar
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
            fprice=get_fprice(db),
            insured=body.insured,
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
        is_insured=body.insured,
        fprice=quotation["fprice"],
        route_metric_cost=quotation["route_metric_cost"],
        hops_count=quotation["hops_count"],
        next_hop=quotation["next_hop"],
        full_path=quotation["full_path"],
        final_price=quotation["final_price"],
        status="quoted",
        priority_class=body.priority_class,
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
        "is_insured": shipment.is_insured,
        "insurance_premium": quotation.get("insurance_premium", 0),
        "priority_class": shipment.priority_class,
        "created_at": shipment.created_at,
    }


# RF05: vista de envíos del usuario autenticado
@router.get("/my-shipments")
def my_shipments(
    db: Session = Depends(get_db),
    payload: dict = Depends(validate_token),
    #payload = {"sub": "test-user"}, # probar
):
    user_id = payload.get("sub")

    shipments = (
        db.query(ShipmentRequest)
        .filter_by(user_id=user_id)
        .order_by(ShipmentRequest.created_at.desc())
        .all()
    )

    result = []
    for s in shipments:
        # último pago asociado (puede haber reintentos fallidos)
        payment = (
            db.query(Payment)
            .filter_by(shipment_request_id=s.id)
            .order_by(Payment.created_at.desc())
            .first()
        )
        # paquete creado post-pago (si existe)
        package = db.query(Package).filter_by(shipment_request_id=s.id).first()

        result.append({
            "id": s.id,
            "status": s.status,
            "origin_id": s.origin_id,
            "destination_id": s.destination_id,
            "criteria": s.criteria,
            "max_hops": s.max_hops,
            "hops_count": s.hops_count,
            "next_hop": s.next_hop,
            "full_path": s.full_path,
            "route_metric_cost": s.route_metric_cost,
            "fprice": s.fprice,
            "final_price": s.final_price,
            "is_insured": s.is_insured,
            "deliver_not_before": s.deliver_not_before,
            "meta_content": s.meta_content,
            "created_at": s.created_at,
            "payment": {
                "id": payment.id,
                "status": payment.status,
                "amount": payment.amount,
                "currency": payment.currency,
                "authorization_code": payment.authorization_code,
                "created_at": payment.created_at,
                "updated_at": payment.updated_at,
            } if payment else None,
            "package": {
                "id": package.id,
                "status": package.status,
                "last_action": package.last_action,
            } if package else None,
        })

    return result

# indica si el JobsMaster está operativo (para monitoreo desde el frontend)
@router.get("/jobs/heartbeat")
def jobs_heartbeat():
    alive = check_heartbeat()
    return {"alive": alive, "jobs_master_url": os.getenv("JOBS_MASTER_URL")}