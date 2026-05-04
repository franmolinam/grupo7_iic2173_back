from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.services.package_service import (
    save_package,
    update_package_status,
    deliver_package,
    upsert_connections,
    get_package_by_id,
)
from src.models.city_connection import CityConnection
import random

# Esto es una capa intermedia entre el consumer de RabbitMQ y los servicios de la bdd
# desde consumer.py, se debe llamar a las funciones de este módulo para manejar cada tipo de mensaje que llegue del broker

CIUDAD_PROPIA = "LSN"

def handle_package_received(db: Session, package_body: dict, received_from: str) -> dict:
    package_data = {**package_body, "receivedFrom": received_from}
    pkg = save_package(db, package_data)

    destination = package_body.get("destinationId", "").upper()  # Bug 1 fix
    max_hops = package_body.get("maxHops", 0)

    # Caso 1: el paquete es para nuestra ciudad
    if destination == CIUDAD_PROPIA:
        update_package_status(db, pkg.id, "pending_delivery", "received")
        return {"action": "deliver", "package_id": pkg.id}

    # Caso 2: maxHops agotados → expirar
    if max_hops <= 0:
        update_package_status(db, pkg.id, "expired", "expired")
        return {"action": "expire", "package_id": pkg.id}

    # Caso 3: hay que reenviar — Bug 2 fix
    # Verificar si hay ruta directa habilitada
    conexion_directa = db.query(CityConnection).filter_by(
        destination_code=destination, enabled=True
    ).first()

    if conexion_directa:
        ciudad_destino = destination
    else:
        # Buscar ciudad aleatoria habilitada que no sea nosotros ni el remitente
        excluir = {CIUDAD_PROPIA, received_from.upper()}
        alternativas = db.query(CityConnection).filter(
            CityConnection.enabled == True,
            ~CityConnection.destination_code.in_(excluir)
        ).all()

        if not alternativas:
            # Sin rutas disponibles → expirar
            update_package_status(db, pkg.id, "expired", "expired")
            return {"action": "expire", "package_id": pkg.id}

        ciudad_destino = random.choice(alternativas).destination_code

    update_package_status(db, pkg.id, "in_transit", "received")
    return {
        "action": "forward",
        "package_id": pkg.id,
        "destination_id": ciudad_destino,
        "max_hops_remaining": max_hops - 1,
    }


def handle_package_forwarded(db: Session, package_id: str, next_city_id: str) -> None:
    """
    Llamar DESPUÉS de que Dev2 haya publicado exitosamente el paquete
    a la siguiente ciudad (ruta directa o redirigida).

    Args:
        db:           Sesión de base de datos
        package_id:   ID del paquete reenviado
        next_city_id: Código de ciudad destino al que se envió

    Ejemplo de uso en consumer.py:
        handle_package_forwarded(db, package_id="uuid-xxx", next_city_id="HGW")
    """
    update_package_status(db, package_id, "forwarded", "forwarded", next_city_id=next_city_id)


def handle_package_expired(db: Session, package_id: str) -> None:
    """
    Llamar cuando maxHops llega a 0 y el paquete no es para nuestra ciudad.
    Marca el paquete como expirado en la DB.

    Args:
        db:          Sesión de base de datos
        package_id:  ID del paquete expirado

    Ejemplo de uso en consumer.py:
        handle_package_expired(db, package_id="uuid-xxx")
    """
    update_package_status(db, package_id, "expired", "expired")


def handle_distance_table(db: Session, distances: dict) -> None:
    """
    Llamar cuando llega un mensaje type='distance-table' (desde la central
    o como update periódico en la cola propia).

    Args:
        db:        Sesión de base de datos
        distances: El objeto 'data.distances' del mensaje RabbitMQ (dict)

    Ejemplo de uso en consumer.py:
        if mensaje["type"] == "distance-table":
            handle_distance_table(db, distances=mensaje["data"]["distances"])
    """
    upsert_connections(db, distances)


def handle_package_delivered(db: Session, package_id: str) -> tuple:
    """
    Llamar cuando el frontend solicita concretar una entrega (RF04).
    Valida deliverNotBefore e idempotencia.

    Args:
        db:          Sesión de base de datos
        package_id:  ID del paquete a entregar

    Returns:
        (package, message) — misma firma que deliver_package()

    Ejemplo de uso en routes/packages.py:
        pkg, msg = handle_package_delivered(db, package_id=id)
    """
    return deliver_package(db, package_id)