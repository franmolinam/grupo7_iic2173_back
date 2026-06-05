import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from src.database import get_db
from src.auth_utils import validate_token
from src.models.payment import Payment
from src.models.shipment_request import ShipmentRequest
from src.services.webpay_service import create_transaction, commit_transaction
from src.rabbitmq.auditor import enviar_auditoria_pago
from tests.test_handlers import db

router = APIRouter(prefix="", tags=["payments"])

WEBPAY_RETURN_URL = os.getenv("WEBPAY_RETURN_URL", "http://localhost:8000/payments/callback")
CODIGO_CIUDAD = os.getenv("CODIGO_CIUDAD", "LSN").upper()


class CallbackBody(BaseModel):
    token_ws: Optional[str] = None  # None significa que el usuario anuló


# POST /shipments/:id/pay —> inicia el flujo Webpay
@router.post("/shipments/{shipment_id}/pay", status_code=201)
def initiate_payment(
    shipment_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(validate_token),
):
    user_id = payload.get("sub")

    # Buscar el shipment
    shipment = db.query(ShipmentRequest).filter_by(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment no encontrado")

    if shipment.user_id != user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para pagar este shipment")

    if shipment.status != "quoted":
        raise HTTPException(status_code=400, detail=f"El shipment no está en estado 'quoted' (estado actual: {shipment.status})")

    # si ya existe un pago TRYING para este shipment, lo devolvemos
    # Idempotencia — va ANTES del chequeo de status
    existing = db.query(Payment).filter_by(
    shipment_request_id=shipment_id, status="TRYING"
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe un pago en proceso para este shipment")

if shipment.status != "quoted":
    raise HTTPException(status_code=400, detail=f"El shipment no está en estado 'quoted' (estado actual: {shipment.status})")

    # Crear transacción en Webpay
    payment_id = str(uuid.uuid4())
    try:
        webpay_response = create_transaction(payment_id, shipment.final_price, WEBPAY_RETURN_URL)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al crear transacción en Webpay: {e}")

    # Guardar Payment con status TRYING
    payment = Payment(
        id=payment_id,
        shipment_request_id=shipment_id,
        user_id=user_id,
        webpay_token=webpay_response["token"],
        status="TRYING",
        amount=shipment.final_price,
        currency="CLP",
    )
    db.add(payment)

    # Actualizar shipment a "paying"
    shipment.status = "paying"
    db.commit()
    db.refresh(payment)

    # Auditoría TRYING al broker
    try:
        enviar_auditoria_pago(
            payment_id=payment.id,
            pkg_id=shipment_id,
            token=payment.webpay_token,
            status="TRYING",
            amount=payment.amount,
            destination_id=shipment.destination_id,
            criteria=shipment.criteria,
            route_metric_cost=shipment.route_metric_cost,
            max_hops=shipment.max_hops,
        )
    except Exception:
        pass  # No bloquear el flujo si el broker falla

    return {
        "payment_id": payment.id,
        "token": webpay_response["token"],
        "url": webpay_response["url"],
    }


# POST /payments/callback —> Webpay redirige aquí después del pago
@router.post("/payments/callback")
def payment_callback(
    body: CallbackBody,
    db: Session = Depends(get_db),
):
    # Usuario anuló la compra (Webpay no envía token_ws)
    if not body.token_ws:
        return {"status": "CANCELLED", "message": "El usuario anuló la compra"}

    # Buscar el pago por token
    payment = db.query(Payment).filter_by(webpay_token=body.token_ws).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    # Si ya fue procesado, devolvemos el estado actual
    if payment.status in ("SUCCESS", "FAILED"):
        return {"status": payment.status, "payment_id": payment.id}

    # Confirmar con Webpay
    try:
        result = commit_transaction(body.token_ws)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al confirmar transacción: {e}")

    shipment = db.query(ShipmentRequest).filter_by(id=payment.shipment_request_id).first()

    if result["response_code"] == 0:
        # Pago exitoso
        payment.status = "SUCCESS"
        payment.authorization_code = result["authorization_code"]
        payment.updated_at = datetime.now(timezone.utc)
        if shipment:
            shipment.status = "paid"
        db.commit()

        # Auditoría SUCCESS
        try:
            enviar_auditoria_pago(
                payment_id=payment.id,
                pkg_id=payment.shipment_request_id,
                token=payment.webpay_token,
                status="SUCCESS",
                amount=payment.amount,
                destination_id=shipment.destination_id if shipment else None,
                criteria=shipment.criteria if shipment else None,
                authorization_code=result["authorization_code"],
                transaction_date=str(result["transaction_date"]),
            )
        except Exception:
            pass

        return {
            "status": "SUCCESS",
            "payment_id": payment.id,
            "authorization_code": payment.authorization_code,
        }

    else:
        # Pago rechazado
        payment.status = "FAILED"
        payment.updated_at = datetime.now(timezone.utc)
        if shipment:
            shipment.status = "quoted"  # vuelve a quoted para que pueda reintentar
        db.commit()

        # Auditoría FAILED
        try:
            enviar_auditoria_pago(
                payment_id=payment.id,
                pkg_id=payment.shipment_request_id,
                token=payment.webpay_token,
                status="FAILED",
                amount=payment.amount,
                destination_id=shipment.destination_id if shipment else None,
                criteria=shipment.criteria if shipment else None,
                reason="REJECTED",
            )
        except Exception:
            pass

        return {"status": "FAILED", "payment_id": payment.id, "reason": "REJECTED"}