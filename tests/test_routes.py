import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone, timedelta
import uuid
import tempfile
import os

from src.main import app
from src.database import Base, get_db
from src.models.package import Package
from src.models.city_connection import CityConnection
from unittest.mock import patch
from src.models.shipment_request import ShipmentRequest
from src.auth_utils import validate_token, require_admin

# Archivo temporal nuevo por cada test
@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_validate_token():
        return {"sub": "auth0|testuser"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[validate_token] = override_validate_token
    app.dependency_overrides[require_admin] = override_validate_token

    # guardo SessionLocal para los seeds
    client_obj = TestClient(app)
    client_obj._test_session = SessionLocal

    with TestClient(app) as c:
        c._test_session = SessionLocal
        yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        os.unlink(db_path)
    except:
        pass

# insertar datos de prueba de packages en la base de datos durante los tests
def seed_package(client, **kwargs):
    db = client._test_session()
    defaults = {
        "id": str(uuid.uuid4()),
        "origin_id": "COR",
        "destination_id": "LSN",
        "max_hops": 3,
        "created_at": datetime.now(timezone.utc),
        "deliver_not_before": datetime.now(timezone.utc) - timedelta(hours=1),
        "status": "pending_delivery",
        "last_action": "received",
        "last_processed_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    pkg = Package(**defaults)
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    db.close()
    return pkg

# insertar conexiones de prueba en la base de datos durante los tests
def seed_connection(client, **kwargs):
    db = client._test_session()
    defaults = {
        "source_code": "LSN",
        "destination_code": "HGW",
        "destination_name": "Hogwarts",
        "distance": 1000.0,
        "transport_cost": 500.0,
        "enabled": True,
    }
    defaults.update(kwargs)
    conn = CityConnection(**defaults)
    db.add(conn)
    db.commit()
    db.close()
    return conn


# test para verificar que sin paquetes retorna lista vacía
def test_list_packages_empty(client):
    response = client.get("/packages/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["packages"] == []

# test para verificar que con paquetes en DB los retorna todos
def test_list_packages_returns_all(client):
    seed_package(client)
    seed_package(client)
    response = client.get("/packages/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["packages"]) == 2

# test para verificar que la respuesta incluye los campos requeridos
def test_list_packages_response_fields(client):
    seed_package(client)
    response = client.get("/packages/")
    assert response.status_code == 200
    p = response.json()["packages"][0]
    assert "id" in p
    assert "origin_id" in p
    assert "destination_id" in p
    assert "max_hops" in p
    assert "created_at" in p
    assert "deliver_not_before" in p
    assert "status" in p
    assert "last_action" in p

# test para verificar que el filtro por status retorna solo los paquetes con ese estado
def test_list_packages_filter_by_status(client):
    seed_package(client, status="pending_delivery")
    seed_package(client, status="forwarded")
    response = client.get("/packages/?status=pending_delivery")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["packages"][0]["status"] == "pending_delivery"

# test para verificar que el filtro por origin_id retorna solo los paquetes de ese origen
def test_list_packages_filter_by_origin(client):
    seed_package(client, origin_id="COR")
    seed_package(client, origin_id="HGW")
    response = client.get("/packages/?origin_id=COR")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["packages"][0]["origin_id"] == "COR"

# test para verificar que el filtro por destination_id retorna solo los paquetes de ese destino
def test_list_packages_filter_by_destination(client):
    seed_package(client, destination_id="LSN")
    seed_package(client, destination_id="HGW")
    response = client.get("/packages/?destination_id=LSN")
    assert response.status_code == 200
    assert response.json()["total"] == 1


# test para verificar que retorna el paquete correcto por ID
def test_get_package_by_id(client):
    pkg = seed_package(client)
    response = client.get(f"/packages/{pkg.id}")
    assert response.status_code == 200

# test para verificar que retorna 404 si el paquete no existe
def test_get_package_not_found(client):
    response = client.get("/packages/no-existe")
    assert response.status_code == 404

# test para verificar entrega exitosa cuando deliverNotBefore ya pasó
def test_deliver_package_success(client):
    pkg = seed_package(
        client,
        destination_id="LSN",
        deliver_not_before=datetime.now(timezone.utc) - timedelta(hours=1),
        status="pending_delivery",
    )
    response = client.post(f"/packages/{pkg.id}/deliver")
    assert response.status_code == 200
    data = response.json()
    assert data["package"]["status"] == "delivered"

# test para verificar que retorna 400 si deliverNotBefore aún no pasó
def test_deliver_package_too_early(client):
    pkg = seed_package(client,
        destination_id="LSN",
        deliver_not_before=datetime.now(timezone.utc) + timedelta(hours=5),
        status="pending_delivery",
    )
    response = client.post(f"/packages/{pkg.id}/deliver")
    assert response.status_code == 400
    assert "cannot be delivered before" in response.json()["detail"]

# test para verificar que retorna 404 si el paquete no existe
def test_deliver_package_not_found(client):
    response = client.post("/packages/no-existe/deliver")
    assert response.status_code == 404

# test para verificar que entregar dos veces retorna 400 en la segunda
def test_deliver_package_idempotencia(client):
    pkg = seed_package(
        client,
        destination_id="LSN",
        deliver_not_before=datetime.now(timezone.utc) - timedelta(hours=1),
        status="pending_delivery",
    )
    client.post(f"/packages/{pkg.id}/deliver")
    response = client.post(f"/packages/{pkg.id}/deliver")
    assert response.status_code == 400
    assert "already delivered" in response.json()["detail"]

# test para verificar que sin conexiones retorna lista vacía
def test_list_connections_empty(client):
    response = client.get("/connections/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["connections"] == []

# test para verificar que si hay conexiones en la DB las retorna todas
def test_list_connections_returns_all(client):
    seed_connection(client, destination_code="HGW")
    seed_connection(client, destination_code="COR")
    response = client.get("/connections/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2

# test para verificar que la respuesta incluye los campos requeridos
def test_list_connections_response_fields(client):
    seed_connection(client)
    response = client.get("/connections/")
    assert response.status_code == 200
    c = response.json()["connections"][0]
    assert "destination_code" in c
    assert "destination_name" in c
    assert "enabled" in c

# test para verificar que el campo enabled refleja correctamente el estado de la conexión
def test_list_connections_enabled_field(client):
    seed_connection(client, destination_code="HGW", enabled=True)
    seed_connection(client, destination_code="COR", enabled=False)
    response = client.get("/connections/")
    assert response.status_code == 200
    conns = {c["destination_code"]: c for c in response.json()["connections"]}
    assert conns["HGW"]["enabled"] == True
    assert conns["COR"]["enabled"] == False

# testeo el endpoint raíz solo para verificar que la app está corriendo y responde
def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "LSN" in response.json()["message"]

# testeo el endpoint de health solo para verificar que la app está corriendo y responde
def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


MOCK_ROUTE = {
    "status": "done",
    "routeMetricCost": 12000,
    "hops": ["LSN", "TRA", "HGW"],
    "hopCount": 2,
}

# test para verificar que POST /shipments retorna 201 con cotización completa
def test_create_shipment_ok(client):
    with patch("src.routes.shipments.get_quotation", return_value={
        "criteria": "price",
        "route_metric_cost": 12000,
        "hops_count": 2,
        "next_hop": "TRA",
        "full_path": ["LSN", "TRA", "HGW"],
        "fprice": 1.0,
        "final_price": 36000,
    }):
        response = client.post("/shipments", json={
            "destination_id": "HGW",
            "height": 100,
            "width": 100,
            "depth": 100,
            "criteria": "price",
            "max_hops": 3,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "quoted"
        assert data["final_price"] == 36000
        assert data["next_hop"] == "TRA"

# test de regresión: priority_class del body debe reenviarse a get_quotation
# (bug encontrado: el handler lo ignoraba y calculate_price siempre usaba "medium")
def test_create_shipment_reenvia_priority_class(client):
    with patch("src.routes.shipments.get_quotation", return_value={
        "criteria": "price",
        "route_metric_cost": 12000,
        "hops_count": 2,
        "next_hop": "TRA",
        "full_path": ["LSN", "TRA", "HGW"],
        "fprice": 1.0,
        "final_price": 90000,
    }) as mock_get_quotation:
        response = client.post("/shipments", json={
            "destination_id": "HGW",
            "height": 100,
            "width": 100,
            "depth": 100,
            "criteria": "price",
            "max_hops": 3,
            "priority_class": "high",
        })
        assert response.status_code == 201
        assert mock_get_quotation.call_args.kwargs["priority_class"] == "high"
        assert response.json()["priority_class"] == "high"

# test para verificar que dimensiones inválidas retornan 400
def test_create_shipment_dimensiones_invalidas(client):
    with patch("src.routes.shipments.get_quotation", side_effect=ValueError("Las dimensiones superan el máximo")):
        response = client.post("/shipments", json={
            "destination_id": "HGW",
            "height": 1000,
            "width": 1000,
            "depth": 1001,
            "criteria": "price",
            "max_hops": 3,
        })
        assert response.status_code == 400
        assert "dimensiones" in response.json()["detail"]

# test para verificar que ciudad no alcanzable retorna 400
def test_create_shipment_ciudad_no_alcanzable(client):
    with patch("src.routes.shipments.get_quotation", side_effect=ValueError("no es alcanzable")):
        response = client.post("/shipments", json={
            "destination_id": "XYZ",
            "height": 10,
            "width": 10,
            "depth": 10,
            "criteria": "price",
            "max_hops": 3,
        })
        assert response.status_code == 400
        assert "alcanzable" in response.json()["detail"]

# test para verificar que maxHops insuficiente retorna 400
def test_create_shipment_max_hops_insuficiente(client):
    with patch("src.routes.shipments.get_quotation", side_effect=ValueError("maxHops insuficiente")):
        response = client.post("/shipments", json={
            "destination_id": "HGW",
            "height": 10,
            "width": 10,
            "depth": 10,
            "criteria": "price",
            "max_hops": 1,
        })
        assert response.status_code == 400
        assert "maxHops" in response.json()["detail"]

# test para verificar que criteria inválido retorna 422
def test_create_shipment_criteria_invalido(client):
        response = client.post("/shipments", json={
            "destination_id": "HGW",
            "height": 10,
            "width": 10,
            "depth": 10,
            "criteria": "velocidad",
            "max_hops": 3,
        })
        assert response.status_code == 422

# insertar un shipment request de prueba en la base de datos durante los tests de pagos
def seed_shipment(client, **kwargs):
    db = client._test_session()
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
        "status": "quoted",
    }
    defaults.update(kwargs)
    sr = ShipmentRequest(**defaults)
    db.add(sr)
    db.commit()
    db.refresh(sr)
    db.close()
    return sr


# TEST DE POST /shipments/:id/pay
# Para estos tests se asume que create_transaction y commit_transaction funcionan correctamente, por lo que se mockean para no depender de Webpay ni de la lógica interna de esas funciones.
# inicio de pago exitoso retorna token y url de Webpay para redirigir al usuario a pagar, y también el payment_id generado para identificar el pago en el callback
def test_initiate_payment_ok(client):
    sr = seed_shipment(client)
    with patch("src.routes.payments.create_transaction", return_value={
        "token": "token-webpay-test",
        "url": "https://webpay3gint.transbank.cl/initTransaction",
    }), patch("src.routes.payments.enviar_auditoria_pago"):
        response = client.post(f"/shipments/{sr.id}/pay")
        assert response.status_code == 201
        data = response.json()
        assert "token" in data
        assert "url" in data
        assert "payment_id" in data

# iniciar pago con shipment request inexistente retorna 404
def test_initiate_payment_shipment_not_found(client):
    with patch("src.routes.payments.create_transaction"), \
         patch("src.routes.payments.enviar_auditoria_pago"):
        response = client.post("/shipments/no-existe/pay")
        assert response.status_code == 404

# iniciar pago con shipment request que no está en estado "quoted" retorna 400
def test_initiate_payment_shipment_not_quoted(client):
    sr = seed_shipment(client, status="paying")
    with patch("src.routes.payments.create_transaction"), \
         patch("src.routes.payments.enviar_auditoria_pago"):
        response = client.post(f"/shipments/{sr.id}/pay")
        assert response.status_code == 400

# iniciar pago dos veces retorna 409 en la segunda vez por idempotencia
def test_initiate_payment_idempotencia(client):
    sr = seed_shipment(client)
    with patch("src.routes.payments.create_transaction", return_value={
        "token": "token-webpay-test",
        "url": "https://webpay3gint.transbank.cl/initTransaction",
    }), patch("src.routes.payments.enviar_auditoria_pago"):
        client.post(f"/shipments/{sr.id}/pay")
        response = client.post(f"/shipments/{sr.id}/pay")
        assert response.status_code == 409


# TEST DE POST /payments/callback
# Para estos tests se asume que commit_transaction funciona correctamente, por lo que se mockea para no depender de Webpay ni de la lógica interna de esa función.
def test_callback_success(client):
    sr = seed_shipment(client, status="paying")
    db = client._test_session()
    from src.models.payment import Payment
    payment = Payment(
        id=str(uuid.uuid4()),
        shipment_request_id=sr.id,
        user_id="auth0|testuser",
        webpay_token="token-success",
        status="TRYING",
        amount=36000,
        currency="CLP",
    )
    db.add(payment)
    db.commit()
    db.close()

    with patch("src.routes.payments.commit_transaction", return_value={
        "response_code": 0,
        "authorization_code": "AUTH-123",
        "amount": 36000,
        "transaction_date": "2026-06-05T12:00:00",
        "status": "AUTHORIZED",
    }), patch("src.routes.payments.enviar_auditoria_pago"):
        response = client.post("/payments/callback", json={"token_ws": "token-success"})
        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"

# callback con token que retorna estado FAILED actualiza el pago a FAILED
def test_callback_failed(client):
    sr = seed_shipment(client, status="paying")
    db = client._test_session()
    from src.models.payment import Payment
    payment = Payment(
        id=str(uuid.uuid4()),
        shipment_request_id=sr.id,
        user_id="auth0|testuser",
        webpay_token="token-failed",
        status="TRYING",
        amount=36000,
        currency="CLP",
    )
    db.add(payment)
    db.commit()
    db.close()

    with patch("src.routes.payments.commit_transaction", return_value={
        "response_code": -1,
        "authorization_code": None,
        "amount": 36000,
        "transaction_date": None,
        "status": "FAILED",
    }), patch("src.routes.payments.enviar_auditoria_pago"):
        response = client.post("/payments/callback", json={"token_ws": "token-failed"})
        assert response.status_code == 200
        assert response.json()["status"] == "FAILED"

# callback con token que retorna estado distinto a AUTHORIZED o FAILED actualiza el pago a CANCELLED
def test_callback_cancelled(client):
    response = client.post("/payments/callback", json={"token_ws": None})
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"

# callback con token que ya fue procesado como SUCCESS no vuelve a actualizar el pago (idempotencia)
def test_callback_idempotencia(client):
    sr = seed_shipment(client, status="paying")
    db = client._test_session()
    from src.models.payment import Payment
    payment = Payment(
        id=str(uuid.uuid4()),
        shipment_request_id=sr.id,
        user_id="auth0|testuser",
        webpay_token="token-idem",
        status="SUCCESS",
        amount=36000,
        currency="CLP",
    )
    db.add(payment)
    db.commit()
    db.close()

    response = client.post("/payments/callback", json={"token_ws": "token-idem"})
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"

# callback con token que no existe retorna 404
def test_callback_token_not_found(client):
    response = client.post("/payments/callback", json={"token_ws": "token-inexistente"})
    assert response.status_code == 404  

# Para estos tests se asume que el endpoint de creación de shipments funciona correctamente, por lo que se insertan ShipmentRequest de prueba directamente en la base de datos usando un helper (seed_shipment) en vez de crear shipments a través del endpoint POST /shipments.
# test para verificar que si el usuario no tiene shipments retorna lista vacía
def test_my_shipments_empty(client):
    response = client.get("/shipments/my-shipments")
    assert response.status_code == 200
    assert response.json() == []

# test para verificar que retorna sólo los shipments del usuario autenticado
def test_my_shipments_retorna_los_del_usuario(client):
    seed_shipment(client)
    seed_shipment(client)
    response = client.get("/shipments/my-shipments")
    assert response.status_code == 200
    assert len(response.json()) == 2

# test para verificar que no retorna shipments de otro usuario
def test_my_shipments_no_retorna_de_otro_usuario(client):
    # shipment del usuario autenticado (auth0|testuser)
    seed_shipment(client)
    # shipment de otro usuario
    seed_shipment(client, user_id="auth0|otrouser")

    response = client.get("/shipments/my-shipments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert all(s["origin_id"] == "LSN" for s in data)  # sólo el nuestro

# test para verificar que la respuesta incluye los campos requeridos
def test_my_shipments_campos_requeridos(client):
    seed_shipment(client)
    response = client.get("/shipments/my-shipments")
    assert response.status_code == 200
    s = response.json()[0]
    for campo in ["id", "status", "origin_id", "destination_id", "criteria",
                  "max_hops", "final_price", "created_at", "payment", "package"]:
        assert campo in s

# test para verificar que el campo payment es None si no hay pago asociado al shipment
def test_my_shipments_payment_none_sin_pago(client):
    seed_shipment(client)
    response = client.get("/shipments/my-shipments")
    assert response.status_code == 200
    assert response.json()[0]["payment"] is None

# test para verificar que el campo payment incluye el último pago asociado al shipment, si existe
def test_my_shipments_incluye_pago(client):
    from src.models.payment import Payment as PaymentModel
    sr = seed_shipment(client, status="paying")
    db = client._test_session()
    payment = PaymentModel(
        id=str(uuid.uuid4()),
        shipment_request_id=sr.id,
        user_id="auth0|testuser",
        webpay_token="tok-test",
        status="TRYING",
        amount=36000,
        currency="CLP",
    )
    db.add(payment)
    db.commit()
    db.close()

    response = client.get("/shipments/my-shipments")
    assert response.status_code == 200
    pago = response.json()[0]["payment"]
    assert pago is not None
    assert pago["status"] == "TRYING"
    assert pago["amount"] == 36000

# test para verificar que el campo package es None si no hay paquete asociado al shipment
def test_my_shipments_incluye_paquete(client):
    from src.models.package import Package as PackageModel
    from src.models.payment import Payment as PaymentModel
    sr = seed_shipment(client, status="forwarded")
    db = client._test_session()
    pkg = PackageModel(
        id=str(uuid.uuid4()),
        origin_id="LSN",
        destination_id="HGW",
        max_hops=3,
        created_at=datetime.now(timezone.utc),
        deliver_not_before=datetime.now(timezone.utc),
        status="forwarded",
        last_action="forwarded",
        last_processed_at=datetime.now(timezone.utc),
        shipment_request_id=sr.id,
    )
    db.add(pkg)
    db.commit()
    db.close()

    response = client.get("/shipments/my-shipments")
    assert response.status_code == 200
    paquete = response.json()[0]["package"]
    assert paquete is not None
    assert paquete["status"] == "forwarded"

# test para verificar que si el shipment no tiene paquete asociado, el campo package es None
def test_my_shipments_package_none_sin_paquete(client):
    seed_shipment(client, status="quoted")
    response = client.get("/shipments/my-shipments")
    assert response.status_code == 200
    assert response.json()[0]["package"] is None

# test para verificar que los shipments se ordenan por fecha de creación descendente (más recientes primero)
def test_my_shipments_orden_descendente(client):
    import time
    sr1 = seed_shipment(client)
    time.sleep(0.01)
    sr2 = seed_shipment(client)
    response = client.get("/shipments/my-shipments")
    assert response.status_code == 200
    ids = [s["id"] for s in response.json()]
    assert ids[0] == sr2.id  # el más reciente primero

# test para verificar que con pago exitoso, se crea un paquete asociado al shipment y el estado del shipment se actualiza a "forwarded"
def test_callback_success_crea_paquete_y_estado_forwarded(client):
    sr = seed_shipment(client, status="paying")
    db = client._test_session()
    from src.models.payment import Payment as PaymentModel
    payment = PaymentModel(
        id=str(uuid.uuid4()),
        shipment_request_id=sr.id,
        user_id="auth0|testuser",
        webpay_token="token-rf04",
        status="TRYING",
        amount=36000,
        currency="CLP",
    )
    db.add(payment)
    db.commit()
    db.close()

    with patch("src.routes.payments.commit_transaction", return_value={
        "response_code": 0,
        "authorization_code": "AUTH-RF04",
        "amount": 36000,
        "transaction_date": "2026-06-05T12:00:00",
        "status": "AUTHORIZED",
    }), patch("src.routes.payments.enviar_auditoria_pago"), \
       patch("src.routes.payments.create_and_send_package") as mock_create:
        from src.models.package import Package as PackageModel
        fake_pkg = PackageModel(id="pkg-fake-id", origin_id="LSN", destination_id="HGW",
                                max_hops=2, created_at=datetime.now(timezone.utc),
                                deliver_not_before=datetime.now(timezone.utc),
                                status="forwarded", last_action="forwarded",
                                last_processed_at=datetime.now(timezone.utc))
        mock_create.return_value = fake_pkg

        response = client.post("/payments/callback", json={"token_ws": "token-rf04"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["package_id"] == "pkg-fake-id"
    assert data["shipment_status"] == "forwarded"
    mock_create.assert_called_once()

# test para verificar que si el pago es exitoso pero no se crea el paquete (por ejemplo, por error en create_and_send_package), el endpoint igual retorna 200 pero sin package_id ni actualización del estado del shipment
def test_callback_success_sin_shipment_no_crea_paquete(client):
    db = client._test_session()
    from src.models.payment import Payment as PaymentModel
    # pago sin shipment_request asociado (forzamos shipment_request_id inexistente)
    payment = PaymentModel(
        id=str(uuid.uuid4()),
        shipment_request_id="no-existe",
        user_id="auth0|testuser",
        webpay_token="token-noshipment",
        status="TRYING",
        amount=36000,
        currency="CLP",
    )
    db.add(payment)
    db.commit()
    db.close()

    with patch("src.routes.payments.commit_transaction", return_value={
        "response_code": 0,
        "authorization_code": "AUTH-X",
        "amount": 36000,
        "transaction_date": "2026-06-05T12:00:00",
        "status": "AUTHORIZED",
    }), patch("src.routes.payments.enviar_auditoria_pago"), \
       patch("src.routes.payments.create_and_send_package") as mock_create:

        response = client.post("/payments/callback", json={"token_ws": "token-noshipment"})

    assert response.status_code == 200
    mock_create.assert_not_called()

# test para verificar que si no hay registro en la base de datos para fprice, el endpoint GET /config/fprice retorna el valor default definido en el .env (1.0)
def test_get_fprice_default(client):
    response = client.get("/config/fprice")
    assert response.status_code == 200
    assert response.json()["fprice"] == 1.0

# test para verificar que si hay un registro en la base de datos para fprice, el endpoint GET /config/fprice retorna ese valor en vez del default
def test_get_fprice_desde_bd(client):
    from src.models.branch_config import BranchConfig
    db = client._test_session()
    db.add(BranchConfig(key="fprice", value=1.5))
    db.commit()
    db.close()

    response = client.get("/config/fprice")
    assert response.status_code == 200
    assert response.json()["fprice"] == 1.5

# test para verificar que el endpoint PUT /config/fprice actualiza el valor de fprice en la base de datos, y que luego GET /config/fprice devuelve el nuevo valor actualizado
def test_put_fprice_actualiza_valor(client):
    response = client.put("/config/fprice", json={"value": 1.8})
    assert response.status_code == 200
    assert response.json()["fprice"] == 1.8

    # Verificar que GET devuelve el nuevo valor
    response2 = client.get("/config/fprice")
    assert response2.json()["fprice"] == 1.8

# test para verificar que si se hace PUT /config/fprice con un valor nuevo, y luego otro PUT con otro valor distinto, el segundo PUT sobrescribe el valor anterior en la base de datos (en vez de crear un nuevo registro), y GET /config/fprice devuelve el último valor actualizado
def test_put_fprice_sobrescribe_valor_existente(client):
    client.put("/config/fprice", json={"value": 1.5})
    client.put("/config/fprice", json={"value": 0.8})

    response = client.get("/config/fprice")
    assert response.json()["fprice"] == 0.8

    # Verificar que no se crearon duplicados en BD
    from src.models.branch_config import BranchConfig
    db = client._test_session()
    count = db.query(BranchConfig).filter_by(key="fprice").count()
    db.close()
    assert count == 1

# test para verificar que el endpoint PUT /config/fprice valida que el valor esté dentro del rango permitido (0.5 a 2.0), y retorna 422 si se intenta actualizar con un valor fuera de ese rango
def test_put_fprice_rechaza_menor_a_minimo(client):
    response = client.put("/config/fprice", json={"value": 0.4})
    assert response.status_code == 422

# test para verificar que el endpoint PUT /config/fprice valida que el valor esté dentro del rango permitido (0.5 a 2.0), y retorna 422 si se intenta actualizar con un valor fuera de ese rango
def test_put_fprice_rechaza_mayor_a_maximo(client):
    response = client.put("/config/fprice", json={"value": 2.1})
    assert response.status_code == 422

# test para verificar que el endpoint PUT /config/fprice acepta valores dentro del rango permitido, incluyendo los límites exactos (0.5 y 2.0), y actualiza correctamente el valor en la base de datos
def test_put_fprice_acepta_limites_exactos(client):
    response = client.put("/config/fprice", json={"value": 0.5})
    assert response.status_code == 200
    response = client.put("/config/fprice", json={"value": 2.0})
    assert response.status_code == 200

# test para verificar que el endpoint PUT /config/fprice requiere autenticación, y que sin un token válido retorna 401 o 403 (dependiendo de la configuración de seguridad), lo que verifica que el override de validate_token está funcionando correctamente en los tests
def test_put_fprice_requiere_auth(client):
    """Sin override de auth debería fallar — verificamos que el dep está puesto."""
    # Removemos el override de validate_token temporalmente
    del app.dependency_overrides[validate_token]
    del app.dependency_overrides[require_admin]
    response = client.put("/config/fprice", json={"value": 1.5})
    # Restaurar
    app.dependency_overrides[validate_token] = lambda: {"sub": "auth0|testadmin"}
    app.dependency_overrides[require_admin] = lambda: {"sub": "auth0|testadmin"}
    assert response.status_code in (401, 403)

# Para estos tests se asume que la función check_heartbeat que verifica el estado del worker de procesamiento de paquetes funciona correctamente, por lo que se mockea para no depender de la lógica interna de esa función ni del estado real del worker durante los tests.
# test para verificar que si check_heartbeat retorna True, el endpoint GET /jobs/heartbeat retorna alive: true
def test_jobs_heartbeat_alive(client):
    with patch("src.routes.shipments.check_heartbeat", return_value=True):
        response = client.get("/shipments/jobs/heartbeat")
    assert response.status_code == 200
    assert response.json()["alive"] is True

# test para verificar que si check_heartbeat retorna False, el endpoint GET /jobs/heartbeat retorna alive: false
def test_jobs_heartbeat_down(client):
    with patch("src.routes.shipments.check_heartbeat", return_value=False):
        response = client.get("/shipments/jobs/heartbeat")
    assert response.status_code == 200
    assert response.json()["alive"] is False
