import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone, timedelta
import uuid
import httpx

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
from unittest.mock import MagicMock, patch
from src.services.shipment_service import validate_dimensions, calculate_price, get_quotation
from src.models.shipment_request import ShipmentRequest
from src.models.payment import Payment
from src.services.package_service import create_and_send_package
from src.services.jobs_master_service import get_routes, check_heartbeat

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
    upsert_connections(db, "LSN", distances)
    conns = get_all_connections(db)
    assert len(conns) == 2

# test para verificar que si se inserta una conexión con un destination_code que ya existe, se actualiza la conexión existente en vez de crear una nueva
def test_upsert_connections_updates_existing(db): 
    distances = {
        "HGW": {"destinationName": "Hogwarts", "distance": 1000, "transportCost": 500, "enabled": True},
    }
    upsert_connections(db, "LSN", distances)
    distances["HGW"]["enabled"] = False
    upsert_connections(db, "LSN", distances)
    conn = db.query(CityConnection).filter_by(source_code="LSN", destination_code="HGW").first()
    assert conn.enabled == False
    total = db.query(CityConnection).count()
    assert total == 1

# TEST DE VALIDATE_DIMENSIONS

# test para verificar que validar dimensiones dentro del límite no lanza error
def test_validate_dimensions_ok():
    validate_dimensions(100, 100, 100)  # 300 cm, no lanza

# test para verificar que validar dimensiones exactamente en el límite no lanza error
def test_validate_dimensions_exactamente_limite():
    validate_dimensions(1000, 1000, 1000)  # exactamente 3000 cm, no lanza

# test para verificar que validar dimensiones que superan el límite lanza ValueError
def test_validate_dimensions_supera_limite():
    with pytest.raises(ValueError, match="3000"):
        validate_dimensions(1000, 1000, 1001)  # 3001 cm


# TEST DE CALCULATE_PRICE

# test para verificar que calcular precio con dimensiones y costo de ruta normales retorna el precio esperado
def test_calculate_price_normal():
    # 0.01 * (10+10+10) * 12000 * 1.0 = 3600 -> mínimo 5000
    resultado = calculate_price(10, 10, 10, 12000, 1.0)
    assert resultado == 5000

# test para verificar que calcular precio con dimensiones grandes y costo de ruta alto retorna el precio máximo
def test_calculate_price_minimo():
    resultado = calculate_price(1, 1, 1, 1, 1.0)
    assert resultado == 5000

# test para verificar que calcular precio con dimensiones grandes y costo de ruta alto retorna el precio máximo
def test_calculate_price_maximo():
    resultado = calculate_price(1000, 1000, 1000, 99999, 2.0)
    assert resultado == 100000

# test para verificar que calcular precio con un fprice alto retorna un precio mayor
def test_calculate_price_con_fprice():
    # 0.01 * 300 * 10000 * 2.0 = 60000
    resultado = calculate_price(100, 100, 100, 10000, 2.0)
    assert resultado == 60000

# test para verificar que calcular precio con un fprice bajo retorna un precio menor
def test_calculate_price_fprice_bajo():
    # 0.01 * 300 * 10000 * 0.5 = 15000
    resultado = calculate_price(100, 100, 100, 10000, 0.5)
    assert resultado == 15000


# TEST DE GET_QUOTATION

MOCK_ROUTE = {
    "status": "done",
    "routeMetricCost": 12000,
    "hops": ["LSN", "TRA", "HGW"],
    "hopCount": 2,
}

# test para verificar que obtener una cotización con datos válidos retorna la cotización esperada
def test_get_quotation_ok():
    with patch("src.services.shipment_service.get_routes", return_value=MOCK_ROUTE):
        result = get_quotation("HGW", 100, 100, 100, "price", 3, 1.0)
        assert result["route_metric_cost"] == 12000
        assert result["hops_count"] == 2
        assert result["next_hop"] == "TRA"
        assert result["full_path"] == ["LSN", "TRA", "HGW"]
        assert result["final_price"] == 36000

# test para verificar que obtener una cotización con dimensiones que superan el límite lanza ValueError
def test_get_quotation_dimensiones_invalidas():
    with patch("src.services.shipment_service.get_routes", return_value=MOCK_ROUTE):
        with pytest.raises(ValueError, match="3000"):
            get_quotation("HGW", 1000, 1000, 1001, "price", 3, 1.0)

# test para verificar que obtener una cotización con maxHops insuficiente lanza ValueError
def test_get_quotation_max_hops_insuficiente():
    with patch("src.services.shipment_service.get_routes", return_value=MOCK_ROUTE):
        with pytest.raises(ValueError, match="maxHops insuficiente"):
            get_quotation("HGW", 100, 100, 100, "price", 1, 1.0)  # ruta necesita 2, se manda 1

# test para verificar que obtener una cotización para una ciudad no alcanzable lanza ValueError
def test_get_quotation_ciudad_no_alcanzable():
    mock_sin_ruta = {"status": "done", "routeMetricCost": 0, "hops": [], "hopCount": 0}
    with patch("src.services.shipment_service.get_routes", return_value=mock_sin_ruta):
        with pytest.raises(ValueError, match="no es alcanzable"):
            get_quotation("XYZ", 100, 100, 100, "price", 3, 1.0)

# test para verificar que obtener una cotización con un fprice alto retorna un precio mayor
def test_get_quotation_precio_minimo():
    mock_barato = {"status": "done", "routeMetricCost": 1, "hops": ["LSN", "HGW"], "hopCount": 1}
    with patch("src.services.shipment_service.get_routes", return_value=mock_barato):
        result = get_quotation("HGW", 1, 1, 1, "price", 1, 1.0)
        assert result["final_price"] == 5000

# test para verificar que obtener una cotización con un fprice alto retorna un precio mayor
def test_get_quotation_precio_maximo():
    mock_caro = {"status": "done", "routeMetricCost": 999999, "hops": ["LSN", "HGW"], "hopCount": 1}
    with patch("src.services.shipment_service.get_routes", return_value=mock_caro):
        result = get_quotation("HGW", 1000, 1000, 1000, "price", 1, 2.0)
        assert result["final_price"] == 100000

# ─── HELPERS PARA RF04 ────────────────────────────────────────────
# Estos helpers crean ShipmentRequest y Payment en la base de datos para luego probar la función create_and_send_package, que es la que se encarga de crear el paquete y enviarlo a RabbitMQ. De esta forma, podemos probar create_and_send_package en un entorno lo más realista posible, con datos en la base de datos y sin mocks (salvo el canal de RabbitMQ para no depender de una instancia real).
def make_shipment_request(db, **kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "user_id": "auth0|testuser",
        "origin_id": "LSN",
        "destination_id": "HGW",
        "height": 100.0,
        "width": 100.0,
        "depth": 100.0,
        "criteria": "price",
        "max_hops": 3,
        "fprice": 1.0,
        "route_metric_cost": 12000.0,
        "hops_count": 2,
        "next_hop": "TRA",
        "full_path": ["LSN", "TRA", "HGW"],
        "final_price": 36000,
        "status": "paid",
    }
    defaults.update(kwargs)
    sr = ShipmentRequest(**defaults)
    db.add(sr)
    db.commit()
    db.refresh(sr)
    return sr

# helper para crear un pago asociado a un ShipmentRequest, con datos por defecto que se pueden sobrescribir con kwargs
def make_payment(db, shipment_id, **kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "shipment_request_id": shipment_id,
        "user_id": "auth0|testuser",
        "webpay_token": f"token-{uuid.uuid4()}",
        "status": "SUCCESS",
        "amount": 36000,
        "currency": "CLP",
    }
    defaults.update(kwargs)
    p = Payment(**defaults)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ─── TESTS DE create_and_send_package (RF04) ──────────────────────
# Estos tests verifican que la función create_and_send_package crea el paquete con los datos correctos, que es idempotente, que registra un evento al crear el paquete, que incluye el criterio en constraints, que decrementa maxHops en el mensaje publicado, que publica a la ciudad correcta según nextHop o destinationId, y que no falla si hay un error al obtener el canal de RabbitMQ (en cuyo caso el paquete igual se guarda en la base de datos).
def test_create_and_send_package_crea_paquete(db):
    sr = make_shipment_request(db)
    payment = make_payment(db, sr.id)

    with patch("src.services.package_service._get_rabbitmq_channel") as mock_ch:
        mock_conn = mock_ch.return_value = (MagicMock(), MagicMock())
        pkg = create_and_send_package(db, sr, payment)

    assert pkg is not None
    assert pkg.origin_id == "LSN"
    assert pkg.destination_id == "HGW"
    assert pkg.shipment_request_id == sr.id
    assert pkg.constraints == {"criteria": "price"}
    assert pkg.status == "forwarded"

# test para verificar que si se llama a create_and_send_package dos veces con el mismo shipment, no se crean paquetes duplicados y se retorna el mismo paquete
def test_create_and_send_package_idempotencia(db):
    sr = make_shipment_request(db)
    payment = make_payment(db, sr.id)

    with patch("src.services.package_service._get_rabbitmq_channel") as mock_ch:
        mock_ch.return_value = (MagicMock(), MagicMock())
        pkg1 = create_and_send_package(db, sr, payment)
        pkg2 = create_and_send_package(db, sr, payment)

    assert pkg1.id == pkg2.id
    total = db.query(Package).count()
    assert total == 1

# test para verificar que al crear un paquete se registra un evento con el tipo de evento igual al nuevo estado del paquete (en este caso, "forwarded") y con la ciudad del siguiente salto
def test_create_and_send_package_registra_evento(db):
    sr = make_shipment_request(db)
    payment = make_payment(db, sr.id)

    with patch("src.services.package_service._get_rabbitmq_channel") as mock_ch:
        mock_ch.return_value = (MagicMock(), MagicMock())
        pkg = create_and_send_package(db, sr, payment)

    events = db.query(PackageEvent).filter_by(package_id=pkg.id).all()
    assert len(events) == 1
    assert events[0].event_type == "forwarded"
    assert events[0].next_city_id == "TRA"

# test para verificar que el criterio de evaluación se incluye en constraints del paquete creado
def test_create_and_send_package_criteria_en_constraints(db):
    sr = make_shipment_request(db, criteria="distance")
    payment = make_payment(db, sr.id)

    with patch("src.services.package_service._get_rabbitmq_channel") as mock_ch:
        mock_ch.return_value = (MagicMock(), MagicMock())
        pkg = create_and_send_package(db, sr, payment)

    assert pkg.constraints["criteria"] == "distance"

# test para verificar que el mensaje publicado a RabbitMQ tiene maxHops decrementado en 1 respecto al ShipmentRequest
def test_create_and_send_package_max_hops_decrementado(db):
    sr = make_shipment_request(db, max_hops=5)
    payment = make_payment(db, sr.id)

    with patch("src.services.package_service._get_rabbitmq_channel") as mock_ch:
        mock_channel = MagicMock()
        mock_ch.return_value = (MagicMock(), mock_channel)
        create_and_send_package(db, sr, payment)

    # Verificar que el mensaje publicado tiene maxHops = 4 (5 - 1)
    call_args = mock_channel.basic_publish.call_args
    body = json.loads(call_args.kwargs["body"])
    assert body["packageBody"]["maxHops"] == 4

# test para verificar que el mensaje se publica a la ciudad del nextHop si nextHop está presente, o a destinationId si no hay nextHop
def test_create_and_send_package_publica_a_next_hop(db):
    sr = make_shipment_request(db, next_hop="TRA")
    payment = make_payment(db, sr.id)

    with patch("src.services.package_service._get_rabbitmq_channel") as mock_ch:
        mock_channel = MagicMock()
        mock_ch.return_value = (MagicMock(), mock_channel)
        create_and_send_package(db, sr, payment)

    call_args = mock_channel.basic_publish.call_args
    assert call_args.kwargs["routing_key"] == "city.tra"

# test para verificar que si no hay nextHop, el mensaje se publica a destinationId
def test_create_and_send_package_usa_destination_si_no_hay_next_hop(db):
    sr = make_shipment_request(db, next_hop=None, destination_id="HGW")
    payment = make_payment(db, sr.id)

    with patch("src.services.package_service._get_rabbitmq_channel") as mock_ch:
        mock_channel = MagicMock()
        mock_ch.return_value = (MagicMock(), mock_channel)
        create_and_send_package(db, sr, payment)

    call_args = mock_channel.basic_publish.call_args
    assert call_args.kwargs["routing_key"] == "city.hgw"

# test para verificar que si hay un error al obtener el canal de RabbitMQ, create_and_send_package no lanza excepción y el paquete igual se guarda en la base de datos con estado "forwarded"
def test_create_and_send_package_no_falla_si_mqtt_error(db):
    sr = make_shipment_request(db)
    payment = make_payment(db, sr.id)

    with patch("src.services.package_service._get_rabbitmq_channel", side_effect=Exception("MQTT caído")):
        # No debe lanzar excepción; el paquete igual se guarda en BD
        pkg = create_and_send_package(db, sr, payment)

    assert pkg is not None
    assert db.query(Package).filter_by(id=pkg.id).first() is not None

# ─── TESTS DE get_routes (JobsMaster real) ────────────────────────

MOCK_JOB_RESPONSE = {
    "status": "done",
    "routeMetricCost": 12000.0,
    "hops": ["LSN", "TRA", "HGW"],
    "hopCount": 2,
}

# Simula respuesta exitosa de POST /job.
def _mock_post(job_id="job-123"):
    mock = MagicMock()
    mock.json.return_value = {"jobId": job_id, "status": "pending"}
    mock.raise_for_status.return_value = None
    return mock

# Simula respuesta exitosa de GET /job/:id con status done.
def _mock_get_done():
    mock = MagicMock()
    mock.json.return_value = MOCK_JOB_RESPONSE
    mock.raise_for_status.return_value = None
    return mock

# test para verificar que get_routes retorna la ruta correctamente cuando el JobsMaster responde con éxito
def test_get_routes_ok():
    with patch("src.services.jobs_master_service.httpx.post", return_value=_mock_post()), \
         patch("src.services.jobs_master_service.httpx.get", return_value=_mock_get_done()), \
         patch("src.services.jobs_master_service.time.sleep"):
        result = get_routes("LSN", "HGW", "price")
    assert result["status"] == "done"
    assert result["routeMetricCost"] == 12000.0
    assert result["hops"] == ["LSN", "TRA", "HGW"]
    assert result["hopCount"] == 2

# test para verificar que si el POST para crear el job falla con timeout, get_routes lanza RuntimeError con mensaje de timeout
def test_get_routes_timeout_en_post():
    with patch("src.services.jobs_master_service.httpx.post",
               side_effect=httpx.TimeoutException("timeout")):
        with pytest.raises(RuntimeError, match="timeout"):
            get_routes("LSN", "HGW", "price")

# test para verificar que si el POST para crear el job falla con un error HTTP, get_routes lanza RuntimeError con mensaje de rechazo
def test_get_routes_error_http_en_post():
    mock = MagicMock()
    mock.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error", request=MagicMock(), response=MagicMock(status_code=500)
    )
    with patch("src.services.jobs_master_service.httpx.post", return_value=mock):
        with pytest.raises(RuntimeError, match="rechazó"):
            get_routes("LSN", "HGW", "price")

# test para verificar que si el POST para crear el job falla con una excepción de conexión, get_routes lanza RuntimeError con mensaje de conexión
def test_get_routes_respuesta_sin_job_id():
    mock = MagicMock()
    mock.json.return_value = {"status": "pending"}  # sin jobId
    mock.raise_for_status.return_value = None
    with patch("src.services.jobs_master_service.httpx.post", return_value=mock):
        with pytest.raises(RuntimeError, match="malformada"):
            get_routes("LSN", "HGW", "price")

# test para verificar que si el GET de polling responde con status failed, get_routes lanza RuntimeError con mensaje de fallo
def test_get_routes_status_failed():
    mock_get = MagicMock()
    mock_get.json.return_value = {"status": "failed", "error": "sin ruta disponible"}
    mock_get.raise_for_status.return_value = None
    with patch("src.services.jobs_master_service.httpx.post", return_value=_mock_post()), \
         patch("src.services.jobs_master_service.httpx.get", return_value=mock_get), \
         patch("src.services.jobs_master_service.time.sleep"):
        with pytest.raises(RuntimeError, match="falló"):
            get_routes("LSN", "HGW", "price")

# test para verificar que si el GET de polling responde con status pending en todos los intentos, get_routes lanza RuntimeError con mensaje de no completó
def test_get_routes_timeout_polling():
    mock_get = MagicMock()
    mock_get.json.return_value = {"status": "pending"}
    mock_get.raise_for_status.return_value = None
    with patch("src.services.jobs_master_service.httpx.post", return_value=_mock_post()), \
         patch("src.services.jobs_master_service.httpx.get", return_value=mock_get), \
         patch("src.services.jobs_master_service.time.sleep"), \
         patch("src.services.jobs_master_service.POLL_ATTEMPTS", 3):
        with pytest.raises(RuntimeError, match="no completó"):
            get_routes("LSN", "HGW", "price")

# done pero sin los campos requeridos.
def test_get_routes_done_malformado():
    mock_get = MagicMock()
    mock_get.json.return_value = {"status": "done"}  # faltan routeMetricCost, hops, hopCount
    mock_get.raise_for_status.return_value = None
    with patch("src.services.jobs_master_service.httpx.post", return_value=_mock_post()), \
         patch("src.services.jobs_master_service.httpx.get", return_value=mock_get), \
         patch("src.services.jobs_master_service.time.sleep"):
        with pytest.raises(RuntimeError, match="malformada"):
            get_routes("LSN", "HGW", "price")

# test para verificar que si el GET de polling falla con timeout en los primeros intentos pero eventualmente responde con status done, get_routes retorna la ruta correctamente
def test_get_routes_timeout_en_polling_get():
    mock_get_timeout = MagicMock()
    mock_get_timeout.raise_for_status.side_effect = httpx.TimeoutException("timeout")

    call_count = 0
    def get_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.TimeoutException("timeout")
        return _mock_get_done()

    with patch("src.services.jobs_master_service.httpx.post", return_value=_mock_post()), \
         patch("src.services.jobs_master_service.httpx.get", side_effect=get_side_effect), \
         patch("src.services.jobs_master_service.time.sleep"):
        result = get_routes("LSN", "HGW", "price")
    assert result["status"] == "done"


# ─── TESTS DE check_heartbeat ─────────────────────────────────────
# test para verificar que check_heartbeat retorna True cuando el JobsMaster responde con status 200
def test_check_heartbeat_ok():
    mock = MagicMock()
    mock.status_code = 200
    with patch("src.services.jobs_master_service.httpx.get", return_value=mock):
        assert check_heartbeat() is True

# test para verificar que check_heartbeat retorna False cuando el JobsMaster responde con un status diferente a 200
def test_check_heartbeat_falla_por_status():
    mock = MagicMock()
    mock.status_code = 503
    with patch("src.services.jobs_master_service.httpx.get", return_value=mock):
        assert check_heartbeat() is False

# test para verificar que check_heartbeat retorna False cuando hay una excepción al intentar conectar con el JobsMaster (por ejemplo, si el servicio está caído)
def test_check_heartbeat_falla_por_excepcion():
    with patch("src.services.jobs_master_service.httpx.get",
               side_effect=Exception("conexión rechazada")):
        assert check_heartbeat() is False