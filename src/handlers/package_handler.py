"""
src/handlers/package_handler.py

Capa intermedia entre el consumer de RabbitMQ y los servicios de base de datos.
Dev2 (Ingeniero de Mensajería) debe llamar las funciones de este módulo
desde consumer.py — nunca importar package_service directamente.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.services.package_service import (
    save_package,
    update_package_status,
    deliver_package,
    upsert_connections,
    get_package_by_id,
)

CIUDAD_PROPIA = "LSN"


def handle_package_received(db: Session, package_body: dict, received_from: str) -> dict:
    """
    Llamar cuando llega un mensaje type='package-transit' a nuestra cola.

    Dev2 debe llamar esta función ANTES de decidir si reenviar o entregar.
    Retorna un dict con la acción que debe tomarse.

    Args:
        db:             Sesión de base de datos (obtener con SessionLocal())
        package_body:   El objeto 'packageBody' del mensaje RabbitMQ (dict)
        received_from:  cityId de quien nos envió el paquete (o "central")

    Returns:
        {
            "action": "deliver" | "forward" | "expire",
            "package_id": str,
            "destination_id": str,   # solo si action == "forward"
        }

    Ejemplo de uso en consumer.py:
        from src.handlers.package_handler import handle_package_received
        from src.database import SessionLocal

        def callback(ch, method, properties, body):
            mensaje = json.loads(body)
            if mensaje["type"] == "package-transit":
                db = SessionLocal()
                try:
                    result = handle_package_received(
                        db,
                        package_body=mensaje["packageBody"],
                        received_from=mensaje.get("cityId", "central")
                    )
                    # result["action"] te dice qué hacer a continuación
                finally:
                    db.close()
    """
    package_data = {**package_body, "receivedFrom": received_from}
    pkg = save_package(db, package_data)

    destination = package_body.get("destinationId")
    max_hops = package_body.get("maxHops", 0)

    # Caso 1: el paquete es para nuestra ciudad
    if destination == CIUDAD_PROPIA:
        update_package_status(db, pkg.id, "pending_delivery", "received")
        return {"action": "deliver", "package_id": pkg.id}

    # Caso 2: maxHops agotados → expirar
    if max_hops <= 0:
        update_package_status(db, pkg.id, "expired", "expired")
        return {"action": "expire", "package_id": pkg.id}

    # Caso 3: hay que reenviar
    update_package_status(db, pkg.id, "in_transit", "received")
    return {
        "action": "forward",
        "package_id": pkg.id,
        "destination_id": destination,
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