from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from src.database import get_db
from src.services.package_service import (
    get_all_packages,
    get_package_by_id,
)
from src.handlers.package_handler import handle_package_delivered

router = APIRouter(prefix="/packages", tags=["packages"])


@router.get("/")
def list_packages(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    origin_id: Optional[str] = None,
    destination_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    RF01: Lista todos los paquetes recibidos por LSN.
    Permite filtrar por status, origen y destino.
    """
    from src.models.package import Package
    query = db.query(Package)

    if status:
        query = query.filter(Package.status == status)
    if origin_id:
        query = query.filter(Package.origin_id == origin_id)
    if destination_id:
        query = query.filter(Package.destination_id == destination_id)

    packages = query.offset(skip).limit(limit).all()

    return {
        "total": len(packages),
        "packages": [
            {
                "id": p.id,
                "origin_id": p.origin_id,
                "destination_id": p.destination_id,
                "max_hops": p.max_hops,
                "created_at": p.created_at,
                "deliver_not_before": p.deliver_not_before,
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