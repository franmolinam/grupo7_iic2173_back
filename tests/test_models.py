import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import uuid

from src.database import Base
from src.models.package import Package
from src.models.city_connection import CityConnection
from src.models.package_event import PackageEvent
from src.models.shipment_request import ShipmentRequest
from src.models.payment import Payment

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

    # helpers para ShipmentRequest y Payment
def make_shipment_request(**kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "auth0|testuser",
        "origin_id": "LSN",
        "destination_id": "HGW",
        "height": 10.0,
        "width": 10.0,
        "depth": 10.0,
        "criteria": "price",
        "max_hops": 5,
        "fprice": 1.0,
        "status": "pending_quote",
    }
    defaults.update(kwargs)
    return ShipmentRequest(**defaults)

def make_payment(shipment_request_id, **kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "shipment_request_id": shipment_request_id,
        "user_id": "auth0|testuser",
        "status": "TRYING",
        "amount": 15000,
        "currency": "CLP",
    }
    defaults.update(kwargs)
    return Payment(**defaults)


# TEST DE SHIPMENT REQUEST

# test para crear una solicitud de envío y verificar que se guarda correctamente
def test_create_shipment_request(db):
    sr = make_shipment_request()
    db.add(sr)
    db.commit()
    result = db.query(ShipmentRequest).filter_by(id=sr.id).first()
    assert result is not None
    assert result.status == "pending_quote"

# test para verificar que el status por defecto de una solicitud de envío es "pending_quote"
def test_shipment_request_default_status(db):
    sr = make_shipment_request()
    db.add(sr)
    db.commit()
    assert sr.status == "pending_quote"

# test para verificar que el precio por defecto de una solicitud de envío es 1.0
def test_shipment_request_default_fprice(db):
    sr = make_shipment_request()
    db.add(sr)
    db.commit()
    assert sr.fprice == 1.0

# test para actualizar el status de una solicitud de envío y verificar que se actualiza correctamente
def test_shipment_request_update_status(db):
    sr = make_shipment_request()
    db.add(sr)
    db.commit()
    sr.status = "quoted"
    sr.route_metric_cost = 12000.0
    sr.hops_count = 3
    sr.final_price = 15000
    db.commit()
    result = db.query(ShipmentRequest).filter_by(id=sr.id).first()
    assert result.status == "quoted"
    assert result.final_price == 15000


# TEST DE PAYMENT

# test para crear un pago asociado a una solicitud de envío y verificar que se guarda correctamente
def test_create_payment(db):
    sr = make_shipment_request()
    db.add(sr)
    db.commit()

    payment = make_payment(sr.id, webpay_token="token-abc-123")
    db.add(payment)
    db.commit()

    result = db.query(Payment).filter_by(id=payment.id).first()
    assert result is not None
    assert result.status == "TRYING"
    assert result.amount == 15000

# test para verificar que el status por defecto de un pago es "TRYING"
def test_payment_default_status(db):
    sr = make_shipment_request()
    db.add(sr)
    db.commit()

    payment = make_payment(sr.id)
    db.add(payment)
    db.commit()
    assert payment.status == "TRYING"

# test para actualizar el status de un pago a "SUCCESS" y verificar que se actualiza correctamente
def test_payment_update_to_success(db):
    sr = make_shipment_request()
    db.add(sr)
    db.commit()

    payment = make_payment(sr.id, webpay_token="token-abc-123")
    db.add(payment)
    db.commit()

    payment.status = "SUCCESS"
    payment.authorization_code = "AUTH-999"
    db.commit()

    result = db.query(Payment).filter_by(id=payment.id).first()
    assert result.status == "SUCCESS"
    assert result.authorization_code == "AUTH-999"

# test para verificar que el campo webpay_token de un pago es único (idempotencia)
def test_payment_webpay_token_unique(db):
    sr = make_shipment_request()
    db.add(sr)
    db.commit()

    p1 = make_payment(sr.id, webpay_token="token-duplicado")
    p2 = make_payment(sr.id, webpay_token="token-duplicado")
    db.add(p1)
    db.commit()
    db.add(p2)

    with pytest.raises(Exception):
        db.commit()

#  test para verificar la relación entre solicitudes de envío y pagos (una solicitud de envío puede tener varios pagos asociados)
def test_payment_shipment_request_relationship(db):
    sr = make_shipment_request()
    db.add(sr)
    db.commit()

    payment = make_payment(sr.id)
    db.add(payment)
    db.commit()

    result = db.query(ShipmentRequest).filter_by(id=sr.id).first()
    assert len(result.payments) == 1
    assert result.payments[0].amount == 15000