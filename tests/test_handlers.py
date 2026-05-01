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

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def seed_connection(db, destination_code="HGW", enabled=True):
    """Siembra una conexión habilitada para tests de ruteo."""
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


def make_package_body(**kwargs):
    """Helper para construir un packageBody como lo manda RabbitMQ."""
    defaults = {
        "id": str(uuid.uuid4()),
        "originId": "COR",
        "destinationId": "HGW",  # por defecto NO es para LSN
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


# --- Tests de handle_package_received ---

def test_receive_package_for_own_city(db):
    """Paquete destinado a LSN → acción 'deliver'."""
    body = make_package_body(destinationId="LSN")
    result = handle_package_received(db, body, received_from="COR")
    assert result["action"] == "deliver"
    assert "package_id" in result


def test_receive_package_for_other_city(db):
    """Paquete con destino distinto a LSN y hops disponibles → acción 'forward'."""
    seed_connection(db, destination_code="HGW", enabled=True)
    body = make_package_body(destinationId="HGW", maxHops=3)
    result = handle_package_received(db, body, received_from="COR")
    assert result["action"] == "forward"
    assert result["max_hops_remaining"] == 2


def test_receive_package_max_hops_zero(db):
    """Paquete con maxHops=0 que no es para LSN → acción 'expire'."""
    body = make_package_body(destinationId="HGW", maxHops=0)
    result = handle_package_received(db, body, received_from="COR")
    assert result["action"] == "expire"


def test_receive_package_max_hops_one(db):
    """Paquete con maxHops=1 que no es para LSN → forward con 0 hops restantes."""
    seed_connection(db, destination_code="HGW", enabled=True)
    body = make_package_body(destinationId="HGW", maxHops=1)
    result = handle_package_received(db, body, received_from="COR")
    assert result["action"] == "forward"
    assert result["max_hops_remaining"] == 0


def test_receive_package_saves_to_db(db):
    """handle_package_received debe persistir el paquete en la DB."""
    body = make_package_body(destinationId="HGW", maxHops=2)
    result = handle_package_received(db, body, received_from="central")
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg is not None
    assert pkg.received_from == "central"


def test_receive_package_idempotencia(db):
    """Recibir el mismo paquete dos veces no crea duplicados."""
    body = make_package_body(destinationId="HGW", maxHops=2)
    handle_package_received(db, body, received_from="COR")
    handle_package_received(db, body, received_from="COR")
    total = db.query(Package).count()
    assert total == 1


def test_receive_package_for_lsn_sets_pending_delivery(db):
    """Paquete para LSN queda en estado pending_delivery."""
    body = make_package_body(destinationId="LSN")
    result = handle_package_received(db, body, received_from="COR")
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg.status == "pending_delivery"


def test_receive_package_forward_sets_in_transit(db):
    """Paquete a reenviar queda en estado in_transit."""
    seed_connection(db, destination_code="HGW", enabled=True)
    body = make_package_body(destinationId="HGW", maxHops=3)
    result = handle_package_received(db, body, received_from="COR")
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg.status == "in_transit"


def test_receive_package_expire_sets_expired(db):
    """Paquete expirado queda en estado expired."""
    body = make_package_body(destinationId="HGW", maxHops=0)
    result = handle_package_received(db, body, received_from="COR")
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg.status == "expired"


# --- Tests de handle_package_forwarded ---

def test_handle_package_forwarded(db):
    """Después de reenviar, el paquete queda en estado forwarded."""
    body = make_package_body(destinationId="HGW", maxHops=3)
    result = handle_package_received(db, body, received_from="COR")
    handle_package_forwarded(db, result["package_id"], next_city_id="HGW")
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg.status == "forwarded"
    assert pkg.last_action == "forwarded"


def test_handle_package_forwarded_creates_event(db):
    """handle_package_forwarded registra el evento con next_city_id."""
    body = make_package_body(destinationId="HGW", maxHops=3)
    result = handle_package_received(db, body, received_from="COR")
    handle_package_forwarded(db, result["package_id"], next_city_id="HGW")
    events = db.query(PackageEvent).filter_by(
        package_id=result["package_id"],
        event_type="forwarded"
    ).all()
    assert len(events) == 1
    assert events[0].next_city_id == "HGW"


# --- Tests de handle_package_expired ---

def test_handle_package_expired(db):
    """handle_package_expired marca el paquete como expirado."""
    body = make_package_body(destinationId="HGW", maxHops=0)
    result = handle_package_received(db, body, received_from="COR")
    handle_package_expired(db, result["package_id"])
    pkg = db.query(Package).filter_by(id=result["package_id"]).first()
    assert pkg.status == "expired"


# --- Tests de handle_distance_table ---

def test_handle_distance_table_inserts(db):
    """handle_distance_table persiste las conexiones en la DB."""
    distances = {
        "HGW": {"destinationName": "Hogwarts", "distance": 1000, "transportCost": 500, "enabled": True},
        "COR": {"destinationName": "Coruscant", "distance": 2000, "transportCost": 800, "enabled": False},
    }
    handle_distance_table(db, distances)
    total = db.query(CityConnection).count()
    assert total == 2


def test_handle_distance_table_updates(db):
    """handle_distance_table actualiza conexiones existentes."""
    distances = {"HGW": {"destinationName": "Hogwarts", "distance": 1000, "transportCost": 500, "enabled": True}}
    handle_distance_table(db, distances)
    distances["HGW"]["enabled"] = False
    handle_distance_table(db, distances)
    conn = db.query(CityConnection).filter_by(destination_code="HGW").first()
    assert conn.enabled == False
    assert db.query(CityConnection).count() == 1


# --- Tests de handle_package_delivered ---

def test_handle_package_delivered_success(db):
    """Entrega exitosa cuando deliverNotBefore ya pasó."""
    body = make_package_body(
        destinationId="LSN",
        deliverNotBefore=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    )
    result = handle_package_received(db, body, received_from="COR")
    pkg, msg = handle_package_delivered(db, result["package_id"])
    assert pkg.status == "delivered"
    assert "successfully" in msg


def test_handle_package_delivered_too_early(db):
    """Entrega bloqueada si deliverNotBefore aún no pasó."""
    body = make_package_body(
        destinationId="LSN",
        deliverNotBefore=(datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    )
    result = handle_package_received(db, body, received_from="COR")
    pkg, msg = handle_package_delivered(db, result["package_id"])
    assert pkg.status != "delivered"
    assert "cannot be delivered before" in msg


def test_handle_package_delivered_not_found(db):
    """Retorna None si el paquete no existe."""
    pkg, msg = handle_package_delivered(db, "no-existe")
    assert pkg is None
    assert "not found" in msg