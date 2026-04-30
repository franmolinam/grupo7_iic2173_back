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


@pytest.fixture
def client():
    # Archivo temporal nuevo por cada test
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

    # Guardamos SessionLocal para los seeds
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


# --- Tests de GET /packages ---

def test_list_packages_empty(client):
    """Sin paquetes retorna lista vacía."""
    response = client.get("/packages/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["packages"] == []


def test_list_packages_returns_all(client):
    """Con paquetes en DB los retorna todos."""
    seed_package(client)
    seed_package(client)
    response = client.get("/packages/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["packages"]) == 2


def test_list_packages_response_fields(client):
    """Verifica que la respuesta incluye los campos requeridos por RF01."""
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


def test_list_packages_filter_by_status(client):
    """Filtro por status retorna solo los paquetes con ese estado."""
    seed_package(client, status="pending_delivery")
    seed_package(client, status="forwarded")
    response = client.get("/packages/?status=pending_delivery")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["packages"][0]["status"] == "pending_delivery"


def test_list_packages_filter_by_origin(client):
    """Filtro por origin_id retorna solo los paquetes de ese origen."""
    seed_package(client, origin_id="COR")
    seed_package(client, origin_id="HGW")
    response = client.get("/packages/?origin_id=COR")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["packages"][0]["origin_id"] == "COR"


def test_list_packages_filter_by_destination(client):
    """Filtro por destination_id."""
    seed_package(client, destination_id="LSN")
    seed_package(client, destination_id="HGW")
    response = client.get("/packages/?destination_id=LSN")
    assert response.status_code == 200
    assert response.json()["total"] == 1


# --- Tests de GET /packages/{id} ---

def test_get_package_by_id(client):
    """Retorna el paquete correcto por ID."""
    pkg = seed_package(client)
    response = client.get(f"/packages/{pkg.id}")
    assert response.status_code == 200


def test_get_package_not_found(client):
    """Retorna 404 si el paquete no existe."""
    response = client.get("/packages/no-existe")
    assert response.status_code == 404


# --- Tests de POST /packages/{id}/deliver ---

def test_deliver_package_success(client):
    """Entrega exitosa cuando deliverNotBefore ya pasó."""
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


def test_deliver_package_too_early(client):
    """Retorna 400 si deliverNotBefore aún no pasó."""
    pkg = seed_package(client,
        destination_id="LSN",
        deliver_not_before=datetime.now(timezone.utc) + timedelta(hours=5),
        status="pending_delivery",
    )
    response = client.post(f"/packages/{pkg.id}/deliver")
    assert response.status_code == 400
    assert "cannot be delivered before" in response.json()["detail"]


def test_deliver_package_not_found(client):
    """Retorna 404 si el paquete no existe."""
    response = client.post("/packages/no-existe/deliver")
    assert response.status_code == 404


def test_deliver_package_idempotencia(client):
    """Entregar dos veces retorna 400 en la segunda."""
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


# --- Tests de GET /connections ---

def test_list_connections_empty(client):
    """Sin conexiones retorna lista vacía."""
    response = client.get("/connections/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["connections"] == []


def test_list_connections_returns_all(client):
    """Con conexiones en DB las retorna todas."""
    seed_connection(client, destination_code="HGW")
    seed_connection(client, destination_code="COR")
    response = client.get("/connections/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


def test_list_connections_response_fields(client):
    """Verifica que la respuesta incluye los campos requeridos por RF02."""
    seed_connection(client)
    response = client.get("/connections/")
    assert response.status_code == 200
    c = response.json()["connections"][0]
    assert "destination_code" in c
    assert "destination_name" in c
    assert "enabled" in c


def test_list_connections_enabled_field(client):
    """El campo enabled refleja correctamente el estado de la conexión."""
    seed_connection(client, destination_code="HGW", enabled=True)
    seed_connection(client, destination_code="COR", enabled=False)
    response = client.get("/connections/")
    assert response.status_code == 200
    conns = {c["destination_code"]: c for c in response.json()["connections"]}
    assert conns["HGW"]["enabled"] == True
    assert conns["COR"]["enabled"] == False


# --- Tests de endpoints base ---

def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "LSN" in response.json()["message"]


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"