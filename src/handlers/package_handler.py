from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.services.package_service import (
    save_package,
    update_package_status,
    deliver_package,
    upsert_connections,
    get_package_by_id,
    get_all_connections
)
from src.models.city_connection import CityConnection
import random

# Acá manejo los mensajes del broker, así que se debe llamar desde consumer.py
# a las funciones de este módulo para manejar cada tipo de mensaje que llegue del broker

CIUDAD_PROPIA = "LSN"

# Función para manejar un paquete recibido
def handle_package_received(db: Session, package_body: dict, received_from: str) -> dict:
    package_data = {**package_body, "receivedFrom": received_from}
    # guardo el paquete en la base de datos
    pkg = save_package(db, package_data)

    # destino del paquete y lo paso a mayúsculas por problemas de mayúsculas/minúsculas en los códigos de ciudad
    destination = package_body.get("destinationId", "").upper()
    # maxHops que vienen en el paquete, o 0 si no viene ese campo
    max_hops = package_body.get("maxHops", 0)

    # si es que el paquete es para nuestra ciudad:
    if destination == CIUDAD_PROPIA:
        # lo marco como pending_delivery para que el frontend lo pueda entregar después
        update_package_status(db, pkg.id, "pending_delivery", "received")
        return {"action": "deliver", "package_id": pkg.id}

    # si es que maxHops agotados:
    if max_hops <= 0:
        # marco el paquete como expirado
        update_package_status(db, pkg.id, "expired", "expired")
        return {"action": "expire", "package_id": pkg.id}

    # si es que hay que reenviar:
    # veo si hay ruta directa habilitada
    conexion_directa = db.query(CityConnection).filter_by(
        source_code=CIUDAD_PROPIA,
        destination_code=destination,
        enabled=True
    ).first()
    # si es que hay ruta directa, la uso:
    if conexion_directa:
        ciudad_destino = destination
    # sino busco una ciudad aleatoria habilitada para reenviar el paquete 
    else:
        # no puede ser ni nosotros ni la ciudad desde donde nos llegó el paquete
        excluir = {CIUDAD_PROPIA, received_from.upper()}
        alternativas = db.query(CityConnection).filter(
            CityConnection.source_code == CIUDAD_PROPIA,
            CityConnection.enabled == True,
            ~CityConnection.destination_code.in_(excluir)
        ).all()

        # si no hay rutas disponibles expira:
        if not alternativas:
            update_package_status(db, pkg.id, "expired", "expired")
            return {"action": "expire", "package_id": pkg.id}

        # elijo una ciudad destino aleatoria entre las alternativas disponibles que me dio antes
        ciudad_destino = random.choice(alternativas).destination_code

    # marco el paquete como in_transit y con la acción received
    update_package_status(db, pkg.id, "in_transit", "received")
    return {
        "action": "forward",
        "package_id": pkg.id,
        "destination_id": ciudad_destino,
        "max_hops_remaining": max_hops - 1,
    }

# Manejar un paquete reenviado 
# cuando se publica el paquete a la siguiente ciudad, llamo esta función para actualizar el estado del paquete en la base de datos
def handle_package_forwarded(db: Session, package_id: str, next_city_id: str) -> None:
    update_package_status(db, package_id, "forwarded", "forwarded", next_city_id=next_city_id)

# Manejar paquete expirado (cuando maxhops llega a  0 y el paquete no es para nuestra ciudad, lo marco expirado)
def handle_package_expired(db: Session, package_id: str) -> None:
    update_package_status(db, package_id, "expired", "expired")

# Manejar actualizacion de tabla de distancias/costos
def handle_distance_table(db: Session, distances: dict) -> None:
    upsert_connections(db, distances)

# Llamar cuando el frontend solicita concretar una entrega (RF04).
def handle_package_delivered(db: Session, package_id: str) -> tuple:
    return deliver_package(db, package_id)

# Leer las conexiones de la DB local y enviarlas en un mensaje 'cost-update' a otras ciudades.
def get_local_distance_table(db: Session) -> dict:
    conexiones = get_all_connections(db)
    distances = {}
    for conn in conexiones:
        distances[conn.destination_code] = {
            "destinationCode": conn.destination_code,
            "destinationName": conn.destination_name,
            "distance": conn.distance,
            "transportCost": conn.transport_cost,
            "enabled": conn.enabled
        }
    return distances