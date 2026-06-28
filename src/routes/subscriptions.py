from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

from src.database import get_db
from src.auth_utils import validate_token
from src.services.subscription_service import (
    create_subscription,
    get_user_subscriptions,
    get_subscription_detail,
    get_subscription_packages,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class SubscriptionCreate(BaseModel):
    # Parametros del paquete
    destination_id: str
    height: float
    width: float
    depth: float
    criteria: str
    max_hops: int
    deliver_not_before: Optional[datetime] = None
    meta_content: Optional[str] = None

    # Configuración de la suscripcion
    periodicity_seconds: int   # 1 min a 2 dias
    budget: float              # Prepago
    cost_per_shipment: float   # Costo por cada envio
    quantity: int              # Max 100

    @field_validator("criteria")
    @classmethod
    def criteria_valido(cls, v):
        if v not in ("price", "distance"):
            raise ValueError("criteria debe ser 'price' o 'distance'")
        return v

    @field_validator("periodicity_seconds")
    @classmethod
    def periodicidad_valida(cls, v):
        if v < 60 or v > 172800:
            raise ValueError("periodicity_seconds debe estar entre 60 (1 min) y 172800 (2 días)")
        return v

    @field_validator("quantity")
    @classmethod
    def cantidad_valida(cls, v):
        if v < 1 or v > 100:
            raise ValueError("quantity debe estar entre 1 y 100")
        return v

    @field_validator("height", "width", "depth")
    @classmethod
    def dimensiones_positivas(cls, v):
        if v <= 0:
            raise ValueError("Las dimensiones deben ser positivas")
        return v

    @field_validator("budget", "cost_per_shipment")
    @classmethod
    def montos_positivos(cls, v):
        if v <= 0:
            raise ValueError("Los montos deben ser positivos")
        return v


def _format_subscription(s) -> dict:
    return {
        "id": s.id,
        "status": s.status,
        "destination_id": s.destination_id,
        "criteria": s.criteria,
        "max_hops": s.max_hops,
        "height": s.height,
        "width": s.width,
        "depth": s.depth,
        "meta_content": s.meta_content,
        "deliver_not_before": s.deliver_not_before,
        "periodicity_seconds": s.periodicity_seconds,
        "budget": s.budget,
        "budget_remaining": s.budget_remaining,
        "cost_per_shipment": s.cost_per_shipment,
        "quantity": s.quantity,
        "packages_sent": s.packages_sent,
        "execution_arn": s.execution_arn,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


@router.post("", status_code=201)
def crear_suscripcion(
    body: SubscriptionCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(validate_token),
):
    user_id = payload.get("sub")

    if body.height + body.width + body.depth > 3000:
        raise HTTPException(status_code=400, detail="Las dimensiones superan los 3000 cm lineales")

    if body.cost_per_shipment > body.budget:
        raise HTTPException(status_code=400, detail="cost_per_shipment no puede superar el budget total")

    try:
        sub = create_subscription(db, user_id, body.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return _format_subscription(sub)


@router.get("")
def listar_suscripciones(
    db: Session = Depends(get_db),
    payload: dict = Depends(validate_token),
):
    user_id = payload.get("sub")
    subs = get_user_subscriptions(db, user_id)
    return [_format_subscription(s) for s in subs]


@router.get("/{subscription_id}")
def detalle_suscripcion(
    subscription_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(validate_token),
):
    user_id = payload.get("sub")
    sub = get_subscription_detail(db, subscription_id, user_id)

    if not sub:
        raise HTTPException(status_code=404, detail="Suscripcion no encontrada")

    detail = _format_subscription(sub)
    detail["packages"] = get_subscription_packages(db, subscription_id)
    return detail
