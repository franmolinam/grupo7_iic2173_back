import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone, timedelta
import uuid

from src.database import Base
from src.models.package import Package
from src.models.package_event import PackageEvent
from src.models.city_connection import CityConnection
from src.handlers.package_handler import (
    handle_package_received,
    handle_package_forwarded,
    handle_package_expired,
    handle_distance_table,
    handle_package_delivered,
)

# DB en memoria para tests
TEST_DATABASE_URL = "sqlite:///:memory:"

# fixture para la sesión de DB en tests
@pytest.fixture
def db():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

# helper para sembrar conexiones en la DB pq tests de handlers fallan con 'expire' en vez de 'forward'
# se crea una CityConnection habilitada antes de cada test de ruteo
def seed_connection(db, destination_code="HGW", enabled=True):
    from src.models.city_connection import CityConnection
    conn = CityConnection(
        destination_code=destination_code,
        destination_name="Test City",
        distance=1000.0,
        transport_cost=500.0,
        enabled=enabled,
    )
    db.add(conn)
    db.commit()
    return conn

# helper para construir un packageBody como lo manda RabbitMQ, con valores por defecto que se pueden sobrescribir
def make_package_body(**kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "originId": "COR",
        "destinationId": "HGW",
        "maxHops": 3,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "deliverNotBefore": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "metaContent": "",
        "isMetaEncrypted": False,
        "constraints": {},
        "priorityClass": "medium",
        "payment": 0,
        "deliveryStrategy": "direct",
    }
    defaults.update(kwargs)
    return defaults

# test para verificar que si el paquete es para nuestra ciudad, se marca como pending_delivery y se retorna la acción 'deliver'
def test_receive_package_for_own_city(db):
    body = make_package_body(destinationId="LSN")
    result = handle_package_received(db, body, received_from="COR")
    assert result["action"] == "deliver"
    assert "package_id" in result

# test para verificar que si el paquete no es para nuestra ciudad y tiene maxHops disponibles, se marca como in_transit y se retorna la acción 'forward' con una ciudad destino válida
def test_receive_package_for_other_city(db):
    seed_connection(db, destination_code="HGW", enabled=True)
    body = make_package_body(destinationId="HGW", maxHops=3)
    result = handle_package_received(db, body, received_from="COR")
    assert result["action"] == "forward"
    assert result["max_hops_remaining"] == 2

# test para verificar que si el paquete no es para nuestra ciudad y tiene maxHops 0, se marca como expired y se retorna la acción 'expire'
def test_receive_package_max_hops_zero(db):
    body = make_package_body(destinationId="HGW", maxHops=0)
    result = handle_package_received(db, body, received_from="COR")
    assert result["action"] == "expire"

# test para verificar si el paquete tiene maxHops=1 y no es para LSN → forward con 0 hops restantes
def test_receive_package_max_hops_one(db): 
    seed_connection(db, destination_code="HGW", enabled=True)
    body = make_package_body(destinationId="HGW", maxHops=1)
    result = handle_package_received(db, body, received_from="COR")
    assert result["action"] == "forward"
    assert result["max_hops_remaining"] == 0

# test para verificar que handle_package_received persiste el paquete en la DB
def test_receive_package_saves_to_db(db):
    body = make_package_body(destinationId="HGW", maxHops=2)
    result = handle_package_received(db, body, received_from="central")
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg is not None
    assert pkg.received_from == "central"

# test para verificar que recibir el mismo paquete dos veces no crea duplicados
def test_receive_package_idempotencia(db):
    body = make_package_body(destinationId="HGW", maxHops=2)
    handle_package_received(db, body, received_from="COR")
    handle_package_received(db, body, received_from="COR")
    total = db.query(Package).count()
    assert total == 1

# test para verificar que el paquete para LSN queda en estado pending_delivery
def test_receive_package_for_lsn_sets_pending_delivery(db):
    body = make_package_body(destinationId="LSN")
    result = handle_package_received(db, body, received_from="COR")
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg.status == "pending_delivery"

# test para verificar que el paquete a reenviar queda en estado in_transit
def test_receive_package_forward_sets_in_transit(db):
    seed_connection(db, destination_code="HGW", enabled=True)
    body = make_package_body(destinationId="HGW", maxHops=3)
    result = handle_package_received(db, body, received_from="COR")
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg.status == "in_transit"

# test para verificar que el paquete expirado queda en estado expired
def test_receive_package_expire_sets_expired(db):
    body = make_package_body(destinationId="HGW", maxHops=0)
    result = handle_package_received(db, body, received_from="COR")
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg.status == "expired"


# test para verificar que después de reenviar, el paquete queda en estado forwarded
def test_handle_package_forwarded(db):
    body = make_package_body(destinationId="HGW", maxHops=3)
    result = handle_package_received(db, body, received_from="COR")
    handle_package_forwarded(db, result["package_id"], next_city_id="HGW")
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg.status == "forwarded"
    assert pkg.last_action == "forwarded"

# test para verificar quehandle_package_forwarded registra el evento con next_city_id
def test_handle_package_forwarded_creates_event(db):
    body = make_package_body(destinationId="HGW", maxHops=3)
    result = handle_package_received(db, body, received_from="COR")
    handle_package_forwarded(db, result["package_id"], next_city_id="HGW")
    events = db.query(PackageEvent).filter_by(
        package_id=result["package_id"],
        event_type="forwarded"
    ).all()
    assert len(events) == 1
    assert events[0].next_city_id == "HGW"

# test para verificar que handle_package_expired marca el paquete como expirado
def test_handle_package_expired(db):
    body = make_package_body(destinationId="HGW", maxHops=0)
    result = handle_package_received(db, body, received_from="COR")
    handle_package_expired(db, result["package_id"])
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg.status == "expired"

# test para verificar que handle_distance_table persiste las conexiones en la DB
def test_handle_distance_table_inserts(db):
    distances = {
        "HGW": {"destinationName": "Hogwarts", "distance": 1000, "transportCost": 500, "enabled": True},
        "COR": {"destinationName": "Coruscant", "distance": 2000, "transportCost": 800, "enabled": False},
    }
    handle_distance_table(db, distances)
    total = db.query(CityConnection).count()
    assert total == 2

# test para verificar que handle_distance_table actualiza conexiones existentes
def test_handle_distance_table_updates(db):
    distances = {"HGW": {"destinationName": "Hogwarts", "distance": 1000, "transportCost": 500, "enabled": True}}
    handle_distance_table(db, distances)
    distances["HGW"]["enabled"] = False
    handle_distance_table(db, distances)
    conn = db.query(CityConnection).filter_by(destination_code="HGW").first()
    assert conn.enabled == False
    assert db.query(CityConnection).count() == 1

# test para verificar entrega exitosa cuando deliverNotBefore ya pasó
def test_handle_package_delivered_success(db):
    body = make_package_body(
        destinationId="LSN",
        deliverNotBefore=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    )
    result = handle_package_received(db, body, received_from="COR")
    pkg, msg = handle_package_delivered(db, result["package_id"])
    assert pkg.status == "delivered"
    assert "successfully" in msg

# test para verificar entrega bloqueada si deliverNotBefore aún no pasó
def test_handle_package_delivered_too_early(db):
    body = make_package_body(
        destinationId="LSN",
        deliverNotBefore=(datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    )
    result = handle_package_received(db, body, received_from="COR")
    pkg, msg = handle_package_delivered(db, result["package_id"])
    assert pkg.status != "delivered"
    assert "cannot be delivered before" in msg

# test para verificar que retorna None si el paquete no existe
def test_handle_package_delivered_not_found(db):
    pkg, msg = handle_package_delivered(db, "no-existe")
    assert pkg is None
    assert "not found" in msg