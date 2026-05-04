from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, func
from typing import Optional
from src.database import get_db
from src.services.package_service import (
    get_all_packages,
    get_package_by_id,
)
from src.handlers.package_handler import handle_package_delivered

router = APIRouter(prefix="/packages", tags=["packages"])


@router.get("")
def list_packages(
    page: int = 1,
    limit: int = 25,
    status: Optional[str] = None,
    origin_id: Optional[str] = None,
    destination_id: Optional[str] = None,
    max_hops: Optional[int] = None,
    created_at: Optional[str] = None,
    deliver_not_before: Optional[str] = None,
    delivery_strategy: Optional[str] = None,
    meta_content: Optional[str] = None,
    is_meta_encrypted: Optional[bool] = None,
    priority_class: Optional[str] = None,
    payment: Optional[int] = None,
    constraints: Optional[dict] = None,
    db: Session = Depends(get_db)
):
    """
    RF01: Lista todos los paquetes recibidos por LSN.
    Permite filtrar por status, origen y destino.
    """
    from src.models.package import Package
    skip = (page - 1) * limit
    query = db.query(Package)

    if payment is not None:
        query = query.filter(Package.payment == payment)
    if priority_class:
        query = query.filter(Package.priority_class == priority_class)
    if created_at:
        query = query.filter(func.date(Package.created_at) == created_at)
    if max_hops:
        query = query.filter(Package.max_hops == max_hops)
    if deliver_not_before:
        query = query.filter(func.date(Package.deliver_not_before) == deliver_not_before)
    if delivery_strategy:
        query = query.filter(Package.delivery_strategy == delivery_strategy)
    if status:
        query = query.filter(Package.status == status)
    if origin_id:
        query = query.filter(Package.origin_id == origin_id)
    if destination_id:
        query = query.filter(Package.destination_id == destination_id)
    if constraints:
        query = query.filter(Package.constraints.contains(constraints))

    packages = query.offset(skip).limit(limit).all()

    return {
        "total": len(packages),
        "packages": [
            {
                "id": p.id,
                "delivery_strategy": p.delivery_strategy,
                "origin_id": p.origin_id,
                "destination_id": p.destination_id,
                "max_hops": p.max_hops,
                "created_at": p.created_at,
                "deliver_not_before": p.deliver_not_before,
                "meta_content": p.meta_content,
                "is_meta_encrypted": p.is_meta_encrypted,
                "priority_class": p.priority_class,
                "payment": p.payment,
                "status": p.status,
                "last_action": p.last_action,
                "last_processed_at": p.last_processed_at,
            }
            for p in packages
        ]
    }


@router.get("/{package_id}")
def get_package(package_id: str, db: Session = Depends(get_db)):
    """Retorna el detalle de un paquete específico."""
    pkg = get_package_by_id(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


@router.post("/{package_id}/deliver")
def deliver_package(package_id: str, db: Session = Depends(get_db)):
    """
    RF04: Concreta la entrega de un paquete.
    Valida deliverNotBefore e idempotencia.
    """
    pkg, msg = handle_package_delivered(db, package_id)

    if pkg is None:
        raise HTTPException(status_code=404, detail=msg)

    if "already delivered" in msg:        
        raise HTTPException(status_code=400, detail=msg)
    
    if pkg.status != "delivered":
        raise HTTPException(status_code=400, detail=msg)

    return {"message": msg, "package": {
        "id": pkg.id,
        "status": pkg.status,
        "last_action": pkg.last_action,
        "last_processed_at": pkg.last_processed_at,
    }}