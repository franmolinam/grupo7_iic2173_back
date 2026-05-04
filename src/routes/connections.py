from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.database import get_db
from src.services.package_service import get_all_connections

# Router para los endpoints de conexiones entre ciudades
router = APIRouter(prefix="/connections", tags=["connections"])

# listar estado conexiones entre ciudades
@router.get("")
def list_connections(db: Session = Depends(get_db)):
    # listar todas las conexiones entre ciudades  (deberían ser las 16 q hay)
    connections = get_all_connections(db)
    return {
        "total": len(connections),
        "connections": [
            {
                "destination_code": c.destination_code,
                "destination_name": c.destination_name,
                "distance": c.distance,
                "transport_cost": c.transport_cost,
                "enabled": c.enabled,
            }
            for c in connections
        ]
    }