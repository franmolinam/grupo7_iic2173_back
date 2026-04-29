from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
import uuid

from src.models.package import Package
from src.models.package_event import PackageEvent
from src.models.city_connection import CityConnection


# --- Funciones de Package ---

def get_all_packages(db: Session, skip: int = 0, limit: int = 100):
    """Retorna todos los paquetes recibidos por LSN."""
    return db.query(Package).offset(skip).limit(limit).all()


def get_package_by_id(db: Session, package_id: str) -> Optional[Package]:
    """Retorna un paquete por su id."""
    return db.query(Package).filter(Package.id == package_id).first()

def _parse_datetime(value):
    """Convierte un string ISO 8601 a datetime si es necesario."""
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def save_package(db: Session, package_data: dict) -> Package:
    """
    Guarda un paquete nuevo. Si ya existe (idempotencia), retorna el existente.
    """
    existing = get_package_by_id(db, package_data["id"])
    if existing:
        return existing

    pkg = Package(
        id=package_data["id"],
        origin_id=package_data.get("originId", ""),
        destination_id=package_data.get("destinationId", ""),
        max_hops=package_data.get("maxHops", 0),
        created_at=_parse_datetime(package_data.get("createdAt")),
        deliver_not_before=_parse_datetime(package_data.get("deliverNotBefore")),
        meta_content=package_data.get("metaContent"),
        is_meta_encrypted=package_data.get("isMetaEncrypted", False),
        priority_class=package_data.get("priorityClass"),
        payment=package_data.get("payment"),
        constraints=package_data.get("constraints", {}),
        delivery_strategy=package_data.get("deliveryStrategy"),
        status="received",
        last_action="received",
        last_processed_at=datetime.now(timezone.utc),
        received_from=package_data.get("receivedFrom"),
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


def update_package_status(db: Session, package_id: str, status: str, last_action: str, next_city_id: str = None) -> Optional[Package]:
    """Actualiza el estado de un paquete y registra el evento."""
    pkg = get_package_by_id(db, package_id)
    if not pkg:
        return None

    pkg.status = status
    pkg.last_action = last_action
    pkg.last_processed_at = datetime.now(timezone.utc)
    db.commit()

    # Registrar evento
    event = PackageEvent(
        id=str(uuid.uuid4()),
        package_id=package_id,
        event_type=last_action,
        next_city_id=next_city_id,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    db.refresh(pkg)
    return pkg


def deliver_package(db: Session, package_id: str) -> tuple[Optional[Package], str]:
    """
    Intenta entregar un paquete.
    Retorna (paquete, mensaje).
    """
    pkg = get_package_by_id(db, package_id)
    if not pkg:
        return None, "Package not found"

    if pkg.status == "delivered":
        return pkg, "Package already delivered"

    now = datetime.now(timezone.utc)
    
    # Verificar deliverNotBefore
    deliver_not_before = pkg.deliver_not_before
    if deliver_not_before.tzinfo is None:
        deliver_not_before = deliver_not_before.replace(tzinfo=timezone.utc)

    if now < deliver_not_before:
        return pkg, f"Package cannot be delivered before {deliver_not_before.isoformat()}"

    return update_package_status(db, package_id, "delivered", "delivered"), "Package delivered successfully"


# --- Funciones de CityConnection ---

def get_all_connections(db: Session):
    """Retorna todas las conexiones de ciudades."""
    return db.query(CityConnection).all()


def upsert_connections(db: Session, distances: dict):
    """
    Actualiza o inserta las conexiones de ciudades
    a partir de la tabla de distancias del broker.
    """
    for city_code, data in distances.items():
        existing = db.query(CityConnection).filter_by(destination_code=city_code).first()
        if existing:
            existing.destination_name = data.get("destinationName", city_code)
            existing.distance = data.get("distance")
            existing.transport_cost = data.get("transportCost")
            existing.enabled = data.get("enabled", False)
        else:
            conn = CityConnection(
                destination_code=city_code,
                destination_name=data.get("destinationName", city_code),
                distance=data.get("distance"),
                transport_cost=data.get("transportCost"),
                enabled=data.get("enabled", False),
            )
            db.add(conn)
    db.commit()