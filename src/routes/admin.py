from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth_utils import require_admin
from src.database import get_db

from src.models.package import Package
from src.models.payment import Payment
from src.models.routing_jobs import RoutingJob
from src.models.shipment_request import ShipmentRequest

router = APIRouter(prefix="/admin",tags=["admin"])

@router.get("/jobs")
def get_jobs(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin)
):
    jobs = db.query(RoutingJob).all()

    return [
        {
            "id": job.id,
            "status": job.status,
            "criteria": job.criteria,
            "origin": job.origin,
            "destination": job.destination,
            "route_metric_cost": job.route_metric_cost,
            "hop_count": job.hop_count,
            "hops": job.hops,
        }
        for job in jobs
    ]    

@router.get("/routes")
def get_routes(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin)
):
    shipments = (
    db.query(ShipmentRequest)
    .filter(ShipmentRequest.full_path.isnot(None))
    .all()
)

    return [
        {
            "shipment_id": s.id,
            "origin": s.origin_id,
            "destination": s.destination_id,
            "criteria": s.criteria,
            "route_metric_cost": s.route_metric_cost,
            "hops_count": s.hops_count,
            "next_hop": s.next_hop,
            "full_path": s.full_path,
            "status": s.status,
        }
        for s in shipments
    ]
    
@router.get("/packages")
def get_packages(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin)
):
    packages = db.query(Package).all()

    return [
        {
            "id": p.id,
            "origin_id": p.origin_id,
            "destination_id": p.destination_id,
            "status": p.status,
            "last_action": p.last_action,
            "last_processed_at": p.last_processed_at,
            "received_from": p.received_from,
        }
        for p in packages
    ]
    
@router.get("/payments")
def get_payments(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin)
):
    payments = db.query(Payment).all()

    return [
        {
            "id": p.id,
            "status": p.status,
            "amount": p.amount,
            "currency": p.currency,
            "user_id": p.user_id,
            "shipment_request_id": p.shipment_request_id,
        }
        for p in payments
    ]
