from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
import uuid
import os
import json
import pika
import ssl

from src.models.package import Package
from src.models.package_event import PackageEvent
from src.models.city_connection import CityConnection

CODIGO_CIUDAD = os.getenv("CODIGO_CIUDAD", "LSN").upper()


def _get_rabbitmq_channel():
    credenciales = pika.PlainCredentials(
        os.getenv("RABBITMQ_USER"), os.getenv("RABBITMQ_PASSWORD")
    )
    context = ssl.create_default_context()
    ssl_options = pika.SSLOptions(context)
    parameters = pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST"),
        port=int(os.getenv("RABBITMQ_PORT", 5671)),
        virtual_host="fulfillment",
        credentials=credenciales,
        ssl_options=ssl_options,
        heartbeat=60,
    )
    conexion = pika.BlockingConnection(parameters)
    return conexion, conexion.channel()

# Crea el Package en BD y lo publica al siguiente salto via MQTT. Idempotente: si ya existe paquete para este shipment, lo retorna sin re-enviar.
def create_and_send_package(db: Session, shipment, payment) -> Package:
    existing = db.query(Package).filter_by(shipment_request_id=shipment.id).first()
    if existing:
        return existing

    now = datetime.now(timezone.utc)
    pkg_id = str(uuid.uuid4())

    deliver_not_before = shipment.deliver_not_before or now
    if hasattr(deliver_not_before, 'tzinfo') and deliver_not_before.tzinfo is None:
        deliver_not_before = deliver_not_before.replace(tzinfo=timezone.utc)

    # calcular prima por seguridad
    is_insured = bool(getattr(shipment, "is_insured", False))
    insurance_premium = int(payment.amount * 0.05) if is_insured else None

    pkg = Package(
        id=pkg_id,
        origin_id=shipment.origin_id,
        destination_id=shipment.destination_id,
        max_hops=shipment.max_hops,
        created_at=now,
        deliver_not_before=deliver_not_before,
        meta_content=shipment.meta_content,
        constraints={"criteria": shipment.criteria},
        payment=payment.amount,
        is_insured=is_insured,
        insurance_premium=insurance_premium,
        status="forwarded",
        last_action="forwarded",
        last_processed_at=now,
        shipment_request_id=shipment.id,
        received_from=CODIGO_CIUDAD,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)

    # Publicar al siguiente salto via MQTT
    next_hop = shipment.next_hop or shipment.destination_id
    package_body = {
        "id": pkg.id,
        "originId": pkg.origin_id,
        "destinationId": pkg.destination_id,
        "maxHops": pkg.max_hops - 1,  # descontamos el salto inicial
        "createdAt": now.isoformat(),
        "deliverNotBefore": deliver_not_before.isoformat(),
        "metaContent": {"insured": is_insured} if is_insured else pkg.meta_content,
        "constraints": {"criteria": shipment.criteria},
        "payment": pkg.payment,
    }
    mensaje = {
        "idpk": str(uuid.uuid4()),
        "msgId": str(uuid.uuid4()),
        "type": "package-transit",
        "timestamp": now.isoformat(),
        "cityId": CODIGO_CIUDAD,
        "packageBody": package_body,
    }

    try:
        conexion, channel = _get_rabbitmq_channel()
        channel.basic_publish(
            exchange="fulfillment.x",
            routing_key=f"city.{next_hop.lower()}",
            body=json.dumps(mensaje),
            mandatory=True,
        )
        conexion.close()
        print(f"[*] Paquete {pkg.id} enviado a {next_hop} via MQTT")
    except Exception as e:
        print(f"[!] Error al publicar paquete {pkg.id} en MQTT: {e}")
        # El paquete queda en BD; el estado refleja que está "forwarded" pero falló el envío

    # Registrar evento de envío
    event = PackageEvent(
        id=str(uuid.uuid4()),
        package_id=pkg.id,
        event_type="forwarded",
        next_city_id=next_hop,
        timestamp=now,
    )
    db.add(event)
    db.commit()

    return pkg


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
    
    # leer insured desde metaContent
    raw_meta = package_data.get("metaContent")
    meta_dict = {}
    if isinstance(raw_meta, dict):
        meta_dict = raw_meta
    elif isinstance(raw_meta, str):
        try:
            import json as _json
            meta_dict = _json.loads(raw_meta)
        except Exception:
            pass
    is_insured = bool(meta_dict.get("insured", False))
    base_payment = package_data.get("payment") or 0
    insurance_premium = int(base_payment * 0.05) if is_insured else None

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
        is_insured=is_insured,
        insurance_premium=insurance_premium,
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