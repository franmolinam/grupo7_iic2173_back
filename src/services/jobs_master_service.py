import os
import httpx
import time

JOBS_MASTER_URL = os.getenv("JOBS_MASTER_URL", "http://localhost:8001")
CODIGO_CIUDAD = os.getenv("CODIGO_CIUDAD", "LSN").upper()


def get_routes_mock(origin: str, destination: str, criteria: str) -> dict:
    return {
        "status": "done",
        "routeMetricCost": 12000,
        "hops": [origin, "TRA", destination],
        "hopCount": 2,
    }


def get_routes_real(origin: str, destination: str, criteria: str) -> dict:
    try:
        # Crear el job
        response = httpx.post(
            f"{JOBS_MASTER_URL}/job",
            json={"origin": origin, "destination": destination, "criteria": criteria},
            timeout=10.0,
        )
        response.raise_for_status()
        job_id = response.json()["jobId"]

        # Polling hasta que el job esté listo
        for _ in range(10):
            result = httpx.get(f"{JOBS_MASTER_URL}/job/{job_id}", timeout=10.0)
            result.raise_for_status()
            data = result.json()
            if data["status"] == "done":
                return data
            time.sleep(1)

        raise TimeoutError("JobsMaster no respondió a tiempo")

    except Exception as e:
        raise RuntimeError(f"Error al consultar JobsMaster: {e}")


# Cambiar USE_MOCK a False cuando Back 1 implemente la lógica real
USE_MOCK = False

def get_routes(origin: str, destination: str, criteria: str) -> dict:
    if USE_MOCK:
        return get_routes_mock(origin, destination, criteria)
    return get_routes_real(origin, destination, criteria)