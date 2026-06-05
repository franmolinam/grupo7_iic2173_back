from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
import uuid

from src.models.package import Package
from src.models.package_event import PackageEvent
from src.models.city_connection import CityConnection


# Funciones de Package

# Obtener todos los paquetes de LSN
# puse los 100 primeros para no saturar la memoria, dsp voy a paginar
def get_all_packages(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Package).offset(skip).limit(limit).all()

# Obtener un paquete por su id para el RF de packages/id
def get_package_by_id(db: Session, package_id: str) -> Optional[Package]:
    return db.query(Package).filter(Package.id == package_id).first()

# Para los string ISO a datetime (fechas en createdAt y deliverNotBefore)
def _parse_datetime(value):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value

# Guarda un paquete nuevo y si ya existe, retorna ese
def save_package(db: Session, package_data: dict) -> Package:
    existing = get_package_by_id(db, package_data["id"])
    if existing:
        return existing

    # todos los campos que vienen en el paquete, más los campos de seguimiento que cree
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
    # guardo el paquete en la base de datos
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg

# Actualizar el estado del paquete y registrar un evento cada vez que se procesa o se hace alguna acción sobre el
def update_package_status(db: Session, package_id: str, status: str, last_action: str, next_city_id: str = None) -> Optional[Package]:
    pkg = get_package_by_id(db, package_id)
    # si el paquete no existe, retorno None
    if not pkg:
        return None

    # actualizo el estado del paquete
    pkg.status = status
    pkg.last_action = last_action
    pkg.last_processed_at = datetime.now(timezone.utc)
    db.commit()

    # registrar evento
    event = PackageEvent(
        id=str(uuid.uuid4()),
        package_id=package_id,
        event_type=last_action,
        next_city_id=next_city_id,
        timestamp=datetime.now(timezone.utc),
    )
    # guardar bbdd
    db.add(event)
    db.commit()

    # actualizar el paquete para que tenga el nuevo estado y el evento asociado
    db.refresh(pkg)
    return pkg

# Para entregar un paquete /deliver
def deliver_package(db: Session, package_id: str) -> tuple[Optional[Package], str]:
    # lo busco en la base de datos con su id
    pkg = get_package_by_id(db, package_id)
    # si no existe, retorno None y un mensaje de error
    if not pkg:
        return None, "Package not found"

    # si ya está entregado, no hago nada y retorno un mensaje de que ya fue entregado
    if pkg.status == "delivered":
        return pkg, "Package already delivered"

    # veo que no esté expirado con deliverNotBefore
    now = datetime.now(timezone.utc)
    deliver_not_before = pkg.deliver_not_before
    # manejo de errores por si la fecha no es válida o no tiene tzinfo, asumo que es UTC
    if deliver_not_before.tzinfo is None:
        deliver_not_before = deliver_not_before.replace(tzinfo=timezone.utc)

    # entonces: si la fecha actual es menor a deliverNotBefore, no puedo entregar el paquete
    if now < deliver_not_before:
        return pkg, f"Package cannot be delivered before {deliver_not_before.isoformat()}"

    # si todo esta bien (para delivery y en fecha), actualizo el estado del paquete a delivered y registro un evento de entrega
    return update_package_status(db, package_id, "delivered", "delivered"), "Package delivered successfully"


# Funciones para city connections

# Obtener todas las conexiones de ciudades para el RF de connections
def get_all_connections(db: Session):
    return db.query(CityConnection).all()

# Actualizar o insertar las conexiones de ciudades a partir de la tabla de distancias del broker
def upsert_connections(db: Session, source_code: str,distances: dict):
    # recorro las conexiones que me manda el broker por cada ciudad
    for city_code, data in distances.items():
        # reviso si ya existe una conexión para esa ciudad
        existing = db.query(CityConnection).filter_by(
            source_code=source_code,
            destination_code=city_code).first()
        if existing:
            # en este caso la actualizo con los nuevos datos que me manda el broker
            existing.destination_name = data.get("destinationName", city_code)
            existing.distance = data.get("distance")
            existing.transport_cost = data.get("transportCost")
            existing.enabled = data.get("enabled", False)
        # si no la creo
        else:
            conn = CityConnection(
                source_code=source_code,
                destination_code=city_code,
                destination_name=data.get("destinationName", city_code),
                distance=data.get("distance"),
                transport_cost=data.get("transportCost"),
                enabled=data.get("enabled", False),
            )
            # guardo la nueva conexión en la BDD
            db.add(conn)
    db.commit()