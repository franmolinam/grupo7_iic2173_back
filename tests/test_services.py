import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone, timedelta
import uuid

from src.database import Base
from src.models.package import Package
from src.models.city_connection import CityConnection
from src.models.package_event import PackageEvent
from src.services.package_service import (
    save_package,
    get_package_by_id,
    get_all_packages,
    update_package_status,
    deliver_package,
    get_all_connections,
    upsert_connections,
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

# helper para crear paquetes de prueba
def make_package_data(**kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "originId": "COR",
        "destinationId": "LSN",
        "maxHops": 3,
        "createdAt": datetime.now(timezone.utc),
        "deliverNotBefore": datetime.now(timezone.utc) - timedelta(hours=1),
        "metaContent": "test",
        "isMetaEncrypted": False,
        "priorityClass": "medium",
        "payment": 100,
        "constraints": {},
        "deliveryStrategy": "direct",
    }
    defaults.update(kwargs)
    return defaults


# test para guardar un paquete nuevo y verificar que se guarda correctamente
def test_save_package(db):
    data = make_package_data()
    pkg = save_package(db, data)
    assert pkg.id == data["id"]
    assert pkg.status == "received"

# test para verificar que guardar el mismo paquete dos veces no crea duplicados
def test_save_package_idempotencia(db):
    data = make_package_data()
    pkg1 = save_package(db, data)
    pkg2 = save_package(db, data)
    assert pkg1.id == pkg2.id
    total = db.query(Package).count()
    assert total == 1

# test para obtener un paquete por id y verificar que se obtiene correctamente
def test_get_package_by_id(db):
    data = make_package_data()
    save_package(db, data)
    result = get_package_by_id(db, data["id"])
    assert result is not None
    assert result.id == data["id"]

# test para verificar que obtener un paquete por id que no existe retorna None
def test_get_package_by_id_not_found(db):
    result = get_package_by_id(db, "no-existe")
    assert result is None

# test para obtener todos los paquetes y verificar que se obtienen correctamente
def test_get_all_packages(db):
    save_package(db, make_package_data())
    save_package(db, make_package_data())
    results = get_all_packages(db)
    assert len(results) == 2

# test para actualizar el estado de un paquete y verificar que se actualiza correctamente
def test_update_package_status(db):
    data = make_package_data()
    pkg = save_package(db, data)
    updated = update_package_status(db, pkg.id, "transit", "transit", next_city_id="HGW")
    assert updated.status == "transit"
    assert updated.last_action == "transit"

# test para verificar que cada vez que se actualiza el estado de un paquete, se crea un evento asociado
def test_update_package_status_creates_event(db): 
    data = make_package_data()
    pkg = save_package(db, data)
    update_package_status(db, pkg.id, "expired", "expired")
    events = db.query(PackageEvent).filter_by(package_id=pkg.id).all()
    assert len(events) == 1
    assert events[0].event_type == "expired"

# # test para entregar un paquete exitosamente y verificar que se actualiza el estado a "delivered"
def test_deliver_package_success(db): 
    data = make_package_data(
        deliverNotBefore=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    save_package(db, data)
    pkg, msg = deliver_package(db, data["id"])
    assert pkg.status == "delivered"
    assert "successfully" in msg

# test para verificar que no se puede entregar un paquete antes de su deliverNotBefore
def test_deliver_package_too_early(db):
    data = make_package_data(
        deliverNotBefore=datetime.now(timezone.utc) + timedelta(hours=5)
    )
    save_package(db, data)
    pkg, msg = deliver_package(db, data["id"])
    assert pkg.status != "delivered"
    assert "cannot be delivered before" in msg

# test para verificar que no se puede entregar un paquete que ya fue entregado
def test_deliver_package_already_delivered(db):
    data = make_package_data(
        deliverNotBefore=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    save_package(db, data)
    deliver_package(db, data["id"])
    pkg, msg = deliver_package(db, data["id"])
    assert "already delivered" in msg

# test para verificar que no se puede entregar un paquete que no existe
def test_deliver_package_not_found(db):
    pkg, msg = deliver_package(db, "no-existe")
    assert pkg is None
    assert "not found" in msg

# test para verificar que se pueden insertar conexiones entre ciudades y que se guardan correctamente
def test_upsert_connections(db):
    distances = {
        "HGW": {"destinationName": "Hogwarts", "distance": 1000, "transportCost": 500, "enabled": True},
        "COR": {"destinationName": "Coruscant", "distance": 2000, "transportCost": 800, "enabled": False},
    }
    upsert_connections(db, distances)
    conns = get_all_connections(db)
    assert len(conns) == 2

# test para verificar que si se inserta una conexión con un destination_code que ya existe, se actualiza la conexión existente en vez de crear una nueva
def test_upsert_connections_updates_existing(db): 
    distances = {
        "HGW": {"destinationName": "Hogwarts", "distance": 1000, "transportCost": 500, "enabled": True},
    }
    upsert_connections(db, distances)
    distances["HGW"]["enabled"] = False
    upsert_connections(db, distances)
    conn = db.query(CityConnection).filter_by(destination_code="HGW").first()
    assert conn.enabled == False
    total = db.query(CityConnection).count()
    assert total == 1