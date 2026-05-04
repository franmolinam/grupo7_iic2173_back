import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import uuid

from src.database import Base
from src.models.package import Package
from src.models.city_connection import CityConnection
from src.models.package_event import PackageEvent

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
def make_package(**kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "origin_id": "COR",
        "destination_id": "LSN",
        "max_hops": 3,
        "created_at": datetime.now(timezone.utc),
        "deliver_not_before": datetime.now(timezone.utc),
        "status": "received",
    }
    defaults.update(kwargs)
    return Package(**defaults)


# TEST DE PACKAGE

# test para crear un paquete y verificar que se guarda correctamente
def test_create_package(db):
    pkg = make_package()
    db.add(pkg)
    db.commit()
    result = db.query(Package).filter_by(id=pkg.id).first()
    assert result is not None
    assert result.status == "received"

# test para verificar que el status por defecto de un paquete es "received"
def test_package_default_status(db):
    pkg = make_package()
    db.add(pkg)
    db.commit()
    assert pkg.status == "received"

# test para actualizar el status de un paquete y verificar que se actualiza correctamente
def test_update_package_status(db):
    pkg = make_package()
    db.add(pkg)
    db.commit()
    pkg.status = "delivered"
    pkg.last_action = "delivered"
    db.commit()
    result = db.query(Package).filter_by(id=pkg.id).first()
    assert result.status == "delivered"


# TEST DE CITY CONNECTION

# test para crear una conexión entre ciudades y verificar que se guarda correctamente
def test_create_city_connection(db):
    conn = CityConnection(
        destination_code="COR",
        destination_name="Coruscant",
        distance=1000.0,
        transport_cost=500.0,
        enabled=True
    )
    db.add(conn)
    db.commit()
    result = db.query(CityConnection).filter_by(destination_code="COR").first()
    assert result is not None
    assert result.enabled == True

# test para verificar que el campo enabled de una conexión entre ciudades se guarda correctamente
def test_city_connection_disabled(db):
    conn = CityConnection(
        destination_code="HGW",
        destination_name="Hogwarts",
        enabled=False
    )
    db.add(conn)
    db.commit()
    result = db.query(CityConnection).filter_by(destination_code="HGW").first()
    assert result.enabled == False


# TEST DE EVENTOS DE LOS PAQUETES

# test para crear un evento de paquete y verificar que se guarda correctamente
def test_create_package_event(db):
    pkg = make_package()
    db.add(pkg)
    db.commit()

    event = PackageEvent(
        id=str(uuid.uuid4()),
        package_id=pkg.id,
        event_type="received",
        from_city_id="COR"
    )
    db.add(event)
    db.commit()

    result = db.query(PackageEvent).filter_by(package_id=pkg.id).first()
    assert result is not None
    assert result.event_type == "received"

# test para verificar la relación entre paquetes y eventos (un paquete puede tener varios eventos asociados)
def test_package_event_relationship(db):
    pkg = make_package()
    db.add(pkg)
    db.commit()

    event = PackageEvent(
        id=str(uuid.uuid4()),
        package_id=pkg.id,
        event_type="transit",
        next_city_id="HGW"
    )
    db.add(event)
    db.commit()

    result = db.query(Package).filter_by(id=pkg.id).first()
    assert len(result.events) == 1
    assert result.events[0].next_city_id == "HGW"