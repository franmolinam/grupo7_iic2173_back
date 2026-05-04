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

    app.dependency_overrides[get_db] = override_get_db

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